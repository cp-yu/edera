### Task 1: SystemConfig 增 skills_dir 并线程到 NodeExecutor

**Goal**: 引入 `skills_dir` 配置（默认 `data/skills`，与 handlers_dir 对称），沿 SystemConfig → DagController → NodeExecutor 线程传递，为后续 skills 物化与 `--skill` 引用提供路径。

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `packages/core/tests/test_system_config.py`

**Requirements**:
- SystemConfig 新增 `skills_dir: Path = Path("data/skills")` 字段
- DagController 从 `system.toml` 读取 skills_dir 并传入 NodeExecutor 构造
- NodeExecutor 保存 skills_dir 引用，供 `_build_agent_command` 使用

#### Checks

- [x] C1 Verify SystemConfig 含 skills_dir 默认值且可被 system.toml 覆盖
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Skills DB-SoT 物化与复用" / Scenario "agent 引用物化技能目录"
  - Command: `cd packages/core && python -m pytest tests/test_system_config.py -k skills_dir -q`
  - Expect: skills_dir 默认解析为 `data/skills`，system.toml 覆盖生效

### Task 2: skills 物化机制——DB 单点同步到 data/skills

**Goal**: 以 DB skills 表为唯一源，将技能内容物化到 `{skills_dir}/{name}/`；物化由 skill 的 upsert/delete 单一汇聚点触发，并在 daemon 启动时全量刷新。复用 `generate_skill_files` 的安全物化逻辑。

**Files**:
- Modify: `packages/core/src/edera_core/skills/generator.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/graph_service.py`
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Test: `packages/core/tests/test_skill_generator.py`

**Requirements**:
- `generate_skill_files` 物化目标改为 skills_dir（接收目录参数），保留 `_safe_skill_name`/`_safe_relative_path` 安全检查
- `upsert_skill` 与 `delete_skill`（或其 graph_service 调用层）在事务提交后刷新对应 name 的物化目录
- daemon/bootstrap 启动时全量刷新 data/skills（类比 handlers 的启动物化）

#### Checks

- [x] C2 Verify skill upsert 刷新物化目录
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Skills DB-SoT 物化与复用" / Scenario "skill 变更刷新物化目录"
  - Command: `cd packages/core && python -m pytest tests/test_skill_generator.py -q`
  - Expect: upsert 后 `{skills_dir}/{name}/SKILL.md` 写入；delete 后目录移除

### Task 3: _build_agent_command 能力装配重写

**Goal**: 重写 pi 命令装配，接入 skills/system_prompt/tools/context 隔离四项能力，恒定附加 `--no-skills`/`--no-context-files`。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `packages/core/tests/test_node_executor.py`

**Requirements**:
- per-node：仅 `effective.skills` 声明的技能 → `--skill {skills_dir}/{name}`
- system_prompt 非空 → `--system-prompt <text>`；system_prompt_file 非空 → `--append-system-prompt <file>`
- tools 非空 → `--tools <csv>`；空/缺省 → `--no-tools`
- 恒定附加 `--no-skills` 与 `--no-context-files`

#### Checks

- [x] C3 Verify 完整装配 argv（mock-pi 回显）
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Pi CLI subprocess 配置" / Scenario "恒定关闭 pi 自动发现"
  - Command: `cd packages/core && python -m pytest tests/test_node_executor.py -k agent_command -q`
  - Expect: argv 含 `--no-skills`、`--no-context-files`、`--skill {dir}/{name}`、`--system-prompt`/`--append-system-prompt`、`--tools`/`--no-tools`

### Task 4: per-node skill 过滤与 _closure_skills 废弃

**Goal**: 装配依据改为本节点 `effective.skills`，移除 executor 中对 `snapshot.skills` 全量并集的物化调用（session_dir/skills 死文件路径）。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Modify: `packages/core/src/edera_core/snapshot.py`
- Test: `tests/core/unit/test_node_executor_session.py`

**Requirements**:
- `_execute_agent` 不再调用 `generate_skill_files(session_dir, all snapshot skills)`
- 装配仅取 `effective.skills` 与已物化 data/skills 的交集，缺失则失败
- snapshot 仍可保留 skills 副本供查询，但不再作为全量装配来源

#### Checks

- [x] C4 Verify 仅装配本节点声明技能
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Per-node 能力装配" / Scenario "仅装配本节点声明的技能"
  - Command: `cd packages/core && python -m pytest tests/core/unit/test_node_executor_session.py -q`
  - Expect: 节点 A 执行 argv 仅含 `--skill {dir}/foo`，不含 bar

### Task 5: 删除 loader 的 system_prompt_file 快照合并与死代码

**Goal**: 落实 DB 唯一源——删除 `loader.py` 中配置加载期的 system_prompt_file 文件快照合并；移除零引用的 `node/skills.py:load_skill` 与 Python 侧 `SkillDefinition`。

**Files**:
- Modify: `packages/core/src/edera_core/config/loader.py`
- Delete: `packages/core/src/edera_core/node/skills.py`
- Modify: `packages/core/src/edera_core/node/models.py`
- Test: `packages/core/tests/test_node_config_loader.py`

**Requirements**:
- 删除 loader.py:76-80 与 494-498 的 system_prompt_file 读盘覆盖 system_prompt 逻辑
- 删除 node/skills.py 与 models.py 中的 SkillDefinition（Python 侧零引用）

#### Checks

- [x] C5 Verify loader 不再快照合并 system_prompt_file
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Per-node 能力装配" / Scenario "文件型 system prompt 执行时现读"
  - Command: `grep -rn "system_prompt_file" packages/core/src/edera_core/config/loader.py`
  - Expect: 无匹配（合并逻辑已删除，system_prompt_file 仅在 executor 执行时现读）
- [x] C6 Verify load_skill / SkillDefinition 死代码已移除
  - Verifies: `specs/agent-executor/spec.md` / REMOVED Requirement "（无对应 spec requirement——纯死代码清理，Verifies 指向 absence）"
  - Command: `grep -rn "load_skill\|class SkillDefinition" packages/core/src/edera_core/`
  - Expect: 无匹配（web-console 的 TS SkillDefinition 同名无关，不在 src 范围）

### Task 6: tools 字段收归 AgentNodeConfig（标签化联合修复）

**Goal**: 从 `FunctionNodeConfig` 移除死字段 `tools` 与 `_pi_tools` validator，仅保留于 `AgentNodeConfig`；同步修复 inspector_schema 与 payload 生成对 function 节点的 tools 处理。

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/service_common.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `tests/core/unit/test_node_instance_model.py`
- Test: `tests/core/unit/test_node_executor.py`

**Requirements**:
- FunctionNodeConfig 移除 `tools` 字段与 `_pi_tools` validator
- build_inspector_schema 仅对 agent 类型输出 tools；graph_node_payload 仅 agent 传 tools
- core_node_to_entity / _node_from_entity 对 function 节点不读写 tools

#### Checks

- [x] C7 Verify function 节点不携带 tools 字段
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Agent tools 白名单" / Scenario "function 节点不携带 tools 字段"
  - Command: `cd packages/core && python -m pytest tests/core/unit/test_node_instance_model.py tests/core/unit/test_node_executor.py -q`
  - Expect: function 节点 config 不含 tools；agent tools 白名单场景通过

### Task 7: 测试更新——C21 物化断言改写 + mock-pi argv 验证

**Goal**: 两个 C21 测试的 skills 物化断言从 session_dir/skills 改为 data/skills + per-node `--skill` 参数；新增 mock-pi 回显 argv 的端到端装配验证。

**Files**:
- Test: `tests/core/unit/test_node_executor_session.py`
- Test: `tests/core/unit/test_pi_session_invocation.py`
- Test: `packages/core/tests/test_node_executor.py`

**Requirements**:
- C21 测试断言 skills 物化于 data/skills/ 而非 session_dir/skills/
- 新增 mock-pi 回显 argv 用例，覆盖 skills/system_prompt/tools/no-context-files 完整装配
- system_prompt_file 改盘生效用例（第二次执行反映文件修改）

#### Checks

- [x] C8 Verify C21 物化断言指向 data/skills
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Skills DB-SoT 物化与复用" / Scenario "agent 引用物化技能目录"
  - Command: `cd packages/core && python -m pytest tests/core/unit/test_node_executor_session.py tests/core/unit/test_pi_session_invocation.py -q`
  - Expect: 测试断言 `{skills_dir}/{name}/SKILL.md` 存在且 argv 含 `--skill {skills_dir}/{name}`
