## ADDED Requirements

### Requirement: Handler 验证使用静态分析
handler 验证 SHALL 使用 `ast.parse()` 纯静态分析，MUST NOT 通过 `exec()` 或其他运行时执行机制加载处理器代码。验证器 SHALL 检查处理器文件的以下结构属性：(1) 语法有效性，(2) 模块顶层存在名为 `run` 的函数，(3) `run` 声明为 `async def`，(4) `run` 严格接受 1 个参数。

#### Scenario: 合法 handler 通过验证
- **WHEN** 处理器文件定义 `async def run(ctx): ...`
- **THEN** 验证器 SHALL 返回空错误列表

#### Scenario: 语法错误被捕获
- **WHEN** 处理器文件包含语法错误
- **THEN** 验证器 SHALL 返回以 "syntax error:" 开头的错误信息，MUST NOT 抛出未捕获异常

#### Scenario: 缺少 run 函数
- **WHEN** 处理器文件中不存在名为 `run` 的顶层函数
- **THEN** 验证器 SHALL 返回 "missing async def run"

#### Scenario: run 非 async 被拒绝
- **WHEN** 处理器文件定义非 async 函数 `def run(ctx): ...`
- **THEN** 验证器 SHALL 返回 "run must be async def"

#### Scenario: 参数数量不为 1 被拒绝
- **WHEN** 处理器文件的 `run` 函数参数数量不为 1（包括 `*args`、`**kwargs`、keyword-only 参数）
- **THEN** 验证器 SHALL 返回 "run must accept exactly 1 parameter"

#### Scenario: 恶意代码不执行
- **WHEN** 处理器文件在 `run` 函数之外包含任意 Python 代码（import、系统调用等）
- **THEN** 验证阶段 MUST NOT 执行该代码，验证结果仅反映结构检查结论
