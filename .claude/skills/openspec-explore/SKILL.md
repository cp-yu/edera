---
name: openspec-explore
description: Enter explore mode - a thinking partner for exploring ideas, investigating problems, and clarifying requirements. Use when the user wants to think through something before or during a change.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0-cpyu.9"
---

Enter explore mode: investigate, clarify, compare, and help the user think before implementation.

## Skill Delegation Protocol

**Internal Skills** — The following skills are subagent-only and MUST NOT be read directly by this agent:
- `openspec-impact-sweeper` — Use a subagent, not direct reading

Do not read `openspec-impact-sweeper/SKILL.md` directly in the main agent.

## Hard Rules

- Do not implement application code. Creating or revising OpenSpec artifacts is allowed only when the user asks.
- Only modify files under `openspec/sweeper/` unless the user explicitly asks for artifact updates.
- Ask one clarification question at a time; do not auto-capture decisions into artifacts.
- If drafting artifacts, follow the compiled `openspec/config.yaml` prompt projection and preserve canonical headings, BDD keywords, IDs, schema keys, paths, commands, and code identifiers.

## Required Context

- Start with `openspec list --json`.
- Read relevant change artifacts when a change name is present.
- Use OPSX as navigation: project domains/capabilities, code-map refs, specs, and CLI query guidance.
- Ground claims in project files and git evidence when the idea maps to code.

Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Check `openspec/project.opsx.code-map.yaml` for code location references
- Check `openspec/specs/` for behavior documentation
- Treat it as navigation context, not as a replacement for change artifacts

**OPSX-first navigation**:
If `openspec/project.opsx.yaml` exists:
- Use `project.opsx.yaml` for domains → capabilities structure
- Use `project.opsx.code-map.yaml` to locate implementation files
- Use `openspec/specs/` for behavior documentation
- Cross-reference domains to understand system boundaries

## Mandatory Exploration Flow

1. Explore project context and identify affected subsystems.
2. Use a compact visual companion when it clarifies architecture, state, data flow, or trade-offs.
3. Ask exactly one scope/design question at a time.
4. Compare 2-3 viable options with strengths, weaknesses, best fit, and a recommendation when appropriate.
5. Confirm design sections one by one: architecture, components, data flow, tech stack, test strategy, risks/trade-offs.
6. Produce a conversation-only `Design Summary` and end with: "设计总结已完成。请审查上述设计。如果确认无误，请调用 `/opsx:propose <change-name>` 生成制品。"

## Impact Sweeps

Invoke `openspec-impact-sweeper` when the user introduces a new module, workflow, command, configuration key, project concept, or unfamiliar domain term, or when preparing to say the discussion is ready for proposal/change artifacts. Use a subagent, not direct reading, for `openspec-impact-sweeper`. Do not read `openspec-impact-sweeper/SKILL.md` directly in the main agent. Ask the subagent to run the impact sweep with `projectRoot`, `concept`, optional `optionalChangeName`, optional `knownUserTerms`, and optional `focus`. Treat each new concept as an independent sweep, even if another concept was already swept earlier in the conversation. After the subagent returns the JSON report path, read that JSON report and interpret the findings in the explore conversation.

If the report contains terminology observations, decide before impact questions. When the user confirms the terms mean the same concept, record that term group and continue the explore flow. When the user chooses a canonical term, record that canonical term. When the user says the terms are different concepts, record the rejected term group. For any recorded same-concept, canonical-term, or rejected term group, do not ask again for that same group. Do not claim proposal readiness until those scope-affecting questions are resolved or explicitly deferred by the user.

## Brainstorming Checklist

Explore MUST run this sequence before saying a proposal is ready:
1. **Explore project context**. If the request spans multiple independent subsystems, identify them and recommend an implementation order.
2. **Visual companion when useful**.
3. **Clarify one question at a time**. Ask exactly one question, then wait for the answer.
4. **Compare 2-3 options**. Present 2-3 viable approaches.
5. **Confirm design in sections**: architecture, core components, data flow, technology stack, testing strategy, risks and trade-offs.
6. **Generate Design Summary**. Produce a `Design Summary` in the conversation, not in a file.

## Existing Changes

### Capture Boundary for Existing Changes

When exploring an active change, read proposal/design/specs/tasks, reference them naturally, and offer precise artifact updates. The user decides whether to capture them.

| Insight Type                         | Where to Capture               |
|--------------------------------------|--------------------------------|
| Observable behavior requirement      | `specs/<capability>/spec.md` |
| Observable behavior changed          | `specs/<capability>/spec.md` |
| Refactor rationale or rejected path  | `design.md`                  |
| Implementation strategy              | `design.md`                  |
| Scope changed                        | `proposal.md`                |
| New work or verification identified  | `tasks.md`                   |
| OPSX graph intent changed            | `opsx-delta.yaml`            |
| Assumption invalidated               | Relevant artifact              |

Example offers:
- "That's a design decision. Capture it in design.md?"
- "This is observable behavior. Add it to specs?"
- "This changes scope. Update the proposal?"
