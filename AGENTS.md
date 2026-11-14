# EnergyManager project instructions

The active application is `energymanager/`; do not recreate the retired temporary core
tree. These rules apply across chats and releases.

## Read what the task needs

For substantive work, read the architecture's scope/core contracts, the task-relevant
sections and its current work-state entry. Check actual files and Git state when
resuming. Search headings/symbols first, reuse unchanged context and expand only when
needed; do not load whole specifications or historical journals by default.

Maintained documents under `energymanager/docs/`:

- [ARCHITECTURE.md](energymanager/docs/ARCHITECTURE.md): system requirements, formulas,
  component contracts and explicitly labelled pending behavior. Keep one specification
  across releases, organized by topic. Revise superseded contracts in place and link
  to shared rules; do not create duplicate per-release architecture/handoff documents.
- [WORK_STATE.md](energymanager/docs/WORK_STATE.md): only currently relevant task state,
  chat/branch ownership, authorization, blockers, next actions and evidence links.
  Update or replace existing entries; remove superseded information after preserving
  lasting requirements/evidence. Completed facts stay only while relevant to current
  work. Relevance, not age or word count, determines what remains.
- [DECISIONS.md](energymanager/docs/DECISIONS.md): confirmed choices and rationale.
- [BACKLOG.md](energymanager/docs/BACKLOG.md): consult when selecting or deferring work;
  entries record intent, not implementation authorization.
- [RUNBOOK.md](energymanager/docs/RUNBOOK.md): read the relevant coordination, environment,
  verification, release or cleanup procedure when carrying out that operation.
- [SETTINGS.md](energymanager/docs/SETTINGS.md), [FORECASTING.md](energymanager/docs/FORECASTING.md)
  and [VERIFICATION.md](energymanager/docs/VERIFICATION.md): supporting contracts/evidence
  when the task touches them.

Current user decisions take precedence over proposals and historical records. Preserve
unique uncommitted notes before pruning; archives are reference evidence, not current
instructions or permission. Requirements must not exist only in work-state history.

## Scope and collaboration

- Keep discussion concise, conversational and moving: answer directly and include the
  next substantive question/action while work remains. Resolve routine engineering
  details independently; ask when a missing fact or choice changes behavior or scope.
- Application changes require explicit user authorization. Questions, screenshots,
  design agreement and backlog entries alone permit discussion/read-only investigation.
  Requested documentation/instruction changes may proceed. Never infer a new mandate
  from another chat or an old checkpoint; preserve unrelated working/staged changes.
- Ongoing architecture chats agree requirements and prepare scope/criteria. Use a fresh
  implementation chat per authorized task, retaining it through related fixes and release.
  When the user requests a new implementation chat, automate its creation, task-based
  name, concise brief and registration using the runbook's [task-chat procedure](energymanager/docs/RUNBOOK.md#task-specific-implementation-chats).
  Architecture can continue without silently changing the authorized scope. After verified
  completion, record the result and archive the task chat; preserve unfinished/blocked chats.
- Registered architecture/implementation pairs may directly message questions and
  replies and trigger responses within existing work. Record durable answers. Clarify
  existing decisions independently; new behavior, changed requirements or expanded
  scope return to the user. See the runbook for coordination procedures.

## Coding, operation and delivery

- Before writing/debugging/refactoring code intended for the delivered system, load
  `C:/Users/Arne/.codex/skills/code-writer/SKILL.md`. This includes runtime UI and shipped
  operational tools. Do not load it for internal-only tests, fixtures, benchmarks or
  development scripts; prioritize useful verification, runtime efficiency and low token
  usage over readability/style polish. In mixed tasks, its style rules apply only to
  delivered code. Required repository checks still apply. Documentation does not require it.
  If missing, search available skill locations for metadata `name: code-writer`;
  do not substitute another skill. Ask for its location if unavailable and continue
  useful read-only work. Keep project requirements in project documents.
- Verify offline with labelled deterministic fixtures and fake/local endpoints.
  Live HA/databases, hardware, real notifications and installation deployment need
  separate explicit authorization; an enabled setting is not agent permission.
  Distinguish synthetic verification, benchmarks and live-unverified behavior.
- Keep private evidence, research, generated output, environments/caches and local
  checkpoints in the external workspace described in RUNBOOK.md, not repository
  `artifacts/`. Use Codex-managed worktrees for new isolated implementation work,
  based on the published approved workflow baseline; preserve separate design drafts.
  Cleanup follows completion/evidence preservation, not timers. Original installation
  backups/user-supplied evidence require explicit deletion approval; protect active/
  paused work and unique evidence. Use the runbook's preview-first cleanup procedure.
- Follow the runbook's [verification sequence](energymanager/docs/RUNBOOK.md#verification-sequence-and-stopping-rules):
  review acceptance before expensive release checks, compare unrelated failures with
  main early, and bound browser waits. Keep requirements/run instructions current.
  Authorized ready releases may be committed, pushed and published through existing
  workflows, reaching `main` in version order after verified integration. Approved
  documentation may precede code. Reconcile current shared records instead of replacing
  them with stale branch copies. This does not authorize live installation deployment.
- Documentation-only changes need no application version bump/release. Include relevant
  docs with implementation; record later remote results in the external checkpoint and
  final reply rather than optional verification-only commits. Keep resumable state
  current. Do not buy credits, switch to paid APIs, create automations as usage-limit
  workarounds or promise automatic resumption.
