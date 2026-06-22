# Superpowers-Style Explore 行为引导

这份 reference 是 Superpowers brainstorming 在 OpenSpec explore 中的适配版。它恢复设计前置纪律，但不恢复原始 Superpowers 的文件写入、提交或实现计划权限。

## Superpowers brainstorming source

Superpowers brainstorming 的核心不是随意讨论，而是在实现前把模糊想法压成经用户确认的设计：
- 先读项目上下文，再判断问题边界。
- 一次只问一个澄清问题。
- 对关键选择给出 2-3 approaches、取舍和推荐。
- 分段展示设计，每段都等用户确认。
- 自检设计，交给用户 review。
- 通过明确交接进入下一工作流。

OpenSpec 的映射：
- 原始设计文档步骤映射为 conversation-only `Design Summary`。
- 原始提交步骤被移除；explore 不写文件。
- 原始实现计划交接映射为 `openspec-propose` handoff。

## Hard gate before implementation

Do not implement before design confirmation is complete.

Explore 期间不得开始编码、生成 patch、更新 artifacts，或把用户的方向确认解释成写入授权。即使用户说"可以"、"就这样"或选择某个方案，也只表示设计方向被确认。

Simple changes still require design confirmation. 小变更可以缩短设计，但不能跳过：至少确认问题、影响范围、方案和验证方式。

## Project context exploration

先用项目事实约束讨论：
- 读取相关 OpenSpec change、spec、design、tasks。
- 查看相关实现文件、测试和 git evidence。
- 识别受影响子系统；若请求横跨多个独立子系统，先拆清楚边界和推荐顺序。
- 明确未知项，不用一般经验替代项目证据。

## Just-in-time visual companion

视觉表达只在它能降低复杂度时使用。适合场景：
- 架构边界、状态机、数据流、依赖关系。
- 多方案对比。
- 用户卡在抽象关系上。

普通 CLI 行为、窄范围修复、字段命名、测试选择等问题，用简洁文本或表格即可；不要引入浏览器或 server companion。

## One-question discipline

每轮只问一个会改变设计的问题，问完等待用户回答。不要把 scope、API、数据模型、测试策略揉成一串问题。

如果选择集合清楚，优先给 2-3 个选项并说明差异；如果选择集合不清楚，先问能缩小问题空间的一个问题。

## 2-3 approaches

对关键设计点提供 2-3 approaches。每个方案包含：
- 方案描述。
- 优点。
- 缺点或风险。
- 最适合的场景。

给出推荐时必须说明原因，并把推荐绑定到项目约束，而不是偏好。

## Section-by-section design approval

按 section 推进设计，不一次性倾倒完整方案。常见 section：
- Architecture。
- Core components。
- Data flow。
- Technology stack。
- Testing strategy。
- Risks and trade-offs。

每个 section 结束时等待用户确认。用户要求修改时，只修正当前 section 并重新确认，然后再继续下一 section。

## Design Summary self-review

生成 `Design Summary` 前先自检：
- 是否仍有未解决的 scope 问题。
- 是否有占位符、含糊边界或互相矛盾的决策。
- 是否说明了测试策略和风险。
- 是否把文件写入、artifact 更新或后续生成动作留给非 explore workflow。

`Design Summary` 必须留在对话中，不创建或更新文件。内容聚焦架构、组件、数据流、技术栈、测试策略、风险和取舍。

## User review gate

向用户展示 `Design Summary` 后停止推进，让用户 review。用户要求改动时，回到对应 section 重新确认。

Only route to openspec-propose after the user reviews and accepts the Design Summary.

## openspec-propose handoff

用户确认 `Design Summary` 后，使用工具中立 workflow 名称交接：

```
设计总结已完成。请审查上述设计。如果确认无误，请使用 openspec-propose 生成制品。
```

不要在 reference 中使用工具特定调用语法。不要暗示 explore 可以创建 proposal、更新 design、修改 specs、提交文件或直接进入实现。