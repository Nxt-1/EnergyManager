# EnergyManager project instructions

These working rules apply throughout this repository, across chats and versions.
The active application is `energymanager/`. Keep these instructions concise and
maintain project requirements in the living documents below.

## Living project documents

Before substantive project work, read the architecture and deferred-work list. Read
relevant supporting documents and the latest checkpoint for the task. Reuse context
already read in this chat, but check for changes when resuming or when another chat
may have updated the workspace.

- [Architecture](energymanager/docs/ARCHITECTURE.md) is the
  single maintained architecture and implementation specification. It describes
  the current system and explicitly labelled pending changes. Update this document
  when agreed requirements, behavior, formulas or component contracts change.
- [Backlog](energymanager/docs/BACKLOG.md) is the ongoing backlog. Add
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
Local history (formerly the ignored `gpt/` tree) belongs in the external development
workspace; current requirements must remain in tracked project documents.
Historical prompts and draft restrictions do not override later
confirmed decisions or authorize new work. Explicit current user instructions take
precedence; ask about genuine unresolved policy conflicts.

## Conversation, permission and questions

- Keep chats conversational, concise and easy to follow. Answer the user's question
  directly, use plain language and keep technical detail proportional to the request.
  Do not turn a discussion into an implementation session or an unsolicited long plan.
- Keep discussions and work moving. While work remains, include the next substantive
  item, question, suggestion or concrete next action in the same response, so progress
  does not depend on an acknowledgement-only prompt. When the current task is complete,
  state that clearly.
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

## Architecture and implementation chats

- This workflow applies from the remainder of V4.5 onward. The registered release
  sections in WORK_STATE.md identify each chat pair; do not assume this setup chat
  has an architecture role or infer a new task from an older release checkpoint.
- Each release stream has an architecture chat and an implementation chat, covering
  its patch releases (for example, the 4.5 pair covers 4.5.x). Several streams may
  develop concurrently. The user creates and starts implementation chats.
- Architecture chats discuss requirements, record confirmed decisions and prepare
  implementation scope and completion criteria. Implementation chats build explicitly
  authorized tasks, choose routine coding details, verify results and record progress.
- Architecture discussion continues during implementation. Keep each authorized task's
  scope stable; later decisions become follow-up tasks or explicit user-authorized
  amendments. Agreement on a design alone does not authorize implementation.
- Use the release coordination sections in WORK_STATE.md for chat identities, task
  scope, dependencies, progress and open questions. Keep the single maintained
  architecture and decision log shared across releases; label pending behavior with
  its release/task rather than creating separate release architecture/handoff files.
- The user authorizes registered implementation/architecture pairs to message each
  other directly and trigger responses for questions and replies within their existing
  work. Record the question and resolution in the shared release record. Architecture
  may clarify existing decisions; new behavior, changed requirements or expanded scope
  require the user. Continue independent work while a decision is pending. This is
  not permission to create/start implementation chats or launch new implementation work.
- Application releases reach main in version order. Before a newer release is merged
  and published, its implementation chat incorporates the earlier releases from main,
  resolves conflicts and verifies the combined behavior. Parallel work stays on
  separate branches; a clean Git merge alone does not establish correct integration.
- Approved architecture and coordination documentation may reach main ahead of code,
  clearly distinguishing pending behavior from implemented behavior. Branches do not
  share file updates automatically: consult the latest shared records on main and
  reconcile relevant updates before acting or integrating; do not overwrite newer
  decisions or another release's progress with an older branch copy.

## Local development storage and cleanup

- Keep source, tests, reproducible fixtures, configuration templates and maintained
  documentation in Git. Store private evidence, research, run output and checkpoints
  under `ENERGYMANAGER_DEV_HOME`, defaulting to
  `$CODEX_HOME/project-data/EnergyManager` (or `~/.codex/project-data/EnergyManager`).
  Original incident evidence belongs in `evidence/`, outside disposable runs/worktrees.
- Use Codex-managed worktrees for new isolated implementation work. Consult current
  WORK_STATE.md for existing checkout locations; never recreate nested worktrees under
  repository `artifacts/`. Historical paths map through the external migration manifest.
- Use the external Python environment and explicit source path described in RUNBOOK.md.
  Put pytest temporary data, build/install output, previews and tool caches outside Git.
  E2E and benchmark tools create unique external runs by default; avoid historical
  copies of tools that still use repository-relative output paths.
- Cleanup is based on completion, not elapsed days. After successful verification and
  required publication, retain compact results and remove disposable run output. After
  a failed run, extract and retain minimal diagnostic/reproduction evidence before
  deleting temporary output. Preserve that evidence until the issue/fix is resolved
  and verified. Original installation backups/user-supplied evidence require explicit
  user permission for deletion. Active and paused work remains protected.
- Retire worktrees after their work is integrated and verified and unique ignored
  evidence is preserved. Recheck activity, Git state and resolved paths before removal;
  retain branches with unmerged commits and never follow directory links for cleanup.
- `python tools/dev_workspace.py cleanup` previews eligible owned synthetic runs.
  Record completion and retained evidence before using `cleanup --apply`. Automatic
  age-based pruning and blanket deletion of legacy artifacts are not authorized.

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
