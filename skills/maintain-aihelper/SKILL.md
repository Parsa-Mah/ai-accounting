---
name: maintain-aihelper
description: Create or maintain the project's AIHelper.md as a compact, factual knowledge base describing architecture, relationships, conventions, workflows, and important project decisions for AI assistants.
---
# Maintain AIHelper

## Purpose

Maintain `AIHelper.md` as a compact, factual knowledge base for AI assistants working on this project.

`AIHelper.md` describes the project.

It does **not** define future user tasks.

Its purpose is to reduce repeated repository exploration while preserving the information an AI needs to understand the project's architecture, conventions, relationships, workflows, and important decisions.

The goal is not to document every implementation detail.

The goal is to document the project's **stable and important knowledge** so future agents can quickly understand where things belong and how the project is intended to work.

---

# Core Principles

1. `AIHelper.md` must reflect the actual project.
2. Never invent or speculate about project behavior.
3. Prefer stable architectural knowledge over low-level implementation details.
4. Prefer relationships over exhaustive file descriptions.
5. Preserve accurate existing information.
6. Update only knowledge that has actually changed.
7. Minimize repository exploration during incremental maintenance.
8. Keep the document concise enough to be useful as AI context.
9. Do not turn `AIHelper.md` into a copy of the source code.
10. Do not record temporary task instructions as permanent project knowledge unless they represent an enduring project rule or decision.

---

# When to Use

Use this skill when:

- A feature has been completed.
- A subsystem has been added.
- Project architecture changes.
- New folders or modules are introduced.
- Major refactoring occurs.
- Dependencies change.
- Public APIs change.
- Configuration changes.
- Important project workflows change.
- Important design decisions change.
- The user explicitly requests `Maintain AIHelper`.
- `AIHelper.md` does not exist and a project knowledge base needs to be created.

Do not run this skill after trivial changes such as:

- Formatting
- Whitespace changes
- Typo fixes
- Comment-only changes
- Cosmetic changes that do not affect project understanding

---

# Important Distinction

`AIHelper.md` is a project knowledge document.

It is not:

- A task list
- A backlog
- A conversation transcript
- A copy of source files
- A changelog of every edit
- A place for temporary user requests
- A replacement for source code

Do not write things such as:

> "The user asked to add colored rubberbanding."

unless that request resulted in a durable architectural decision or reusable project rule.

Document the resulting architecture or behavior instead.

For example:

> "Topology selection uses the shared interaction layer and applies selection overlays through the topology renderer."

---

# Workflow

## Step 1 — Locate AIHelper.md

Search the project root for:

`AIHelper.md`

### If it exists

Use the existing document as the starting knowledge base.

Read it completely before performing broad exploration.

Preserve accurate information and update only what is necessary.

### If it does not exist

Create it from a comprehensive analysis of the repository.

Do not pretend to know information that has not been verified.

---

# Step 2 — Determine Maintenance Scope

First determine why this maintenance is being performed.

Possible scopes include:

- Initial creation
- Feature completion
- Architecture change
- Refactoring
- Dependency/configuration change
- Folder/module change
- Public API change
- User-requested full review

For incremental maintenance, identify the smallest area of the project that could have changed.

Do not immediately rescan the entire repository.

---

# Step 3 — Detect Relevant Changes

When possible, use Git to identify meaningful changes since the previous AIHelper update.

Look for:

- Added files
- Deleted files
- Renamed files
- Modified architecture
- New or removed dependencies
- Configuration changes
- New modules
- Public API changes
- Entry-point changes
- Changed component relationships
- Changed development workflows

If Git is unavailable, use targeted project inspection and compare current structure/content against the existing `AIHelper.md`.

Do not interpret every file modification as an architectural change.

---

# Step 4 — Prioritize Durable Knowledge

Prioritize information that helps future AI assistants understand the project.

High priority:

- Architecture
- Major components
- Core modules
- Data flow
- Control flow
- Component relationships
- Public APIs
- Entry points
- Dependency relationships
- Important configuration
- Build system
- Coding conventions
- Design rules
- Reusable patterns
- Significant architectural decisions
- Important development workflows
- Known limitations that affect implementation

Low priority:

- Temporary variables
- Implementation trivia
- Comments
- Formatting
- One-off code changes
- Minor tests unless they reveal architectural behavior
- Temporary debugging changes
- User-specific temporary tasks

---

# Step 5 — Use Existing AIHelper Knowledge First

Before reading source files:

- Check what `AIHelper.md` already knows.
- Reuse accurate descriptions.
- Identify exactly which statements may now be outdated.
- Determine which source files are necessary to verify those statements.

Do not reread the entire repository merely to regenerate information that is already known and unchanged.

---

# Step 6 — Use Targeted Source Analysis

Read only the files necessary to verify or update the affected knowledge.

When helpful, use semantic code search to locate:

- Components
- Functions
- Classes
- Feature implementations
- Relationships
- Similar patterns
- Entry points

Semantic search is a discovery mechanism, not a substitute for source verification.

When a relationship or architectural claim matters, verify it against the current source code.

Expand exploration only when required.

---

# Step 7 — Generate or Update AIHelper.md

If creating the document for the first time, include these sections when they are applicable to the project:

1. Project Summary
2. Project Goals
3. High-Level Architecture
4. Folder Structure
5. Critical Files
6. Core Components
7. Data Flow
8. Control Flow
9. Dependency Graph
10. External Libraries
11. Configuration
12. Coding Standards
13. Design Rules
14. Design Patterns
15. Public APIs
16. Common Development Tasks
17. Important Relationships
18. Current Project Status
19. Known Limitations
20. Decision Log
21. Glossary
22. AI Instructions
23. AI Context Index
24. Frequently Referenced Files
25. Quick Project Facts

Do not force irrelevant sections to contain artificial content.

If a section is not applicable, keep it concise or omit unnecessary detail.

---

# Step 8 — Keep AIHelper Optimized for AI Context

Write information so an AI can quickly retrieve the important facts.

Prefer:

- Short factual descriptions
- Clear relationships
- File paths
- Component responsibilities
- Entry points
- Data-flow summaries
- Constraints
- Reusable development rules

Avoid:

- Long prose
- Repeating the same fact in many sections
- Large source-code excerpts
- Exhaustive file inventories
- Low-value implementation detail
- Speculation
- Conversation history

Use compact tables or diagrams where they communicate relationships more efficiently than prose.

---

# Step 9 — Preserve and Update Relationships

Relationships are especially important.

When architecture changes, update relationships such as:

```text
UI
 ↓
Controller
 ↓
Service
 ↓
Repository
 ↓
Database
```

Also update:

- Imports/dependencies
- Data producers and consumers
- Rendering pipelines
- State ownership
- Event flow
- API relationships
- Shared utilities
- Configuration dependencies

Do not document a relationship merely because two files happen to reference one another.

Document relationships that help explain how the system actually works.

---

# Step 10 — Validate

Before saving:

- Verify all changed statements against current source code.
- Remove duplicate information.
- Remove stale information that is confirmed obsolete.
- Check that architecture diagrams remain accurate.
- Check folder descriptions.
- Check important relationships.
- Check dependency information.
- Ensure no speculative claims were introduced.
- Ensure the document remains reasonably concise.
- Ensure the document describes durable project knowledge rather than temporary task instructions.

Do not rewrite stable sections unnecessarily.

---

# Step 11 — Update Metadata

Maintain a metadata section containing:

- Last Updated
- Last Full Scan
- Last Incremental Update
- Files Analyzed
- Git Commit, when available
- Architecture Version
- AIHelper Version

### Metadata rules

`Last Full Scan` changes only after a comprehensive repository analysis.

`Last Incremental Update` changes whenever AIHelper is updated incrementally.

`Files Analyzed` should describe the files actually analyzed for the current maintenance operation rather than claiming that the entire repository was inspected.

Increment `Architecture Version` only when project architecture meaningfully changes.

Increment `AIHelper Version` when the structure or maintenance methodology of AIHelper itself changes.

Do not increment architecture version for ordinary feature additions that do not change architectural meaning.

---

# Rules

- Never invent project information.
- Never guess when source verification is possible.
- Base architectural claims on actual project evidence.
- Keep project knowledge separate from temporary user tasks.
- Preserve accurate existing information.
- Do not remove information unless it is confirmed obsolete.
- Prefer relationships over implementation trivia.
- Minimize unnecessary repository scanning.
- Use targeted source inspection.
- Use semantic search when it improves discovery efficiency.
- Do not copy source code into AIHelper unnecessarily.
- Do not rewrite stable sections without reason.
- Keep AIHelper concise enough to load into an AI context efficiently.
- Record durable architectural decisions, not temporary conversation instructions.
- Treat current source code as the primary evidence of current implementation.
- When current source contradicts AIHelper, update AIHelper to match verified current behavior.
- Do not document assumptions as facts.

---

# Handling Architectural Changes

When a change affects architecture, update all relevant areas, including:

- High-Level Architecture
- Folder Structure
- Core Components
- Data Flow
- Control Flow
- Dependency Graph
- Important Relationships
- Public APIs
- Design Rules
- Design Patterns
- Decision Log
- Current Project Status

Do not update unrelated sections merely because an architectural change occurred elsewhere.

---

# Handling New Features

For a new feature, document:

- Where the feature lives
- Which existing subsystem owns it
- Important components involved
- How data flows through it
- Important relationships
- Public interfaces
- New dependencies
- Important constraints
- Reusable implementation rules

Do not document every function created for the feature.

---

# Handling Refactoring

For refactoring:

- Identify what architectural relationship changed.
- Update affected modules and dependencies.
- Remove descriptions of obsolete structures when their removal is confirmed.
- Preserve unaffected knowledge.
- Update the Decision Log when the refactoring represents an important architectural decision.

---

# Handling Dependencies

When dependencies change, update:

- External Libraries
- Dependency Graph
- Configuration
- Build system
- Relevant Coding Standards or Design Rules

Record why a dependency exists when that reason is important for future development.

---

# Handling Configuration Changes

Document configuration only when it affects:

- Application behavior
- Architecture
- Build/deployment
- Development workflow
- External integrations
- Important environment requirements

Do not copy every configuration option into AIHelper.

---

# Success Criteria

After completion:

- `AIHelper.md` exists in the project root.
- It accurately reflects the current project.
- Important architecture and relationships are documented.
- The document is concise enough to serve as AI context.
- Stable information was preserved.
- Obsolete information was removed only when confirmed.
- No speculative information was introduced.
- The document does not become a task list or conversation history.
- Another AI should be able to understand the project's major architecture, conventions, relationships, and workflows from `AIHelper.md` before needing to inspect implementation details.

The desired result is approximately:

**AIHelper = "What is this project, how is it organized, and what rules should I follow?"**

not:

**AIHelper = "What task am I currently supposed to perform?"**
