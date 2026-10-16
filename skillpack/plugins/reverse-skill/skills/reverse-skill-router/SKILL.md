---
name: reverse-skill-router
description: Use the reverse-skill repository from Codex for authorized reverse engineering, security analysis, CTF, and defensive testing tasks. Requires the reverse-skill repository to be available as the current workspace or an explicitly supplied local path.
---

# Reverse Skill Codex adapter

This plugin is an optional Codex entry point. The repository remains the canonical, client-neutral implementation.

When the current workspace is the `reverse-skill` repository:

1. Read `RULES.md` at the repository root.
2. Run the platform-native `skills/scripts/master-route` entry with the user's task to select the PRIMARY skill from `skills/config/routing.json`.
3. Before any target action, create and validate `work/<case>/scope.md` with the platform-native `case-init` and `case-guard` scripts.
4. Open the selected PRIMARY (`primary_skill` in `route-scope.md`; it may be a `references/**.md`, not only a `SKILL.md`) and follow its instructions.
5. Resolve tools only through the generated `skillpack/skills/TOOLS.md`; do not register MCP servers or install tools unless the user requested that action.

If the repository is not the current workspace and no local repository path was supplied, explain that this adapter does not bundle a second copy of the router. Ask the user for **this package's local path**, or — if it still has to be fetched — ask for **the repository address the user hosts this package at**, show the exact `git clone` command, and obtain approval before running it. Do not choose a remote yourself and do not fetch a third-party repository. Then continue from that checkout's `RULES.md`.

Do not treat the presence of this plugin, a target name, or a sample path as authorization. Authorization comes from the repository's scope contract.
