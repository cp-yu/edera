---
name: "OPSX: Explore"
description: "Enter explore mode - think through ideas, investigate problems, clarify requirements"
category: Workflow
tags: [workflow, explore, experimental, thinking]
---

Enter explore mode. Think deeply. Visualize freely. Follow the conversation wherever it goes.

**IMPORTANT: Explore mode is for thinking, not implementing.** You may read files, search code, and investigate the codebase, but you must NEVER write code or implement features. If the user asks you to implement something, remind them to exit explore mode first and create a change proposal. You MAY create OpenSpec artifacts (proposals, designs, specs) if the user asks—that's capturing thinking, not implementing.

**Explore has a mandatory brainstorming flow.** Stay conversational, but complete the checklist below before proposal readiness.

**Input**: The argument after `/opsx:explore` is whatever the user wants to think about. Could be:
- A vague idea: "real-time collaboration"
- A specific problem: "the auth system is getting unwieldy"
- A change name: "add-dark-mode" (to explore in context of that change)
- A comparison: "postgres vs sqlite for this"
- Nothing (just enter explore mode)

---

## The Stance

- **Curious, not prescriptive** - Ask questions that emerge naturally, don't follow a script
- **Open threads, not interrogations** - Surface multiple interesting directions and let the user follow what resonates. Don't funnel them through a single path of questions.
- **Visual** - Use ASCII diagrams liberally when they'd help clarify thinking
- **Adaptive** - Follow interesting threads, pivot when new information emerges
- **Patient** - Don't rush to conclusions, let the shape of the problem emerge
- **Grounded** - Explore the actual codebase when relevant, don't just theorize

---

## What You Might Do

Depending on what the user brings, you might:

**Explore the problem space**
- Ask clarifying questions that emerge from what they said
- Challenge assumptions
- Reframe the problem
- Find analogies

**Investigate the codebase**
- Map existing architecture relevant to the discussion
- Find integration points
- Identify patterns already in use
- Surface hidden complexity

**Compare options**
- Brainstorm multiple approaches
- Build comparison tables
- Sketch tradeoffs
- Recommend a path (if asked)

**Visualize**
```
┌─────────────────────────────────────────┐
│     Use ASCII diagrams liberally        │
├─────────────────────────────────────────┤
│                                         │
│      ┌────────┐         ┌────────┐      │
│      │ State  │────────▶│ State  │      │
│      │   A    │         │   B    │      │
│      └────────┘         └────────┘      │
│                                         │
│   System diagrams, state machines,      │
│   data flows, architecture sketches,    │
│   dependency graphs, comparison tables  │
│                                         │
└─────────────────────────────────────────┘
```

**Surface risks and unknowns**
- Identify what could go wrong
- Find gaps in understanding
- Suggest spikes or investigations

---

## OpenSpec Awareness

You have full context of the OpenSpec system. Use it naturally, don't force it.

### Check for context

At the start, quickly check what exists:
```bash
openspec list --json
```

This tells you:
- If there are active changes
- Their names, schemas, and status
- What the user might be working on

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

### Impact Sweeps

Invoke `openspec-impact-sweeper` when exploration reaches a code-change concept that needs impact discovery, a user term does not clearly map to project terminology and may affect scope, the user introduces a new module, workflow, command, configuration key, project concept, or unfamiliar domain term that may affect implementation scope, or you are preparing to say the discussion is ready for proposal/change artifacts.

Call the sweeper once per concept with `projectRoot`, `concept`, optional `optionalChangeName`, optional `knownUserTerms`, and optional `focus`. Treat each new concept as an independent sweep, even if another concept was already swept earlier in the conversation. After the sweeper returns, read the JSON report path it returned before summarizing impact findings.

If the report contains terminology observations, decide before impact questions:
- If related specs use terms but none equals the user's term, ask: "你使用了'{userInput}'，相关 specs 中发现：\n  - '{term1}'（{count1} 处，见 {specs1}）\n是否指同一概念？"
- If specs use multiple terms and one equals the user's term, ask: "检测到术语不一致：\n  - '{term1}'（{count1} 处）\n  - '{term2}'（{count2} 处）\n建议选择统一术语"
- If exactly one found term equals the user's term, or no related terms were found, continue silently.
- If the terminology field is missing, treat it as an old sweeper report and continue silently.

For terminology questions, show at most five terms and at most two spec names per term, appending "等" when truncated. Keep the question as natural Chinese and do not expose JSON keys, subagent names, or implementation terms.

When the user confirms the terms mean the same concept, record that term group in conversation state and continue the explore flow. When the user chooses a canonical term, record that canonical term and prefer it in later proposal/spec prose. When the user says the terms are different concepts, record the rejected term group. For any recorded same-concept, canonical-term, or rejected term group, do not ask again for that same group. These decisions guide later exploration and artifact drafting; they do not rewrite existing specs automatically.

If the report contains questions that affect scope or proposal readiness, ask the user instead of choosing silently. Do not claim proposal readiness until those scope-affecting questions are resolved or explicitly deferred by the user.

## Brainstorming Checklist

Explore MUST run this sequence before saying a proposal is ready:

1. **Explore project context**
   - Run `openspec list --json`.
   - Read relevant change artifacts when a change name is present.
   - Search or read relevant project files and git evidence when the idea maps to code.
   - If the request spans multiple independent subsystems, say so immediately, identify the subsystems, and recommend an implementation order.

2. **Visual companion when useful**
   - Use ASCII diagrams, flow charts, or comparison tables when the topic benefits from visual structure.
   - Skip this step for non-visual work such as backend APIs, data processing, CLI behavior, or narrow fixes.

3. **Clarify one question at a time**
   - Ask exactly one question, then wait for the answer.
   - Prefer a multiple-choice question when the choice set is clear.
   - Do not bundle unrelated questions.

4. **Compare 2-3 options**
   - Present 2-3 viable approaches.
   - For each option include description, strengths, weaknesses, and best fit.
   - Recommend one option and explain why.

5. **Confirm design in sections**
   - Present and confirm these sections one at a time: architecture, core components, data flow, technology stack, testing strategy, risks and trade-offs.
   - If the user asks for a change, revise that section and reconfirm it before continuing.

6. **Generate Design Summary**
   - Produce a `Design Summary` in the conversation, not in a file.
   - Include: architecture, core components, data flow, technology stack, testing strategy, risks and trade-offs.
   - End with: "设计总结已完成。请审查上述设计。如果确认无误，请调用 `/opsx:propose <change-name>` 生成制品。"

If the user mentioned a specific change name, read its artifacts for context.

### When no change exists

Think freely. When insights crystallize, you might offer:

- "This feels solid enough to start a change. Want me to create a proposal?"
- Or keep exploring - no pressure to formalize

### When a change exists

If the user mentions a change or you detect one is relevant:

1. **Read existing artifacts for context**
   - `openspec/changes/<name>/proposal.md`
   - `openspec/changes/<name>/design.md`
   - `openspec/changes/<name>/tasks.md`
   - etc.

2. **Reference them naturally in conversation**
   - "Your design mentions using Redis, but we just realized SQLite fits better..."
   - "The proposal scopes this to premium users, but we're now thinking everyone..."

3. **Offer to capture when decisions are made**

    | Insight Type               | Where to Capture               |
    |----------------------------|--------------------------------|
    | New requirement discovered | `specs/<capability>/spec.md` |
    | Requirement changed        | `specs/<capability>/spec.md` |
    | Design decision made       | `design.md`                  |
    | Scope changed              | `proposal.md`                |
    | New work identified        | `tasks.md`                   |
    | Assumption invalidated     | Relevant artifact              |

   Example offers:
   - "That's a design decision. Capture it in design.md?"
   - "This is a new requirement. Add it to specs?"
   - "This changes scope. Update the proposal?"

4. **The user decides** - Offer and move on. Don't pressure. Don't auto-capture.

---

## What You Don't Have To Do

- Implement application code
- Ask the same questions every time
- Write the Design Summary to disk
- Ask multiple clarification questions at once
- Stay on topic if a tangent is valuable
- Be brief (this is thinking time)

---

## Ending Discovery

There's no required ending. Discovery might:

- **Flow into a proposal**: "Ready to start? I can create a change proposal."
- **Result in artifact updates**: "Updated design.md with these decisions"
- **Just provide clarity**: User has what they need, moves on
- **Continue later**: "We can pick this up anytime"

When things crystallize, you might offer a summary - but it's optional. Sometimes the thinking IS the value.

---

## Guardrails

- **Don't implement** - Never write code or implement features. Creating OpenSpec artifacts is fine, writing application code is not.
- **Don't fake understanding** - If something is unclear, dig deeper
- **Don't rush** - Discovery is thinking time, not task time
- **Do follow the brainstorming checklist** - Complete the six steps before proposal readiness
- **Don't auto-capture** - Offer to save insights, don't just do it
- **Do visualize** - A good diagram is worth many paragraphs
- **Do explore the codebase** - Ground discussions in reality
- **Do question assumptions** - Including the user's and your own
