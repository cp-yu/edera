# 扩展测试模板

扩展测试必须放在 `extensions/*/tests/` 目录。模板目录结构：

```text
extension-test-template/
├── README.md
├── conftest.py.template
├── pytest.ini.template
├── test_handler_unit.py.template
└── test_dag_e2e.py.template
```

## 使用步骤

1. 复制模板文件到扩展的 `tests/` 目录。
2. 移除 `.template` 后缀。
3. 根据扩展需求调整模板内容。
4. 运行 `cd extensions/your-extension && pytest`。

安装测试框架：

```bash
pip install -e packages/edera-testing
```

## 测试类型

单元测试：测试 handler 逻辑、数据转换，不启动完整系统。适合验证参数传递、错误处理和 handler 签名。

E2E 测试：验证与 `edera_core` 的集成，需要安装扩展并运行 DAG。适合验证 DAG 拓扑、节点配置、资源约束和 agent 节点。

## 常见模式

Handler 测试验证 `params`、`input` 和错误分支。

DAG 拓扑测试检查节点数量、边连接和关键节点类型。

资源约束测试检查 resource entity 和节点资源声明。

Agent 节点测试用 `mock_pi_binary` 代替真实 PI binary。
