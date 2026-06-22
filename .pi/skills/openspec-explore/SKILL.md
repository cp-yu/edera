---
name: "openspec-explore"
description: "Enter explore mode - a thinking partner for exploring ideas, investigating problems, and clarifying requirements. Use when the user wants to think through something before or during a change."
license: "MIT"
compatibility: "Requires openspec CLI."
metadata:
  author: "openspec"
  version: "1.0"
  generatedBy: "1.4.1-cpyu.1"
---

Enter explore mode: investigate, clarify, compare, and help the user think before implementation.

## Required References

- Read `openspec/references/openspec-explore-supperpowers-style.md` before exploring. It is the authoritative Superpowers brainstorming behavior guide for hard gate, context exploration, visual companion judgment, one-question discipline, options comparison, section approval, Design Summary review, and propose handoff.
- Do not reconstruct or duplicate Superpowers behavior from this prompt. This prompt defines boundaries, context loading, sweeper delegation, and proposal routing only.

## Skill Delegation Protocol

**Internal Skills** — The following skill must NOT be invoked or read directly by this agent:
- `openspec-impact-sweeper` — it is a skill; delegate it to a subagent (see Impact Sweeps)

Do not read `openspec-impact-sweeper/SKILL.md` directly in the main agent.

## Hard Rules

- Explore is read-only for the main agent. Do not create, edit, delete, format, regenerate, or patch any project file or OpenSpec artifact.
- Only the subagent running the `openspec-impact-sweeper` skill may write its JSON report under `openspec/sweeper/`; the main explore agent may only read and interpret that report.
- The sweeper report write is an internal subagent exception and does not grant the main explore agent permission to create or modify project files or OpenSpec artifacts.
- User selection of an option, confirmation of a design section, or statements such as "可以", "就这样", "选 2", or "拆成多个文件" confirm design direction only. They are not authorization to modify files.
- Ask one clarification question at a time; do not auto-capture decisions into artifacts.
- When artifact generation is appropriate, produce a conversation-only `Design Summary` and instruct the user to call `$openspec-propose <change-name>`.

## Required Context

- Start with `openspec list --json`.
- Read relevant change artifacts when a change name is present.
- Use OPSX as navigation: project domains/capabilities, code-map refs, specs, and CLI query guidance.
- Ground claims in project files and git evidence when the idea maps to code.

Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Read the `project:` block for project intent and scope
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
6. Produce a conversation-only `Design Summary` and end with: "设计总结已完成。请审查上述设计。如果确认无误，请调用 `$openspec-propose <change-name>` 生成制品。"

## Impact Sweeps

Invoke `openspec-impact-sweeper` when the user introduces a new module, workflow, command, configuration key, project concept, or unfamiliar domain term, or when preparing to say the discussion is ready for proposal/change artifacts. Do not read `openspec-impact-sweeper/SKILL.md` in the main agent. `openspec-impact-sweeper` is a skill. Spawn a subagent and instruct it to read and execute the `openspec-impact-sweeper` skill, run the impact sweep with `projectRoot`, `concept`, optional `optionalChangeName`, optional `knownUserTerms`, and optional `focus`, and return only the JSON report path. Treat each new concept as an independent sweep, even if another concept was already swept earlier in the conversation. After the subagent returns the JSON report path, read that JSON report and interpret the findings in the explore conversation.

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

When exploring an active change, read proposal/design/specs/tasks, reference them naturally, and classify insights by where a future workflow should capture them. Do not update those artifacts in explore.

| Insight Type                         | Future Capture Target          |
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
- "That is a design decision for `design.md`; include it in the Design Summary, then call `$openspec-propose <change-name>` or the appropriate non-explore workflow."
- "This is observable behavior for `specs/<capability>/spec.md`; include it in the Design Summary, then call `$openspec-propose <change-name>` or the appropriate non-explore workflow."
- "This changes scope for `proposal.md`; include it in the Design Summary, then call `$openspec-propose <change-name>` or the appropriate non-explore workflow."
