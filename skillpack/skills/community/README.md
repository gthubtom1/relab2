# Community capability adapters

This directory is a namespaced compatibility layer for the four external packages
that were reviewed for the integrated `reverse-skill` distribution. The canonical
wrappers under `skills/community/` are the only top-level entry points. Imported
skills stay under their source namespace so duplicate names, relative references,
licenses, and future updates remain auditable.

## Layout after the discovery-isolation move (spec 17.27)

`skills/` is the client discovery root, so raw vendor bodies no longer live inside
it; they sit at the repository root instead:

```text
skills/community/registry.json          # the discovery manifest (manifest-only discovery)
skills/community/canonical-mapping.json
skills/community/README.md              # this file
skills/community/{ctf-hub,hack-hub,delivery,apk-extension}/SKILL.md
community-raw/{ctf-super-hub,hack-skills,ai-fullstack,apk-reverse-source}/**
```

Consequence: a client that only walks `skills/**` for `SKILL.md` finds exactly the
46 canonical skills plus those four wrappers, and nothing else. Raw bodies are
reachable only through `registry.json` (`skills[].path`, `adapted_path`). The move is
recorded in `docs/community/DISCOVERY-ISOLATION.md`, and `skills/INDEX.md` is
generated with an explicit exclusion for `community-raw/` so it can never list a raw
entry again.

Note for `scripts/adapt-community.py`: its write root must stay in sync with this
layout. Writing raw bodies back under `skills/community/<source>/` re-creates the
discovery leak -- see WORK-BOARD CR-001 / CR-002.

Use `python scripts/adapt-community.py` after changing an upstream snapshot. The
script copies skill-local support files, adds the shared reverse-skill contract, and
regenerates `registry.json`. It never installs tools or executes imported scripts.

The registry is a catalog and provenance record. It is not a second global router.
`skills/config/routing.json` selects one of the wrappers below; the wrapper then
chooses an appropriate downstream capability using the registry and the user's
scope, inputs, and desired deliverable.
