# Skill Sources

This file tracks the origin of skills under `.claude/skills/` that were copied from external sources.
Update the `Fetched` date and `Commit` (if known) whenever a skill is re-synced.

| Skill    | Source                                                | Commit | Fetched    | Notes |
|----------|-------------------------------------------------------|--------|------------|-------|
| grill-me | https://www.youtube.com/watch?v=c0kaKxM2pHg | -      | 2026-06-05 | Replaced original mattpocock version with the "capture file" variant from Nate Herk's video "The Skill That 10x'd My Claude Code Projects" (@nateherk); original mattpocock version replaced |
| handoff  | https://github.com/mattpocock/skills/tree/main/handoff  | -      | 2026-05-28 | Copied as-is from mattpocock/skills |

## Update workflow

1. Re-fetch the upstream `SKILL.md` from the source URL.
2. Diff against the local copy; merge intentional local changes.
3. Update the `Commit` (if pinning to a specific commit) and `Fetched` columns above.
4. If a skill is removed upstream or locally, delete its row.
