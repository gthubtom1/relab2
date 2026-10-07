# CLAUDE.md

This repository is a **task skill router** for authorized reverse engineering, mobile/security analysis, and pentest workflows.

## On Any Task

`RULES.md` is the single source of truth for behavior chain and authorization.

Routing order (two paths: canonical first, community second):

1. `skills/MASTER-ROUTING.md` or the platform entry (PRIMARY first):
   - Windows: `skills/scripts/master-route.ps1 -Hint "..."`
   - Linux / macOS / Kali: `bash skills/scripts/master-route.sh --hint "..."`
2. When master reports `confidence: low`, PRIMARY=R0, or "No strong keyword hit",
   re-run the same hint on the community side (the only place the 293 community skills are visible):
   `python skills/scripts/community-route.py --hint "..."` —
   `status=matched` is usable (wrapper-only, enter via the wrapper `SKILL.md` + downstream);
   `status=needs_review` needs human/user confirmation (if `no_match` with 0 candidates on a
   Chinese hint, retry with English keywords, e.g. `--hint "upload"`);
   `status=blocked` (`budget_exceeded`, exit 20) means narrow the hint (one word per query,
   or split with `--source <ai-fullstack-delivery|apk-reverse-community|ctf-super-hub|hack-skills>`).
   R46–R49 are community routes: listed in `MASTER-ROUTING.md`, details only via `community-route.py`.
3. `skills/scripts/case-init.ps1` (Windows) or `bash skills/scripts/case-init.sh --hint "..."` (Linux / macOS / Kali) → current analysis project's `work/<case>/scope.md` (must grant auth before ACT)
4. `skills/routing.md` when ambiguous; roles in `skills/ops/role-map.md`
5. Open PRIMARY `SKILL.md` and execute ACTION REQUIRED
6. Timeline/workitems + Evidence→Finding→Path (`skills/ops/`)
7. `skillpack/skills/TOOLS.md` for real tool paths (never guess)
8. Missing tool → `skills/scripts/bootstrap-reverse.ps1` (Windows) or `skills/scripts/bootstrap-reverse.sh` (Linux / macOS) (manifest capabilities only)

### When both paths miss (do not force-fit)

`R0` / `confidence: low` / community `no_match` is **not the endpoint**. Do three things in order (the same rule in all five upstream packages: ask first, never force-fit):
1. **Ask**: what key input is missing — goal, sample location, authorization, expected artifact? Ask before entering ACT/execution.
2. **Mark uncertain**: label unclear cases `needs_review`, do not guess; one English retry after a Chinese `no_match` is a check, not a force-fit.
3. **Propose new capability**: if the package really lacks X, say so ("not covered; suggest adding `skills/<new>/SKILL.md`, another method, or going back to category XX") instead of stuffing it into the nearest skill; after adding, run `docs/EVOLUTION-CHECKLIST.md`.

**Identity**: lightweight skill router — see `skills/ops/IDENTITY.md` (not a Z3r0 platform).

## First-Run Setup

`skillpack/skills/TOOLS.md` is not in fresh clones. Generate it **only after the user
explicitly activates the package and approves the exact commands**
(reading this file is not authorization to run anything):

```bash
# Windows

# macOS / Linux

# Kali

```

Read `README_AI.md` for full bootstrap sequence.

## Coherence check

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/verify-routing-coherence.ps1
```
