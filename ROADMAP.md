# Edera Development Roadmap

> 以 Entity 为统一原语、DAG 为执行模型的通用编排内核
> Last updated: 2026-06-10

---

## Phase 0 · 基础能力收尾（当前）

> 引擎自举已完成，核心 DAG 运行时可用。本阶段修补已知缺陷、完善已有功能。

| # | 任务 | 来源 | 状态 |
|---|------|------|------|
| 0.1 | CLI 补全 help 文档 | `todo/feat.md` | ⬜ |
| 0.2 | `session_dir` 语义修正 — 控制存放 session 的路径，非 CLI 工作目录 | `todo.md` | ⬜ |
| 0.3 | Extension 导入去重 — DB 记录已导入 extension，避免重复扫描覆写配置 | `todo/feat.md` | ⬜ |
| 0.4 | Extension 卸载 API 设计（先设计，本期不强制实现） | `todo/feat.md` | ⬜ |
| 0.5 | 导出 DB 中可用包，支持复用 | `todo/feat.md` | ⬜ |
| 0.6 | `edera` CLI 入口端到端验证（monkeypatch `sys.argv` 测试） | `todo.md` 风险项 | ⬜ |
| 0.7 | 输出型 Entity 保留/清理策略 → 改为自举 DAG 实现 | `todo.md` | ⬜ |
| 0.8 | 非事务级联删除 — cascade delete 多文件写入非原子，需回滚机制或弱化 design 承诺 | `todo.md` | DONE |
| 0.9 | Startup 信号：系统初始化完成后发出，无需关心是否有接收源 | `todo/feat.md` | ⬜ |

---

## Phase 1 · Sub-DAG & 节点增强

> 引入子 DAG 调用链，补强 agent 节点和边级 optional 语义。

| # | 任务 | 来源 | 状态 |
|---|------|------|------|
| 1.1 | Sub-DAG 执行引擎 — 父子 DAG 调用关系、数据流传递 | `todo.md`, `todo/feat.md` | ⬜ |
| 1.2 | Workbench 节点面板增加 Sub-DAG 节点类型 | `todo/feat.md` | ⬜ |
| 1.3 | Workbench 双击 DAG node 切换到 Sub-DAG 视图 | `todo/feat.md` | ⬜ |
| 1.4 | Agent 节点运行时实时内部信息展示 | `todo.md` | ⬜ |
| 1.5 | 边级 Optional 属性（节点 optional 的细粒度版本） | `todo.md` | ⬜ |
| 1.6 | Bubblewrap 沙箱隔离执行环境 | `todo.md` | ⬜ |

---

## Phase 2 · Web Console 体验打磨

> 提升前端交互质量，补齐运行时调试和可视化能力。

| # | 任务 | 来源 | 状态 |
|---|------|------|------|
| 2.1 | DAG 手动触发运行按钮 | `todo/ui.md` | ⬜ |
| 2.2 | 重试优化 — 可选择 run_id 对应的 prefilled 重新执行 | `todo.md`, `todo/ui.md` | ⬜ |
| 2.3 | Web Console 记忆上次浏览的 DAG，下次打开自动恢复 | `todo.md` | ⬜ |
| 2.4 | 节点面板增加搜索和折叠功能 | `todo.md` | ⬜ |
| 2.5 | 点击 DAG node 高亮节点及连线，其余连线降低透明度 | `todo.md` | ⬜ |
| 2.6 | Extension 管理 UI — 覆盖安装、删除 extension | `todo/ui.md` | ⬜ |
| 2.7 | CLI 同步增加 extension 管理命令 | `todo/ui.md` | ⬜ |

---

## Phase 3 · 可观测性与调试

> 让用户（和 AI）能看到 DAG 运行的全貌。

| # | 任务 | 来源 | 状态 |
|---|------|------|------|
| 3.1 | 节点运行历史输出 — fetch 节点等每个节点都应可查看输出 | `todo.md` | ⬜ |
| 3.2 | Agent 节点 Web Console 交互弹窗（运行中：中断+注入；已结束：直接发送） | `todo/feat.md` | ✅ |
| 3.3 | 触发事件来源配置 — 构思外部事件接入机制 | `todo/feat.md` | ✅ |
| 3.4 | DAG 运行结果浏览 / Result Explorer 完善 | openspec | ⬜ |

---

## Phase 4 · AI 协作 & 文档

> 解决 AI 无法理解项目上下文、无法自主构建 DAG 的核心瓶颈。

| # | 任务 | 来源 | 状态 |
|---|------|------|------|
| 4.1 | 编写面向 AI 的使用文档 — 让 AI 能根据文档构建合理 DAG 及部署内容 | `todo.md`, `todo/feat.md` | ⬜ |
| 4.2 | 编写面向人类的完整使用文档 | `todo/feat.md` | ⬜ |
| 4.3 | AI 按文档将简单 skill 自动转为 DAG 的验证 | `todo/test.md` | ⬜ |
| 4.4 | OpenSpec specs 清理 | `todo/feat.md` | ⬜ |
| 4.5 | 借鉴 [UZI-Skill](https://github.com/wbh604/UZI-Skill/tree/refactor/v3.0.0-pipeline-architecture) 提示词/搜索能力 | `todo.md` | ⬜ |
| 4.6 | 借鉴 [FinceptTerminal](https://github.com/Fincept-Corporation/FinceptTerminal) 整体架构 | `todo.md` | ⬜ |
| 4.7 | 借鉴 [CodeSee](https://github.com/Kaka-cheaper/codeSee) 项目可视化呈现 | `todo.md` | ⬜ |
| 4.8 | Agent 反思机制 — 参考 [agent-scripts skill-cleaner](https://github.com/steipete/agent-scripts/blob/main/skills/skill-cleaner/SKILL.md) | `todo.md` | ⬜ |

---

## External References

| 资源 | 用途 |
|------|------|
| [UZI-Skill v3.0 refactor](https://github.com/wbh604/UZI-Skill/tree/refactor/v3.0.0-pipeline-architecture) | 提示词设计、搜索能力 |
| [FinceptTerminal](https://github.com/Fincept-Corporation/FinceptTerminal) | 整体架构借鉴 |
| [CodeSee](https://github.com/Kaka-cheaper/codeSee) | 项目可视化呈现 |
| [agent-scripts skill-cleaner](https://github.com/steipete/agent-scripts/blob/main/skills/skill-cleaner/SKILL.md) | Agent 反思机制 |
