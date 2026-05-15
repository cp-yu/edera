## 1. OpenSpec 与设计边界

- [x] 1.1 确认变更只修改 `runtime-config-editing`，不新增重叠 capability
- [x] 1.2 明确第一版只写 `portfolio.yaml`，不引入数据库配置表或版本系统

## 2. 结构化保存路径

- [x] 2.1 增加 portfolio 结构化序列化与缺失 source 引用校验
- [x] 2.2 增加结构化保存 API，并复用 `RuntimeConfigEditor.save()`
- [x] 2.3 保留通用 `/config` 与 `/api/config` 编辑能力

## 3. Web 入口

- [x] 3.1 在配置页面展示 targets、holdings、sources 和绑定关系
- [x] 3.2 在界面中明确保存只影响后续运行，当前运行继续使用启动快照
- [x] 3.3 保持移动端可读，不引入前端构建链

## 4. 测试

- [x] 4.1 添加结构化 portfolio 页面测试
- [x] 4.2 添加保存合法 portfolio 的 API 测试
- [x] 4.3 添加非法 URL、负数持仓或缺失字段拒绝测试
- [x] 4.4 添加 target 引用不存在 source 的拒绝测试
- [x] 4.5 添加通用配置编辑回归测试

## 5. Verification

- [x] 5.1 运行 `pytest`
- [x] 5.2 运行 `ruff check .`
- [x] 5.3 运行 `mypy src`
- [x] 5.4 运行 `openspec validate portfolio-source-target-management --type change --json`
- [x] 5.5 实现完成后运行 OpenSpec sync/verify 流程
- [x] 5.6 验收完成后归档 `portfolio-source-target-management`
