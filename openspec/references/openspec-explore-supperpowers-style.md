# Superpowers-Style Explore Behavior Guide

This reference is the OpenSpec explore adaptation of Superpowers brainstorming. It restores design-first discipline but does not restore original Superpowers file writing, committing, or implementation planning permissions.

## Superpowers brainstorming source

The core of Superpowers brainstorming is not free-form discussion, but compressing vague ideas into user-confirmed designs before implementation:
- Read project context first, then determine problem boundaries.
- Ask exactly one clarification question at a time.
- For key choices, present 2-3 approaches with trade-offs and a recommendation.
- Present design section by section; wait for user confirmation on each.
- Self-review the design, then hand off for user review.
- Enter the next workflow through explicit handoff.

OpenSpec mapping:
- The original design-document step maps to a conversation-only `Design Summary`.
- The original commit step is removed; explore does not write files.
- The original implementation-plan handoff maps to `openspec-propose` handoff.

## Hard gate before implementation

Do not implement before design confirmation is complete.

Do not start coding, generate patches, update artifacts, or interpret design confirmations as write authorization during Explore. Even if the user says "ok", "that works", or chooses an option, it only confirms the design direction.

Simple changes still require design confirmation. Simple changes can shorten the design process, but cannot skip it: at minimum confirm the problem, impact scope, approach, and verification method.

## Project context exploration

Constrain the discussion with project facts first:
- Read relevant OpenSpec change, spec, design, and tasks.
- Inspect relevant implementation files, tests, and git evidence.
- Identify affected subsystems; if the request spans multiple independent subsystems, first clarify boundaries and recommend an order.
- Explicitly identify unknowns; do not substitute general experience for project evidence.

## Just-in-time visual companion

Use visual expression only when it reduces complexity. Suitable scenarios:
- Architectural boundaries, state machines, data flow, dependency relationships.
- Multi-option comparison.
- When the user is stuck on abstract relationships.

For routine CLI behavior, narrow fixes, field naming, or test selection, use concise text or tables; do not introduce a browser or server companion.

## One-question discipline

Ask only one design-changing question per turn, then wait for the answer. Do not bundle scope, API, data model, and testing strategy into a string of questions.

If the choice set is clear, prefer presenting 2-3 options with differences explained; if unclear, first ask one question that narrows the problem space.

## 2-3 approaches

Provide 2-3 approaches for key design decisions. Each option includes:
- Description.
- Strengths.
- Weaknesses or risks.
- Best-fit scenario.

When giving a recommendation, explain why and tie it to project constraints, not personal preference.

## Section-by-section design approval

Advance the design by section; do not dump a complete solution all at once. Common sections:
- Architecture。
- Core components。
- Data flow。
- Technology stack。
- Testing strategy。
- Risks and trade-offs。

Wait for user confirmation at the end of each section. When the user requests changes, revise only the current section and reconfirm before continuing.

## Design Summary self-review

Before generating the `Design Summary`, self-review:
- Are there unresolved scope questions?
- Are there placeholders, vague boundaries, or contradictory decisions?
- Are the testing strategy and risks explained?
- Are file writes, artifact updates, or subsequent generation actions left for non-explore workflows?

The `Design Summary` must stay in the conversation; do not create or update files. Content focuses on architecture, components, data flow, technology stack, testing strategy, risks, and trade-offs.

## User review gate

After showing the `Design Summary` to the user, stop advancing; let the user review. When the user requests changes, return to the corresponding section and reconfirm.

Only route to openspec-propose after the user reviews and accepts the Design Summary.

## openspec-propose handoff

After the user confirms the `Design Summary`, hand off using tool-neutral workflow names:

```
Design Summary complete. Review the above design. If confirmed, use openspec-propose to generate artifacts.
```

Do not use tool-specific call syntax in references. Do not imply that explore can create proposals, update designs, modify specs, commit files, or directly enter implementation.