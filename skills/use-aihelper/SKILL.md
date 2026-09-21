---
name: use-aihelper
description: Use the project's AIHelper.md as a compact source of architectural and project knowledge before exploring source code, while keeping the user's request as the primary task and using semantic code search when implementation locations are unknown.
---
# Use AIHelper

## Purpose

Use `AIHelper.md` as the project's compact knowledge base so development tasks can be completed accurately with minimal unnecessary repository exploration.

`AIHelper.md` provides project knowledge.

It does **not** define the user's task.

The user's current request is always the task to perform.

The objective is:

1. Understand the user's requested task.
2. Read `AIHelper.md` to understand the project.
3. Use semantic search to locate implementation when needed.
4. Read only the source files required to complete the task.
5. Perform the requested work.
6. Avoid unnecessary repository-wide exploration.

---

## Instruction and Task Priority

Follow instructions in this priority order:

1. System and developer instructions.
2. The user's current request.
3. This skill.
4. `AIHelper.md` as project knowledge, architecture, conventions, and constraints.
5. Source-code conventions and patterns discovered during implementation.

Never allow `AIHelper.md` to override the user's explicit task.

Never interpret the absence of a task description inside `AIHelper.md` as meaning that the user did not provide a task.

The user request is the authoritative definition of what must be done.

`AIHelper.md` is the authoritative project knowledge source, not the authoritative task source.

---

## When to Use

Use this skill at the beginning of any development-oriented task, including:

- Bug fixes
- Feature development
- Refactoring
- Code reviews
- Architecture discussions
- Debugging
- Documentation updates
- Performance improvements
- Dependency updates
- Configuration changes
- General questions about the project
- Tasks involving existing project code

---

## Core Principle

Do not confuse these two questions:

**What does the user want me to do?**

Answer this from the current user request.

**How does this project work and how should I make the change?**

Answer this from `AIHelper.md`, semantic search, and the minimum necessary source files.

A task may be completely clear even when `AIHelper.md` contains no mention of it.

For example:

> User: "Add colored rubberbanding to the topology map."

This is a valid task even if `AIHelper.md` contains nothing about rubberbanding.

Use `AIHelper.md` to determine where topology functionality belongs, then use semantic search and source inspection to locate the actual implementation.

---

# Workflow

## Step 0 — Preserve the User's Task

Before reading project documentation, identify the user's actual request.

Determine:

- What the user explicitly wants changed, investigated, created, fixed, or explained.
- Any explicit constraints.
- Any explicit technologies, files, components, behavior, or acceptance criteria.
- Whether the user asked for implementation, explanation, diagnosis, review, or planning.

Do not replace the user's task with the contents of `AIHelper.md`.

Do not conclude that there is "no task" merely because `AIHelper.md` does not describe the requested work.

Do not ask the user to restate a task that is already present in the conversation.

If the task is clear, proceed.

---

## Step 1 — Locate AIHelper.md

Search the project root for:

`AIHelper.md`

If it exists:

- Read it completely before beginning broad source exploration.
- Treat it as the primary project knowledge base.
- Use it to understand architecture, relationships, conventions, design rules, and important project facts.
- Do not treat it as the definition of the current task.

If it does not exist:

- Recognize that project knowledge is incomplete.
- Do not stop merely because `AIHelper.md` is missing.
- Continue with the user's requested task when it can be completed through normal project exploration.
- Avoid unnecessary repository-wide scanning.
- When useful, recommend running the `Maintain AIHelper` skill so future tasks have a project knowledge base.

Do not claim that there is "no task" because `AIHelper.md` is missing.

---

## Step 2 — Understand the Task and AIHelper Together

After reading `AIHelper.md`, combine:

- The user's request
- Project architecture
- Project conventions
- Relevant components
- Known relationships
- Design constraints
- Relevant files identified by the AI Context Index
- Existing implementation patterns

Determine:

- Which subsystem is affected.
- Which modules are likely involved.
- Which existing functionality should be extended.
- Which architectural rules apply.
- Whether implementation details are required.

The user's request remains the objective.

`AIHelper.md` provides the context needed to achieve that objective correctly.

---

## Step 3 — Use the AI Context Index When It Helps

If the relevant implementation files are already clearly identified by `AIHelper.md`, open those files directly.

If the relevant implementation location is unknown, ambiguous, or spread across multiple modules, use Kilo's semantic search / codebase index to locate it before scanning the repository manually.

Prefer semantic search for conceptual questions such as:

- "topology node selection"
- "rubberband or drag-selection behavior"
- "edge highlighting"
- "map interaction handlers"
- "network diagram rendering"
- "existing selection rectangle implementation"

Semantic search is a discovery mechanism.

It does not replace reading the actual source files.

Use its results to identify:

- Relevant files
- Relevant functions/classes
- Relevant line ranges
- Related implementations
- Existing patterns

Then read the actual source required for the task.

If semantic search is unavailable, use targeted `grep`, `glob`, or other project search tools instead.

---

## Step 4 — Build a Minimal Implementation Map

Before editing, establish only the amount of structure necessary to perform the task accurately.

Identify:

- Entry point or triggering component.
- Primary implementation module.
- Related state/data flow.
- Rendering/UI layer if applicable.
- Relevant styles/configuration.
- Existing reusable helpers or patterns.
- Tests or validation paths that matter.

Do not map the entire repository when the task affects only a small subsystem.

Do not read files merely because they exist.

---

## Step 5 — Read Only Necessary Source Files

Read the minimum source needed to understand and implement the requested change.

Preferred order:

1. Files identified by `AIHelper.md`.
2. Files returned by semantic search.
3. Direct dependencies of those files when necessary.
4. Tests or configuration needed to validate the change.

Avoid:

- Entire folders.
- Unrelated modules.
- Re-reading files already adequately understood.
- Repository-wide scans without a specific reason.

Expand exploration only when the current evidence is insufficient.

---

## Step 6 — Resolve Conflicts Using Evidence

Never blindly follow outdated information in `AIHelper.md`.

If `AIHelper.md` conflicts with the actual source code:

- Treat the current source code as evidence of the current implementation.
- Avoid inventing an explanation.
- Follow the current architecture when implementing the task.
- Update or recommend updating `AIHelper.md` when the discrepancy represents meaningful project knowledge.

Do not change architecture merely because documentation is outdated.

---

## Step 7 — Respect Project Rules

Follow the documented:

- Architecture
- Design patterns
- Coding conventions
- Naming conventions
- Dependency rules
- AI instructions
- Existing component relationships
- Existing implementation patterns

Prefer extending existing systems over creating parallel systems.

Do not introduce a new architectural pattern unless the user explicitly requests it or the existing architecture genuinely cannot support the requested task.

Avoid unnecessary refactoring.

Keep changes localized whenever possible.

---

## Step 8 — Execute the User's Task

Once enough context has been established, perform the requested work.

Do not remain in an exploration loop after the relevant implementation has been identified.

Do not stop after merely describing what files are relevant when the user asked for an implementation change.

Do not respond with statements such as:

- "I don't know what task to do."
- "There is no task."
- "AIHelper does not specify a task."

when a task exists in the user's request.

Do not wait for another task after reading `AIHelper.md`.

The current user request remains active until it is completed, determined to be impossible, or shown to require missing information that genuinely cannot be obtained from the project.

---

## Step 9 — Validate the Result

After implementation:

- Check the changed code for consistency.
- Run the most relevant available tests or validation.
- Check for obvious integration issues.
- Confirm that the requested behavior was addressed.
- Avoid unrelated cleanup unless required.

If validation cannot be performed, state that clearly rather than pretending it was completed.

---

## Step 10 — Maintain AIHelper When Knowledge Changed

If the task changed meaningful project knowledge, such as:

- Architecture
- Components
- Folder structure
- Public APIs
- Configuration
- Dependencies
- Design rules
- Important relationships
- Development workflows
- Major implementation patterns

recommend running the `Maintain AIHelper` skill.

Trivial changes do not require an AIHelper update.

---

# Rules

- The user's request is the task.
- `AIHelper.md` is project knowledge, not task definition.
- Read `AIHelper.md` before broad source exploration.
- Use semantic search when implementation locations are unknown or ambiguous.
- Use source files to verify implementation details.
- Never guess implementation details when they can be inspected.
- Minimize context usage without sacrificing correctness.
- Do not perform unnecessary repository-wide scans.
- Do not let missing information in `AIHelper.md` prevent a task from being performed.
- Do not let `AIHelper.md` override explicit user instructions.
- Prefer existing architecture and reusable code.
- Do not perform unrelated refactoring.
- Treat current source code as the strongest evidence of current implementation.
- Keep the user's objective active throughout the workflow.
- Once sufficient information is available, implement rather than continuing exploration indefinitely.

---

# Failure Prevention

## "I don't know what task to do"

This is invalid when the user has already provided a task.

Return to the latest user request and use it as the task definition.

`AIHelper.md` does not need to contain the task.

---

## "There is no task"

This is invalid when the user has asked for a change, fix, explanation, analysis, review, or other action.

The task comes from the user.

---

## "AIHelper does not mention this feature"

This is not a reason to stop.

Use AIHelper to determine the surrounding architecture, then use semantic search and source inspection to locate the relevant implementation.

---

## "I need to scan the whole repository"

Do not do this by default.

First use:

1. AIHelper
2. AI Context Index / semantic search
3. Targeted file search
4. Direct source reads

Expand only when evidence shows that broader exploration is required.

---

## "The task is complete after finding the files"

Finding files is not task completion.

If the user asked for implementation, continue through:

`discover → understand → modify → validate`

---

# Success Criteria

A successful execution means:

- The user's actual request was correctly identified and remained the primary task.
- `AIHelper.md` was used as the primary source of project knowledge.
- Semantic search was used when useful for locating unknown or conceptually related implementation.
- Only the minimum necessary source files were read.
- Project conventions were followed.
- Existing architecture was preserved where appropriate.
- The requested task was actually completed rather than merely analyzed.
- No unnecessary repository-wide exploration occurred.
- The final implementation was validated as far as practical.
- `AIHelper.md` remains accurate when meaningful project knowledge changed.
