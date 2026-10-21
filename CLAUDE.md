@AGENTS.md

## Claude Code: skills setup

Skills live in `.kiro/skills/<name>/SKILL.md`. Claude Code only discovers them in
`.claude/skills/` (gitignored, local). Before starting any task, check that every
`.kiro/skills/<name>` has a matching `.claude/skills/<name>`. If any are missing,
create them without asking, as links to the `.kiro` folders (never copies):

- Linux / macOS: `mkdir -p .claude/skills && ln -sfn ../../.kiro/skills/<name> .claude/skills/<name>`
- Windows (PowerShell, no admin needed): `New-Item -ItemType Junction -Path .claude\skills\<name> -Target .kiro\skills\<name>`

Then tell the user to restart the session (or run `/reload-skills`) so the new skills load.
