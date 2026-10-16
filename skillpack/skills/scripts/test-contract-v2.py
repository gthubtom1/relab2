#!/usr/bin/env python3
"""T02 contract test: registry v2, profile migration, handoff schemas.

Four things are verified here:

1. a dependency-free JSON Schema subset validator (the build host has no
   ``jsonschema`` package and this repository must not depend on one);
2. the real ``skills/community/registry.json`` against the frozen 4.1/4.2/4.3
   required-field sets, enums, patterns and cross-record relations;
3. the frozen 4.6 legacy-value migration table, row by row, against real registry
   evidence recorded by T02 plus executable fixtures;
4. real handoff input/output and carrier-manifest documents against
   ``schemas/*.json``, including negative cases that must be rejected.

Every check is fail-closed: an unknown schema keyword, an unknown enum value or an
unresolvable profile is an error, never a silent pass.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "skills/community/registry.json"
PROFILE_MAP = ROOT / "skills/config/profile-map.json"
ROUTING = ROOT / "skills/config/routing.json"
SCHEMAS = ROOT / "schemas"
ROUTE = ROOT / "skills/scripts/community-route.py"

FAILURES: list[str] = []

def require(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)

# --------------------------------------------------------------------------
# 1. dependency-free draft 2020-12 subset validator
# --------------------------------------------------------------------------

SUPPORTED_KEYWORDS = {
    "type", "required", "properties", "additionalProperties", "items", "enum",
    "const", "oneOf", "minLength", "maxLength", "minimum", "maximum", "pattern",
    "minItems", "maxItems", "maxProperties",
}
ANNOTATION_KEYWORDS = {"$schema", "$id", "title", "description"}
TYPE_CHECKS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}

class UnsupportedKeyword(Exception):
    """Raised instead of silently ignoring a keyword we cannot enforce."""

def _check_keywords(schema: dict, path: str) -> None:
    for keyword in schema:
        if keyword in SUPPORTED_KEYWORDS or keyword in ANNOTATION_KEYWORDS:
            continue
        raise UnsupportedKeyword(f"{path}: unsupported schema keyword {keyword!r}")

def _validate(instance: object, schema: dict, path: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        raise UnsupportedKeyword(f"{path}: schema node is not an object")
    _check_keywords(schema, path)

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    if "oneOf" in schema:
        matched = 0
        for branch in schema["oneOf"]:
            branch_errors: list[str] = []
            _validate(instance, branch, path, branch_errors)
            if not branch_errors:
                matched += 1
        if matched != 1:
            errors.append(f"{path}: oneOf matched {matched} branches, expected exactly 1")

    if "type" in schema:
        expected = schema["type"]
        expected_list = expected if isinstance(expected, list) else [expected]
        for name in expected_list:
            if name not in TYPE_CHECKS:
                raise UnsupportedKeyword(f"{path}: unsupported type {name!r}")
        if not any(TYPE_CHECKS[name](instance) for name in expected_list):
            errors.append(f"{path}: expected type {expected!r}, got {type(instance).__name__}")
            return

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance[:60]!r} does not match pattern {schema['pattern']}")

    if isinstance(instance, bool):
        return

    if isinstance(instance, (int, float)):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                _validate(value, properties[key], f"{path}/{key}", errors)
                continue
            extra = schema.get("additionalProperties", True)
            if extra is False:
                errors.append(f"{path}: additional property {key!r} is not allowed")
            elif isinstance(extra, dict):
                _validate(value, extra, f"{path}/{key}", errors)
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errors.append(f"{path}: more than maxProperties {schema['maxProperties']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        if "items" in schema:
            for index, value in enumerate(instance):
                _validate(value, schema["items"], f"{path}/{index}", errors)

def validate(instance: object, schema: dict) -> list[str]:
    errors: list[str] = []
    _validate(instance, schema, "$", errors)
    return errors

def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))

def audit_schema_keywords(node: object, path: str) -> None:
    """Walk a whole schema document and reject any keyword outside the subset."""
    if isinstance(node, dict):
        if any(key in node for key in ("type", "properties", "required", "enum", "items", "oneOf")):
            _check_keywords(node, path)
        for key, value in node.items():
            if key in ANNOTATION_KEYWORDS:
                continue
            audit_schema_keywords(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            audit_schema_keywords(value, f"{path}/{index}")

# --------------------------------------------------------------------------
# 2. registry contract
# --------------------------------------------------------------------------

SOURCE_ENUMS = {
    "source_kind": ("community", "canonical-base", "first-party"),
    "license_status": ("verified", "review-required", "missing-license", "mixed"),
    "third_party_review": ("required", "not-required"),
    "maturity": ("verified", "partial", "unverified"),
    "distribution": ("local-only", "redistributable"),
    "adaptation_status": ("candidate", "imported", "verified", "quarantined"),
}
SKILL_ENUMS = {
    "discovery": ("manifest-only", "reference-only", "disabled"),
    "maturity": ("verified", "partial", "unverified"),
    "distribution": ("local-only", "redistributable"),
    "risk": ("low", "medium", "high"),
    "content_type": ("methodology", "workflow", "tooling", "reference"),
    "path_status": ("clean", "needs-rewrite", "broken", "quarantined"),
    "license_status": ("verified", "review-required", "missing-license", "mixed"),
}
WRAPPER_ENUMS = {"default_action": ("review", "execute"), "maturity": ("verified", "partial", "unverified")}
SOURCE_FIELDS = ("id", "source_kind", "source_url", "commit", "tree_digest", "source_manifest",
                 "snapshot_root", "source_root", "license_declared", "license_status",
                 "third_party_review", "notice_file", "maturity", "distribution",
                 "adaptation_status", "importer_version", "last_verified_at")
SKILL_FIELDS = ("id", "source", "source_path", "adapted_path", "path", "entrypoint", "discovery",
                "license_status", "maturity", "distribution", "allowed_context", "risk",
                "content_type", "keywords", "canonical_downstream", "reference_ids",
                "content_hash", "path_status")
WRAPPER_FIELDS = ("id", "path", "source", "route_ids", "reference_ids", "allowed_downstream",
                  "input_schema", "output_schema", "context_map", "default_action",
                  "auto_execute", "maturity")

def load_route_module():
    spec = importlib.util.spec_from_file_location("community_route_module", ROUTE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def sha256_of(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def check_registry(registry: dict, profile_map: dict, routing: dict) -> None:
    require(registry.get("schemaVersion") == "1.0", "registry.schemaVersion must be 1.0")
    require(isinstance(registry.get("excluded"), list), "registry.excluded must be a list")
    stats = registry.get("stats", {})
    require(stats.get("adapted_skill_count") == 293, f"adapted_skill_count must be 293, got {stats.get('adapted_skill_count')}")
    require(stats.get("excluded_framework_skill_count") == 55, f"excluded count must be 55, got {stats.get('excluded_framework_skill_count')}")
    require(stats.get("adapted_skill_count") == len(registry["skills"]), "stats.adapted_skill_count must equal len(skills)")
    require(stats.get("excluded_framework_skill_count") == len(registry["excluded"]), "stats.excluded must equal len(excluded)")
    by_kind: dict[str, int] = {}
    for _source in registry["sources"]:
        by_kind[str(_source.get("source_kind"))] = by_kind.get(str(_source.get("source_kind")), 0) + 1
    require(by_kind.get("community", 0) == 4,
            f"4 community source records expected, got {by_kind.get('community', 0)} (by_kind={by_kind})")
    require(by_kind.get("canonical-base", 0) <= 1,
            f"at most 1 canonical-base source record expected, got {by_kind.get('canonical-base', 0)} (by_kind={by_kind})")
    require(set(by_kind) <= {"community", "canonical-base"},
            f"sources[] must hold only community + canonical-base kinds, got {sorted(by_kind)}")
    require(len(registry["wrappers"]) == 4, f"4 wrapper records expected, got {len(registry['wrappers'])}")
    require(len(registry["skills"]) == 293, f"293 skill records expected, got {len(registry['skills'])}")

    canonical_skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    source_ids = [s.get("id") for s in registry["sources"]]
    require(len(set(source_ids)) == len(source_ids), "source ids must be unique")
    base_records = [s for s in registry["sources"] if s.get("source_kind") == "canonical-base"]
    require(len(base_records) == by_kind.get("canonical-base", 0),
            "canonical-base grouping must match the sources[] records")
    for base in base_records:
        bid = base.get("id", "?")
        require(bid == "reverse-skill",
                f"canonical-base record id must be reverse-skill, got {bid!r} (T21)")
        for field in ("baseline_commit", "integration_commit", "signature"):
            require(field in base,
                    f"canonical-base {bid}: missing required T21 field {field} "
                    "(schemas/canonical-base-lock.json)")
        for field in ("baseline_commit", "integration_commit"):
            require(re.fullmatch(r"[0-9a-f]{40}", str(base.get(field) or "")),
                    f"canonical-base {bid}: {field} must be 40 lowercase hex")
        require(base.get("baseline_commit") == base.get("commit"),
                f"canonical-base {bid}: baseline_commit must equal commit (T21)")
        require(base.get("commit") == (registry.get("baseline") or {}).get("commit"),
                f"canonical-base {bid}: commit must equal registry baseline.commit (T21)")
        sig = base.get("signature") or {}
        require(sig.get("status") in ("unsigned", "signed-unverified", "signed-verified"),
                f"canonical-base {bid}: signature.status outside the T21 enum")

    seen_null_sources: dict[str, list[str]] = {}
    for source in registry["sources"]:
        sid = source.get("id", "?")
        for field in SOURCE_FIELDS:
            require(field in source, f"source {sid}: missing required field {field}")
        for field, allowed in SOURCE_ENUMS.items():
            require(source.get(field) in allowed, f"source {sid}.{field}={source.get(field)!r} outside {allowed}")
        require(re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", str(source.get("id"))), f"source {sid}: id pattern")
        require(re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit"))), f"source {sid}: commit must be 40 lowercase hex")
        require(source.get("distribution") == "local-only" or (
            source.get("license_status") == "verified"
            and source.get("third_party_review") == "not-required"
            and source.get("maturity") == "verified"
            and source.get("notice_file")), f"source {sid}: redistributable admission rule violated (4.1)")
        if source.get("license_status") == "review-required":
            require(source.get("notice_file") and (ROOT / source["notice_file"]).is_file(),
                    f"source {sid}: review-required needs a real notice_file")
        if source.get("notice_file"):
            require((ROOT / source["notice_file"]).is_file(), f"source {sid}: notice_file does not exist")
        for field in ("tree_digest", "source_manifest", "snapshot_root", "importer_version"):
            if source.get(field) is None:
                seen_null_sources.setdefault(field, []).append(sid)
        if source.get("tree_digest") is not None:
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(source["tree_digest"])), f"source {sid}: tree_digest pattern")
        if source.get("last_verified_at") is not None:
            require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", str(source["last_verified_at"])),
                    f"source {sid}: last_verified_at must be UTC RFC 3339")

    skill_ids = [s.get("id") for s in registry["skills"]]
    require(len(set(skill_ids)) == len(skill_ids), "skill ids must be unique")
    paths = [s.get("path") for s in registry["skills"]]
    require(len(set(paths)) == len(paths), "skill paths must be unique")
    entrypoints = {w["path"] for w in registry["wrappers"]}
    hashes_checked = 0
    for skill in registry["skills"]:
        sid = skill.get("id", "?")
        for field in SKILL_FIELDS:
            require(field in skill, f"skill {sid}: missing required field {field}")
        for field, allowed in SKILL_ENUMS.items():
            require(skill.get(field) in allowed, f"skill {sid}.{field}={skill.get(field)!r} outside {allowed}")
        require(re.fullmatch(r"community-[a-z0-9-]+-\d{3}", str(skill.get("id"))), f"skill {sid}: id pattern")
        require(skill.get("source") in source_ids, f"skill {sid}: unknown source")
        require(skill.get("adapted_path") == skill.get("path"), f"skill {sid}: adapted_path must equal path during the transition")
        require(skill.get("entrypoint") in entrypoints, f"skill {sid}: entrypoint must be a wrapper path")
        require((ROOT / str(skill.get("path"))).is_file(), f"skill {sid}: path does not exist")
        if skill.get("path_status") == "clean":
            require((ROOT / str(skill["path"])).is_file(), f"skill {sid}: clean path_status but the file is missing")
        hashes_checked += 1
        require(skill.get("content_hash") == sha256_of(ROOT / skill["path"]), f"skill {sid}: content_hash does not match the file")
        contexts = skill.get("allowed_context")
        require(isinstance(contexts, list) and contexts, f"skill {sid}: allowed_context must be a non-empty array")
        require(len(contexts) == len(set(contexts)), f"skill {sid}: allowed_context must be de-duplicated")
        require(len(contexts) == 1, f"skill {sid}: allowed_context must resolve to exactly one profile, got {contexts}")
        for value in contexts:
            require(value in profile_map["profiles"], f"skill {sid}: allowed_context {value!r} is not a canonical profile")
        keywords = skill.get("keywords")
        require(isinstance(keywords, list) and 1 <= len(keywords) <= 32, f"skill {sid}: keywords must hold 1-32 entries")
        require(len(set(keywords)) == len(keywords), f"skill {sid}: keywords must be unique")
        require(all(isinstance(k, str) and k == k.lower() for k in keywords), f"skill {sid}: keywords must be lowercase strings")
        for downstream in skill.get("canonical_downstream", []):
            require(downstream in canonical_skills, f"skill {sid}: canonical_downstream {downstream!r} is not a canonical skill")
        for reference in skill.get("reference_ids", []):
            require(reference in skill_ids, f"skill {sid}: reference_ids {reference!r} does not exist")
        extensions = skill.get("extensions")
        if extensions is not None:
            require(isinstance(extensions, dict), f"skill {sid}: extensions must be an object")
            for key in extensions:
                require(re.fullmatch(r"[a-z][a-z0-9_]*", key), f"skill {sid}: extensions key {key!r} must be lower snake_case")
            size = len(json.dumps(extensions, ensure_ascii=False).encode("utf-8"))
            require(size <= 4096, f"skill {sid}: extensions is {size} bytes, above the 4 KiB bound")

    reference_ids = set()
    for wrapper in registry["wrappers"]:
        wid = wrapper.get("id", "?")
        for field in WRAPPER_FIELDS:
            require(field in wrapper, f"wrapper {wid}: missing required field {field}")
        for field, allowed in WRAPPER_ENUMS.items():
            require(wrapper.get(field) in allowed, f"wrapper {wid}.{field}={wrapper.get(field)!r} outside {allowed}")
        require(re.fullmatch(r"wrapper-[a-z0-9-]+", str(wrapper.get("id"))), f"wrapper {wid}: id pattern")
        require(wrapper.get("path") in entrypoints, f"wrapper {wid}: path must equal a SkillRecord.entrypoint")
        require((ROOT / str(wrapper.get("path"))).is_file(), f"wrapper {wid}: path does not exist on disk")
        require(wrapper.get("source") in source_ids, f"wrapper {wid}: unknown source")
        require(wrapper.get("auto_execute") is False, f"wrapper {wid}: auto_execute must be false")
        require(wrapper.get("input_schema") == "schemas/community-handoff-input.json", f"wrapper {wid}: input_schema")
        require(wrapper.get("output_schema") == "schemas/community-handoff-output.json", f"wrapper {wid}: output_schema")
        require(wrapper.get("input_schema") and (ROOT / wrapper["input_schema"]).is_file(), f"wrapper {wid}: input_schema file missing")
        require(wrapper.get("output_schema") and (ROOT / wrapper["output_schema"]).is_file(), f"wrapper {wid}: output_schema file missing")
        require(wrapper.get("route_ids"), f"wrapper {wid}: route_ids must be non-empty")
        for route_id in wrapper["route_ids"]:
            require(route_id in routing.get("routes", {}), f"wrapper {wid}: route {route_id!r} missing from routing.json")
        for downstream in wrapper["allowed_downstream"]:
            require(downstream in canonical_skills, f"wrapper {wid}: allowed_downstream {downstream!r} is not a canonical skill")
        for profile, mode in wrapper["context_map"].items():
            require(profile in profile_map["profiles"], f"wrapper {wid}: context_map key {profile!r} is not canonical")
            require(mode == profile_map["profiles"][profile]["network_mode"],
                    f"wrapper {wid}: context_map[{profile}] contradicts profile-map")
        for reference in wrapper["reference_ids"]:
            require(reference in skill_ids, f"wrapper {wid}: reference_ids {reference!r} does not exist")
            reference_ids.add(reference)
    require(reference_ids == set(skill_ids), "every adapted record must be reachable as a wrapper reference_id")

    # 4.0 rule 3: the registry must not carry contract-external top-level fields.
    allowed_keys = {"id", "source", "source_path", "adapted_path", "path", "entrypoint", "discovery",
                    "license_status", "maturity", "distribution", "allowed_context", "risk",
                    "content_type", "keywords", "canonical_downstream", "reference_ids",
                    "content_hash", "path_status", "extensions"}
    for skill in registry["skills"]:
        extra = set(skill) - allowed_keys
        require(not extra, f"skill {skill.get('id')}: contract-external fields {sorted(extra)} must move into extensions")
    print(f"registry: {len(registry['sources'])} sources, {len(registry['wrappers'])} wrappers, "
          f"{len(registry['skills'])} skills, {hashes_checked} content hashes recomputed")
    if seen_null_sources:
        for field, ids in sorted(seen_null_sources.items()):
            print(f"registry: {field} is null for {len(ids)} source record(s): {', '.join(ids)}")

# --------------------------------------------------------------------------
# 3. 4.6 migration table
# --------------------------------------------------------------------------

def check_profile_migration(registry: dict, profile_map: dict, contract) -> None:
    precedence = profile_map["resolution"]["precedence"]
    require(precedence == ["offline_sample", "offline_ctf", "defensive_review", "local_project",
                           "authorized_lab", "authorized_target_only"],
            "resolution.precedence must stay the frozen fail-closed order")
    require(sorted(profile_map["profiles"]) == sorted(["offline_sample", "offline_ctf", "authorized_lab",
                                                       "authorized_target_only", "defensive_review",
                                                       "local_project"]),
            "profile map must define exactly the six canonical profiles of 4.6")
    require(set(precedence) == set(profile_map["profiles"]), "precedence must cover every canonical profile")
    for profile, spec in profile_map["profiles"].items():
        require(spec["network_mode"] in profile_map["network_modes"],
                f"profile {profile}: network_mode must be one of the frozen network modes")

    legacy_by_id: dict[str, list[str]] = {}
    for skill in registry["skills"]:
        legacy_by_id[skill["id"]] = (skill.get("extensions") or {}).get("legacy_allowed_context", [])

    rows = profile_map["migration_evidence"]["rows"]
    require(len(rows) >= 18, "the migration table must record every row of the frozen 4.6 table")
    for row in rows:
        legacy = row["legacy"]
        evidence = row["evidence"]
        if evidence == "registry":
            counted = sum(1 for values in legacy_by_id.values() if legacy in values)
            require(counted == row["legacy_records"],
                    f"4.6 row {legacy!r}: recorded {row['legacy_records']} records, recomputed {counted}")
            sample = row["sample_record_id"]
            require(sample in legacy_by_id, f"4.6 row {legacy!r}: sample record {sample!r} does not exist")
            require(legacy in legacy_by_id[sample],
                    f"4.6 row {legacy!r}: sample record {sample!r} did not carry that legacy value")
            if row["canonical"] in profile_map["profiles"]:
                actual = next(s["allowed_context"] for s in registry["skills"] if s["id"] == sample)
                require(profile_map["resolution"]["precedence"].index(actual[0]) <=
                        profile_map["resolution"]["precedence"].index(row["canonical"]),
                        f"4.6 row {legacy!r}: sample {sample} resolved to {actual}, wider than {row['canonical']}")
        else:
            resolved, review, unknown = contract.resolve_profiles([legacy])
            if row.get("status") == "needs_review":
                require(not resolved and review and not unknown,
                        f"4.6 row {legacy!r}: must stay needs_review as a listed-but-unsupported value")
            elif row["canonical"] == "offline_sample_or_needs_review":
                with_sample, review_yes, unknown_yes = contract.resolve_profiles([legacy], sample_present=True)
                require(with_sample == ["offline_sample"] and not review_yes and not unknown_yes,
                        f"4.6 row {legacy!r}: with a sample it must resolve to offline_sample")
                without, review_no, unknown_no = contract.resolve_profiles([legacy], sample_present=False)
                require(not without and review_no and not unknown_no,
                        f"4.6 row {legacy!r}: without a sample it must stay needs_review")
            else:
                require(resolved == [row["canonical"]] and not review and not unknown,
                        f"4.6 row {legacy!r}: fixture resolved to {resolved}, expected [{row['canonical']!r}]")

    require(contract.resolve_profiles(["not-in-the-table"])[2] == ["not-in-the-table"],
            "unlisted legacy values must be reported as unknown, never guessed")
    require(registry["stats"]["adapted_skill_count"] == 293, "migration must not change the record count")

    distribution = {}
    for skill in registry["skills"]:
        distribution[skill["allowed_context"][0]] = distribution.get(skill["allowed_context"][0], 0) + 1
    require(distribution == profile_map["record_result"],
            f"record_result in the profile map must match the registry: {distribution}")
    print(f"4.6 migration: {len(rows)} table rows verified against registry evidence and fixtures; "
          f"result {distribution}")

# --------------------------------------------------------------------------
# 4. handoff documents against the schemas
# --------------------------------------------------------------------------

def build_input_sample(registry: dict, route_payload: dict) -> dict:
    wrapper = next(w for w in registry["wrappers"] if w["id"] == route_payload["matches"][0]["id"])
    return {
        "schemaVersion": "1.0",
        "route_id": wrapper["route_ids"][0],
        "wrapper_id": wrapper["id"],
        "hint": "JWT authentication",
        "project_root": "D:/Project/skills-hub/integrated-skill-hub",
        "case_root": "D:/Project/skills-hub/integrated-skill-hub/work/t02-handoff-fixture",
        "intent": "audit",
        "target": {"kind": "repo", "value": "D:/Project/skills-hub/integrated-skill-hub",
                   "digest": sha256_of(REGISTRY)},
        "auth": {
            "auth_source": "scope_file",
            "approver": "T02 fixture",
            "issued_at": "2026-09-29T13:00:00Z",
            "expires_at": "2026-09-29T23:00:00Z",
            "target_allowlist": ["D:/Project/skills-hub/integrated-skill-hub"],
            "allowed_actions": ["read_only", "static_analysis"],
            "evidence_reference": "work/t02-handoff-fixture/scope.md",
            "revocation_status": "active",
        },
        "profile": "defensive_review",
        "execution_profile": {
            "filesystem_allowlist": ["D:/Project/skills-hub/integrated-skill-hub"],
            "network_egress_allowlist": [],
            "credential_policy": "none",
            "max_runtime": 600,
            "max_retries": 1,
            "max_requests": 0,
            "max_artifact_size": 10485760,
            "requires_human_confirmation": False,
        },
        "in_scope": ["skills/community/**", "community-raw/**", "schemas/**"],
        "out_of_scope": ["any live target"],
        "requested_downstream": ["api-security"],
        "tool_requirements": ["python3"],
        "provenance": {
            "source_commit": registry["baseline"]["commit"],
            "registry_digest": sha256_of(REGISTRY),
            "input_digest": sha256_of(REGISTRY),
        },
        "extensions": {"fixture": "t02"},
    }

def build_output_sample(route_payload: dict, registry: dict, contract) -> dict:
    match = route_payload["matches"][0]
    reference = next(s for s in registry["skills"] if s["id"] == match["references"][0]["id"])
    return {
        "schemaVersion": "1.0",
        "status": route_payload["status"],
        "wrapper_id": match["id"],
        "downstream_skill": None,
        "case_root": "D:/Project/skills-hub/integrated-skill-hub/work/t02-handoff-fixture",
        "next_safe_steps": [
            {"action_id": "read_reference", "kind": "read_file",
             "description": "read the matched reference as untrusted data",
             "target": reference["path"], "params": {"max_bytes": 65536},
             "requires_confirmation": False},
            {"action_id": "record_evidence", "kind": "record_evidence",
             "description": "record the reference digest under the case evidence folder",
             "target": "work/t02-handoff-fixture/evidence",
             "params": {"digest": reference["content_hash"]},
             "requires_confirmation": False},
        ],
        "evidence_ids": ["E-t02-001"],
        "artifact_ids": [],
        "failure_reason": None,
        "limitations": ["community bodies are untrusted reference data"],
        "license_notice": f"{reference['license_status']} - see {registry['sources'][0]['notice_file']}",
        "route_explanation": route_payload["route_explanation"],
        "source_commit": registry["baseline"]["commit"],
        "registry_digest": route_payload["registry_digest"],
        "untrusted_content": [
            {"record_id": reference["id"], "path": reference["path"],
             "digest": reference["content_hash"], "trust": "untrusted"}
        ],
        "extensions": {"fixture": "t02"},
    }

def check_handoff_output_semantics(document: dict, canonical_skills: set[str]) -> list[str]:
    """Cross-field rules of 4.5/4.7 that the schema subset cannot express."""
    problems: list[str] = []
    status = document.get("status")
    reason = document.get("failure_reason")
    if status in {"failed", "blocked"}:
        if reason is None:
            problems.append("failure_reason is required when status is failed/blocked")
    elif reason is not None:
        problems.append("failure_reason must be null unless status is failed/blocked")
    downstream = document.get("downstream_skill")
    if downstream is not None and downstream not in canonical_skills:
        problems.append(f"downstream_skill {downstream!r} is not a canonical skill")
    if not document.get("license_notice") and document.get("license_status") != "verified":
        problems.append("license_notice must not be empty unless every loaded record is verified")
    for step in document.get("next_safe_steps", []):
        if not isinstance(step, dict):
            problems.append("next_safe_steps entries must be typed action objects, never bare text")
            continue
        if step.get("kind") == "run_allowlisted_command" and "command_id" not in (step.get("params") or {}):
            problems.append("run_allowlisted_command requires params.command_id from the canonical allowlist")
        description = step.get("description", "")
        if re.search(r"(&&|\|\||;\s*\w|^\s*\$|rm -rf|curl\s+http)", description):
            problems.append(f"action {step.get('action_id')!r} looks like a free-text command, not a typed action")
    return problems

def check_carrier_manifest(registry: dict) -> dict:
    def member(relative: str) -> dict:
        path = ROOT / relative
        return {"path": relative, "kind": "file", "sha256": sha256_of(path), "size_bytes": path.stat().st_size}

    return {
        "schemaVersion": "1.0",
        "carrier_id": "t02-dev-checkout",
        "carrier_kind": "dev_checkout",
        "created_at": "2026-09-29T13:00:00Z",
        "generator": "skills/scripts/test-contract-v2.py",
        "generator_version": "1.0.0",
        "bundle_root": ".",
        "no_git": True,
        "platforms": ["windows"],
        "members": [
            member("skills/community/registry.json"),
            member("schemas/community-handoff-input.json"),
            member("schemas/community-handoff-output.json"),
            member("schemas/carrier-manifest.json"),
            member("skills/config/profile-map.json"),
            {"path": "skills/community", "kind": "directory"},
        ],
        "required_members": ["registry.json", "schemas/"],
        "digests": {
            "registry": sha256_of(REGISTRY),
            "schemas": "sha256:" + hashlib.sha256(b"".join(
                (SCHEMAS / name).read_bytes() for name in sorted(
                    ["community-handoff-input.json", "community-handoff-output.json", "carrier-manifest.json"]))).hexdigest(),
            "notice": None,
            "checksums_manifest": None,
            "source_lock": None,
        },
        "release": {"mode": "local_only", "redistributable": False, "signatures": []},
        "fixtures": [
            {
                "fixture_id": "community-route-jwt",
                "cwd": ".",
                "runtime": "python 3.12",
                "dependencies": ["stdlib only"],
                "inputs": ["skills/community/registry.json"],
                "expected_status": "matched",
                "expected_exit_code": 0,
                "expected_stdout_contains": ["wrapper-only"],
                "expected_json": {"/matches/0/access": "wrapper-only"},
            },
            {
                "fixture_id": "contract-v2",
                "cwd": ".",
                "runtime": "python 3.12",
                "dependencies": ["stdlib only"],
                "inputs": ["schemas/community-handoff-input.json"],
                "expected_status": "matched",
                "expected_exit_code": 0,
            },
        ],
        "extensions": {"fixture": "t02"},
    }

def check_schemas(registry: dict, route_payload: dict, contract) -> None:
    input_schema = load_schema("community-handoff-input.json")
    output_schema = load_schema("community-handoff-output.json")
    carrier_schema = load_schema("carrier-manifest.json")
    for name, schema in (("input", input_schema), ("output", output_schema), ("carrier", carrier_schema)):
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
                f"{name} schema must declare draft 2020-12")
        audit_schema_keywords(schema, name)
    require(input_schema["properties"]["hint"]["minLength"] == 1 and input_schema["properties"]["hint"]["maxLength"] == 4096,
            "handoff input hint must be bounded 1-4096 (4.4)")
    require(input_schema["additionalProperties"] is False, "handoff input must be additionalProperties: false")
    require(output_schema["additionalProperties"] is False, "handoff output must be additionalProperties: false")
    require("network_profile" not in input_schema["properties"],
            "network_profile must not be an input property (4.4/17.22)")
    require(set(input_schema["properties"]["profile"]["enum"]) == set(profile_map_profiles(contract)),
            "handoff input profile enum must match the canonical profiles of 4.6")
    require(set(output_schema["properties"]["status"]["enum"]) ==
            {"matched", "needs_review", "blocked", "missing_input", "unavailable", "failed"},
            "handoff output status enum must match 4.7")

    canonical_skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}

    input_sample = build_input_sample(registry, route_payload)
    errors = validate(input_sample, input_schema)
    require(not errors, f"real handoff input sample must validate: {errors}")

    output_sample = build_output_sample(route_payload, registry, contract)
    errors = validate(output_sample, output_schema)
    require(not errors, f"real handoff output sample must validate: {errors}")
    require(not check_handoff_output_semantics(output_sample, canonical_skills),
            f"handoff output semantic rules: {check_handoff_output_semantics(output_sample, canonical_skills)}")

    carrier_sample = check_carrier_manifest(registry)
    errors = validate(carrier_sample, carrier_schema)
    require(not errors, f"carrier manifest sample must validate: {errors}")

    # negative: an extra property (the frozen contract removed network_profile)
    bad = dict(input_sample, network_profile="lab_only")
    require(validate(bad, input_schema), "an input carrying network_profile must be rejected")
    # negative: unknown enum
    bad = dict(input_sample, profile="authorized_lab_typo")
    require(validate(bad, input_schema), "an unknown profile enum must be rejected")
    # negative: missing auth member (17.4 requires all eight)
    bad = json.loads(json.dumps(input_sample))
    del bad["auth"]["revocation_status"]
    require(validate(bad, input_schema), "auth without revocation_status must be rejected")
    # negative: hint above the frozen bound
    bad = dict(input_sample, hint="x" * 4097)
    require(validate(bad, input_schema), "hint longer than 4096 must be rejected")
    # negative: empty in_scope
    bad = dict(input_sample, in_scope=[])
    require(validate(bad, input_schema), "empty in_scope must be rejected")
    # negative: uppercase-case identifier drift
    bad = dict(input_sample, wrapper_id="Wrapper-Hack-Skills")
    require(validate(bad, input_schema), "wrapper_id case drift must be rejected")

    # negative: free-text command instead of a typed action
    bad = json.loads(json.dumps(output_sample))
    bad["next_safe_steps"] = ["rm -rf / --no-preserve-root"]
    require(validate(bad, output_schema), "free-text next_safe_steps must be rejected")
    # negative: failure_reason set while status is matched (4.5/4.7 cross-field rule)
    bad = json.loads(json.dumps(output_sample))
    bad["failure_reason"] = "timeout"
    require(check_handoff_output_semantics(bad, canonical_skills), "failure_reason outside failed/blocked must be rejected")
    # negative: downstream that is not a canonical skill
    bad = json.loads(json.dumps(output_sample))
    bad["downstream_skill"] = "not-a-canonical-skill"
    require(check_handoff_output_semantics(bad, canonical_skills), "unknown downstream_skill must be rejected")
    # negative: unknown status
    bad = json.loads(json.dumps(output_sample))
    bad["status"] = "tool_unavailable"
    require(validate(bad, output_schema), "tool_unavailable must not become a second status (4.7)")

    # negative: carrier member without a digest, and a required-member typo
    bad = json.loads(json.dumps(carrier_sample))
    bad["members"][0].pop("sha256")
    require(not validate(bad, carrier_schema),
            "documented subset gap: the carrier schema cannot require sha256 per file member, "
            "so the per-member digest rule must stay in the contract test and in T23")
    bad = json.loads(json.dumps(carrier_sample))
    bad["required_members"] = ["registry.json", "schemas"]
    require(validate(bad, carrier_schema), "a bad required_members value must be rejected")

    # the validator must refuse to ignore a keyword it cannot enforce
    try:
        validate({"x": "1"}, {"type": "object", "format": "date-time"})
    except UnsupportedKeyword:
        pass  # scan-ok: 这是**断言**本身——异常必须抛；真抛了才走这里，不抛则由下面的 else 记 FAILURES
    else:
        FAILURES.append("the validator must raise on an unsupported keyword instead of ignoring it")

    print("schemas: 3 documents loaded, sample and negative documents validated")

def profile_map_profiles(contract) -> list[str]:
    return list(contract.canonical_profiles)

def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    profile_map = json.loads(PROFILE_MAP.read_text(encoding="utf-8"))
    routing = json.loads(ROUTING.read_text(encoding="utf-8"))
    module = load_route_module()
    contract = module.load_contract()
    route_payload = module.lookup("JWT authentication", "hack-skills")

    check_registry(registry, profile_map, routing)
    check_profile_migration(registry, profile_map, contract)
    check_schemas(registry, route_payload, contract)

    try:
        import jsonschema  # noqa: F401
    except ImportError:
        print("validator: dependency-free subset validator in use (jsonschema is not installed)")
    else:
        print("validator: NOTE jsonschema is installed on this host; the bundled subset validator is still the tested one")

    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL {failure}")
        print(f"CONTRACT V2 FAILED ({len(FAILURES)} failures)")
        return 1
    print("CONTRACT V2 PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
