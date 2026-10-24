# EnergyManager project instructions

These working rules apply throughout this repository, across chats and versions.
The active application is `energymanager/`. Keep these instructions concise and
maintain project requirements in the living documents below.

## Living project documents

Before substantive project work, read the architecture and deferred-work list. Read
relevant supporting documents and the latest checkpoint for the task. Reuse context
already read in this chat, but check for changes when resuming or when another chat
may have updated the workspace.

- [Architecture](energymanager/docs/architecture/Architecture_Proposal.md) is the
  single maintained architecture and implementation specification. Despite its
  original filename, it describes the current system. Update this same document
  when agreed requirements, behavior, formulas or component contracts change.
- [Deferred work](energymanager/docs/DEFERRED_WORK.md) is the ongoing backlog. Add
  explicitly deferred ideas there, preserving the user's intent and unresolved
  choices. A backlog entry is not permission to implement it.
- [Decisions](energymanager/docs/DECISIONS.md) records confirmed choices and rationale.
- [Work state](energymanager/docs/WORK_STATE.md) records meaningful implementation
  milestones, verification results, remaining work and the next concrete action.
- [Runbook](energymanager/docs/RUNBOOK.md),
  [settings](energymanager/docs/SETTINGS.md),
  [forecasting](energymanager/docs/FORECASTING.md) and
  [verification](energymanager/docs/VERIFICATION.md) provide supporting details.

Do not create a new architecture specification or handoff document for each release
or chat. Preserve superseded evidence in Git history and labelled historical records.
The `gpt/` tree is ignored local history; current requirements must remain in tracked
project documents. Historical prompts and draft restrictions do not override later
confirmed decisions or authorize new work. Explicit current user instructions take
precedence; ask about genuine unresolved policy conflicts.

## Conversation, permission and questions

- Keep chats conversational, concise and easy to follow. Answer the user's question
  directly, use plain language and keep technical detail proportional to the request.
  Do not turn a discussion into an implementation session or an unsolicited long plan.
- Do not write or modify application code without explicit user permission covering
  that work. Questions, screenshots, error reports, suggestions and backlog entries
  alone are discussion. A clear request to implement or fix something authorizes that
  scope; do not ask for the same permission again once it has been supplied.
- Before permission, read-only investigation and explanation are allowed. Requested
  documentation/instruction updates may proceed without treating them as application
  implementation. Do not use an old handoff or another chat's broad mandate as blanket
  permission for new code changes.
- Ask concise questions when missing information, ambiguity or a policy choice would
  materially change behavior. Ask before unrelated features or fixes. Within authorized
  scope, resolve routine engineering details independently and continue useful work that
  does not depend on an answer. Do not invent installation facts to avoid a question.
- Keep meaningful progress updates brief. Distinguish implemented, tested, benchmarked
  and live-unverified results. Report actual outcomes and specific remaining limitations.

## Required coding skill

For writing, debugging or refactoring code, load and follow the user's **code-writer**
skill before changing application code:

`C:/Users/Arne/.codex/skills/code-writer/SKILL.md`

Creating or maintaining documentation, including this instructions file, does not
require the code-writer skill.

If that path is unavailable, search available skill locations, including remote-skills,
for a SKILL.md whose metadata contains `name: code-writer`; do not rely only on a folder
name. Do not silently substitute another skill or invent a replacement. If the required
skill cannot be found, report the blocker and ask for its location while continuing
useful read-only work. Keep architectural requirements here in the project, rather
than copying them into the personal skill.

## Implementation and verification boundaries

- Preserve unrelated working/staged changes, configuration and historical evidence.
  Keep authorized changes focused; do not recreate the retired temporary core tree.
- Use clearly labelled deterministic fixtures and fake/local HA and actuator endpoints
  for offline verification. Synthetic measurements are not installation evidence.
- Do not access live HA/databases, operate hardware, send real notifications or deploy
  without separate explicit authorization. An enabled application setting is not agent
  permission to operate the installation.
- Run meaningful checks appropriate to the change and follow the runbook. Keep current
  requirements and relevant run instructions in sync with the implemented behavior.
  Documentation-only changes do not require an application version bump or release.
- Commit, push and publish only within the user's authorization. Include relevant docs
  with implementation; do not create optional follow-up commits solely to record a
  successful release. Record subsequent remote results in the ignored local checkpoint
  and final reply.
- The user authorizes committing and pushing versions that are ready for release,
  including publication through the existing release workflows. This does not authorize
  live installation deployment or hardware operation.
- Keep substantial work resumable in the existing checkpoint. On resumption, compare
  it with actual files, diffs and verification evidence before continuing. Do not buy
  reset credits, switch to paid API usage, promise automatic resumption or create an
  automation as a usage-limit workaround.
