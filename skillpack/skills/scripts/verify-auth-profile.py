#!/usr/bin/env python3
"""Authorization and execution-profile gate (T15, spec 17.4).

Why this file exists
--------------------
``ready_for_act: true`` in scope.md is one copyable English word. Any agent
(or any prompt-injection payload, cf. the 131 ``AI LOAD INSTRUCTION`` sites)
can type it. This gate makes ACT readiness depend on facts that recompute,
not on text that copies:

* ``work/<case>/auth-profile.json`` -- who approved, what targets/actions,
  validity window, proof reference, execution limits (schemas/auth-profile.json)
* ``work/<case>/attestation.json`` -- offline-reviewable binding whose digest
  recomputes live from case_id + target digest + profile + risk + expiry +
  nonce + issuer (schemas/case-attestation.json)

A copied ``ready_for_act`` line, a foreign attestation, or an edited
allowlist never recomputes, so the gate exits 20 (blocked, spec 4.7).

Relationship to existing scripts (reuse, do not duplicate, do not weaken)
-------------------------------------------------------------------------
* ``skills/scripts/case-guard.ps1`` stays the canonical scope gate
  (auth.status + network_profile + assets + ready_for_act). This gate layers
  the 17.4 checks on top and never replaces it; both must pass before ACT.
* ``skills/scripts/verify-path-and-target.py`` (T22) owns realpath
  containment and DNS/redirect/port enforcement. This gate only checks that
  egress is *declared* and *consistent* (offline => empty egress, otherwise
  egress inside the target allowlist); per-request enforcement stays T22's.
* ``scripts/verify-release-approval.py`` (T16) owns the human-approval trust
  model this gate mirrors: identity is enforced by the approval process, the
  record carries the claim the gate re-verifies.

Read-only: verification never writes. Only ``--issue-attestation`` writes
one file (the attestation the issuer signs off), and only inside the case dir.

Exit codes (spec 4.7): 0 = allow, 20 = blocked, 2 = usage error.

Standard library only. No network access. No defaults are ever filled in:
a missing file or field is BLOCKED, never silently passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# Actions that always need a recorded human confirmation, even when listed
# in allowed_actions. Kept intentionally small and frozen: widening this set
# is a policy change, narrowing it is a weakening (forbidden).
DANGEROUS_ACTIONS = frozenset({
    "exploit_validate",
    "payload_execute",
    "credential_use",
    "active_scan",
    "data_exfil",
})

PLACEHOLDER_PROOF = {"", "fill_me", "todo", "tbd", "none", "null", "n/a"}
RFC3339_Z = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z$")

def parse_rfc3339_z(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)

def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def target_digest(allowlist: list[str]) -> str:
    return "sha256:" + sha256_hex("\n".join(sorted(allowlist)))

def binding_digest(case_id: str, tdigest: str, profile: str, risk: str,
                   expires_at: str, nonce: str, issuer: str) -> str:
    return "sha256:" + sha256_hex("\n".join(
        [case_id, tdigest, profile, risk, expires_at, nonce, issuer]))

def host_of(entry: str) -> str:
    """Host part of a URL-ish or bare-host allowlist entry, lowercased."""
    text = entry.strip()
    if "://" not in text:
        text = "https://" + text
    try:
        host = urlsplit(text).hostname or ""
    except ValueError:
        host = ""
    return host.lower()

# --------------------------------------------------------------------------
# scope.md parsing (same section/field shape case-guard.ps1 reads)
# --------------------------------------------------------------------------

def scope_section(text: str, name: str) -> str:
    match = re.search(r"(?ms)^##\s*" + re.escape(name) + r"\s*\r?\n(.*?)(?=^##\s|\Z)",
                      text)
    return match.group(1) if match else ""

def section_field(section: str, name: str) -> str:
    match = re.search(r"(?m)^\s*-\s*" + re.escape(name) + r":\s*(.*?)\s*$", section)
    return match.group(1).strip() if match else ""

def read_scope(case_root: Path) -> tuple[dict[str, str] | None, str]:
    scope_path = case_root / "scope.md"
    if not scope_path.is_file():
        return None, "scope.md missing"
    text = scope_path.read_text(encoding="utf-8", errors="replace")
    auth = scope_section(text, "auth")
    net = scope_section(text, "network_profile")
    signoff = scope_section(text, "signoff")
    inscope = scope_section(text, "in_scope")
    meta = scope_section(text, "meta")
    assets = []
    assets_block = re.search(r"(?ms)-\s*assets:\s*\r?\n((?:\s+.+\r?\n?|\s*\r?\n?)*)",
                             inscope)
    if assets_block:
        for line in assets_block.group(1).splitlines():
            item = re.match(r"^\s+-\s+(?!\[\s*\])(\S.+?)\s*$", line)
            if item:
                assets.append(item.group(1))
    return {
        "case_id": section_field(meta, "case_id"),
        "auth_status": section_field(auth, "status"),
        "evidence_of_auth": section_field(auth, "evidence_of_auth"),
        "net_mode": section_field(net, "mode"),
        "ready_for_act": section_field(signoff, "ready_for_act"),
        "assets": assets,  # type: ignore[dict-item]
    }, ""

def load_json(path: Path) -> tuple[dict | None, str]:
    if not path.is_file():
        return None, f"{path.name} missing"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return None, f"{path.name} is not valid JSON: {error}"
    if not isinstance(document, dict):
        return None, f"{path.name} must be a JSON object"
    return document, ""

# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------

class Verdict:
    def __init__(self) -> None:
        self.blocks: list[str] = []

    def deny(self, reason: str) -> None:
        self.blocks.append(reason)

    def ok(self) -> bool:
        return not self.blocks

def check_required_shape(document: dict, required: list[str], where: str,
                         verdict: Verdict) -> None:
    for key in required:
        if key not in document:
            verdict.deny(f"{where}.{key} missing (no defaults fill this in)")

def verify(case_root: Path, action: str | None,
           now: datetime) -> tuple[bool, list[str], dict]:
    verdict = Verdict()
    detail: dict = {"case": case_root.as_posix()}

    scope, problem = read_scope(case_root)
    if scope is None:
        verdict.deny(problem)
        return False, verdict.blocks, detail
    detail["scope_case_id"] = scope["case_id"]

    # 1. canonical scope hard gate (mirrors case-guard; never weakened here)
    if scope["auth_status"] != "granted":
        verdict.deny("scope auth.status is not granted")
    if scope["evidence_of_auth"].strip().lower() in PLACEHOLDER_PROOF:
        verdict.deny("scope evidence_of_auth is a placeholder, not proof")
    if scope["ready_for_act"] != "true":
        verdict.deny("scope ready_for_act is not true")
    if not scope["assets"]:
        verdict.deny("scope in_scope.assets is empty")
    if not scope["net_mode"]:
        verdict.deny("scope network_profile.mode missing")

    # 2. auth proof file must exist (missing proof is BLOCKED, never defaulted)
    auth, problem = load_json(case_root / "auth-profile.json")
    if auth is None:
        verdict.deny(f"auth proof missing: {problem}")
        return False, verdict.blocks, detail
    check_required_shape(auth, ["schemaVersion", "case_id", "approver",
                                "issued_at", "expires_at", "target_allowlist",
                                "allowed_actions", "evidence_reference",
                                "revocation_status", "execution_profile",
                                "human_confirmations"],
                         "auth-profile", verdict)
    if not verdict.ok():
        return False, verdict.blocks, detail

    # 3. identity / linkage: the fact must belong to THIS case
    if auth["case_id"] != scope["case_id"]:
        verdict.deny("auth-profile.case_id does not match scope.md case_id "
                     "(foreign proof)")
    if not isinstance(auth["approver"], str) or not auth["approver"].strip():
        verdict.deny("auth-profile.approver missing")
    if (not isinstance(auth["evidence_reference"], str)
            or auth["evidence_reference"].strip().lower() in PLACEHOLDER_PROOF):
        verdict.deny("auth-profile.evidence_reference is a placeholder, not proof")
    if auth.get("revocation_status") != "active":
        verdict.deny("auth-profile.revocation_status is not active")

    # 4. expiry (expired authorization is BLOCKED)
    try:
        expires = parse_rfc3339_z(auth["expires_at"])
    except (ValueError, TypeError):
        verdict.deny("auth-profile.expires_at is not UTC RFC 3339")
        expires = None
    if expires is not None and expires <= now:
        verdict.deny(f"authorization expired at {auth['expires_at']}")

    # 5. blank target allowlist is BLOCKED
    allowlist = auth.get("target_allowlist")
    if not isinstance(allowlist, list) or not allowlist or not all(
            isinstance(item, str) and item.strip() for item in allowlist):
        verdict.deny("auth-profile.target_allowlist is blank")

    # 6. out-of-scope action is BLOCKED (only when an action is presented)
    allowed = auth.get("allowed_actions")
    if action is not None:
        if not isinstance(allowed, list) or action not in allowed:
            verdict.deny(f"action {action!r} is outside allowed_actions")
        elif action in DANGEROUS_ACTIONS:
            confirmations = auth.get("human_confirmations")
            entry = confirmations.get(action) if isinstance(
                confirmations, dict) else None
            if (not isinstance(entry, dict) or not entry.get("by")
                    or not isinstance(entry.get("at"), str)
                    or not RFC3339_Z.match(entry["at"])):
                verdict.deny(f"dangerous action {action!r} has no human "
                             f"confirmation record")

    # 7. execution profile: filesystem / egress / limits, no default bypass
    profile = auth.get("execution_profile")
    if not isinstance(profile, dict):
        verdict.deny("auth-profile.execution_profile missing")
        return False, verdict.blocks, detail
    check_required_shape(profile, ["filesystem_allowlist",
                                   "network_egress_allowlist",
                                   "credential_policy", "max_runtime_s",
                                   "max_retries", "max_requests",
                                   "max_artifact_bytes",
                                   "requires_human_confirmation"],
                         "execution_profile", verdict)
    if verdict.ok():
        fs_allow = profile["filesystem_allowlist"]
        if (not isinstance(fs_allow, list) or not fs_allow or not all(
                isinstance(item, str) and item.strip() for item in fs_allow)):
            verdict.deny("execution_profile.filesystem_allowlist is blank")
        egress = profile["network_egress_allowlist"]
        if not isinstance(egress, list) or not all(
                isinstance(item, str) for item in egress):
            verdict.deny("execution_profile.network_egress_allowlist malformed")
        elif scope["net_mode"] == "offline" and egress:
            verdict.deny("offline profile must not declare network egress")
        elif (scope["net_mode"] and scope["net_mode"] != "offline"
                and isinstance(allowlist, list) and allowlist):
            allowed_hosts = {host_of(item) for item in allowlist}
            for entry in egress:
                if host_of(entry) not in allowed_hosts:
                    verdict.deny(f"egress {entry!r} is outside target_allowlist")
                    break
        for key in ("max_runtime_s", "max_requests", "max_artifact_bytes"):
            value = profile.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                verdict.deny(f"execution_profile.{key} must be a positive integer")
        retries = profile.get("max_retries")
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
            verdict.deny("execution_profile.max_retries must be a non-negative integer")
        if not isinstance(profile.get("credential_policy"), str) or not profile[
                "credential_policy"].strip():
            verdict.deny("execution_profile.credential_policy missing")
        if not isinstance(profile.get("requires_human_confirmation"), bool):
            verdict.deny("execution_profile.requires_human_confirmation "
                         "must be boolean")

    # 8. case attestation: recompute, never trust the text
    attestation, problem = load_json(case_root / "attestation.json")
    if attestation is None:
        verdict.deny(f"case attestation missing: {problem} "
                     f"(ready_for_act text alone never suffices)")
        return False, verdict.blocks, detail
    check_required_shape(attestation, ["schemaVersion", "case_id",
                                       "target_digest", "profile", "risk",
                                       "expires_at", "nonce", "issuer",
                                       "issued_at", "binding"],
                         "attestation", verdict)
    if not verdict.ok():
        return False, verdict.blocks, detail
    if attestation["case_id"] != scope["case_id"]:
        verdict.deny("attestation.case_id does not match scope.md "
                     "(copied attestation)")
    if attestation["profile"] != scope["net_mode"]:
        verdict.deny("attestation.profile does not match scope.md "
                     "network_profile.mode")
    if attestation.get("risk") not in ("low", "medium", "high"):
        verdict.deny("attestation.risk unknown (fail closed)")
    if attestation["expires_at"] != auth["expires_at"]:
        verdict.deny("attestation.expires_at does not match auth-profile")
    if attestation["issuer"] != auth["approver"]:
        verdict.deny("attestation.issuer does not match auth-profile.approver")
    if isinstance(allowlist, list) and allowlist:
        expected_tdigest = target_digest([item.strip() for item in allowlist])
        if attestation["target_digest"] != expected_tdigest:
            verdict.deny("attestation.target_digest does not recompute from "
                         "target_allowlist (allowlist was edited after issue)")
    expected_binding = binding_digest(
        attestation["case_id"], attestation["target_digest"],
        attestation["profile"], attestation["risk"], attestation["expires_at"],
        attestation["nonce"], attestation["issuer"])
    if attestation["binding"] != expected_binding:
        verdict.deny("attestation.binding does not recompute "
                     "(copied or hand-edited attestation)")

    detail["blocks"] = len(verdict.blocks)
    return verdict.ok(), verdict.blocks, detail

def issue_attestation(case_root: Path, risk: str) -> int:
    scope, problem = read_scope(case_root)
    if scope is None:
        print(f"BLOCKED cannot issue: {problem}")
        return 20
    auth, problem = load_json(case_root / "auth-profile.json")
    if auth is None:
        print(f"BLOCKED cannot issue: {problem}")
        return 20
    try:
        allowlist = [item.strip() for item in auth["target_allowlist"]]
        tdigest = target_digest(allowlist)
        nonce = secrets.token_hex(16)
        attestation = {
            "schemaVersion": "1.0",
            "case_id": scope["case_id"],
            "target_digest": tdigest,
            "profile": scope["net_mode"],
            "risk": risk,
            "expires_at": auth["expires_at"],
            "nonce": nonce,
            "issuer": auth["approver"],
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "binding": binding_digest(scope["case_id"], tdigest,
                                      scope["net_mode"], risk,
                                      auth["expires_at"], nonce,
                                      auth["approver"]),
        }
    except (KeyError, TypeError, AttributeError) as error:
        print(f"BLOCKED cannot issue: auth-profile malformed ({error})")
        return 20
    out = case_root / "attestation.json"
    out.write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"ISSUED {out.as_posix()}")
    print(f"  case={attestation['case_id']} target_digest={tdigest[:19]}... "
          f"binding={attestation['binding'][:19]}...")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="T15 authorization gate: verify a case, or issue its "
                    "attestation. --force is accepted for compatibility and "
                    "never bypasses a hard gate.")
    parser.add_argument("--case-root", required=True,
                        help="case directory holding scope.md")
    parser.add_argument("--action", default=None,
                        help="action about to run (checked against "
                             "allowed_actions + dangerous confirmations)")
    parser.add_argument("--now", default=None,
                        help="UTC RFC 3339 override for expiry checks "
                             "(tests only)")
    parser.add_argument("--issue-attestation", action="store_true",
                        help="write attestation.json from live case facts")
    parser.add_argument("--risk", default="medium",
                        help="risk label for --issue-attestation")
    parser.add_argument("--force", action="store_true",
                        help="compatibility flag; never bypasses hard gates")
    args = parser.parse_args(argv)

    case_root = Path(args.case_root)
    if not case_root.is_dir():
        print(f"BLOCKED case root missing: {case_root}")
        return 2
    if args.now:
        try:
            now = parse_rfc3339_z(args.now)
        except ValueError:
            print(f"usage error: --now is not UTC RFC 3339: {args.now}")
            return 2
    else:
        now = datetime.now(timezone.utc)

    if args.issue_attestation:
        if args.risk not in ("low", "medium", "high"):
            print(f"usage error: unknown --risk {args.risk!r}")
            return 2
        return issue_attestation(case_root, args.risk)

    allowed, blocks, detail = verify(case_root, args.action, now)
    if allowed:
        scope_note = (f"case={detail.get('scope_case_id')} "
                      f"action={args.action or '-'}")
        print(f"ALLOW {scope_note}")
        return 0
    print(f"BLOCKED case={detail.get('scope_case_id', '?')}")
    for item in blocks:
        print(f"  - {item}")
    if args.force:
        print("  note: --force does not bypass authorization hard gates")
    return 20

if __name__ == "__main__":
    raise SystemExit(main())
