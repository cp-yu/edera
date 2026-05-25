## Why

Workbench 底部 entity 过滤器当前把所有可选项横向铺开，entity 数量增加后会变成长条，挤占运行状态和底栏操作空间。

## What Changes

- 将底部 entity 过滤器改为一个紧凑的分组选择控件。
- 在展开面板内按 entity type 分组显示 item，保留多选和清除能力。
- 底栏常驻区域只显示选择摘要，不再渲染全部 item。

## Capabilities

### New Capabilities

### Modified Capabilities
- `dag-workbench-ui`: 底部 entity 过滤器从横向 item 列表改为按 entity type 分组的多选控件。

## Impact

- 影响 `apps/web-console/src/features/workbench/components/EntityFilter.tsx`。
- 影响 Workbench 底部工具栏的展示密度和过滤交互。
- 不改变后端 API、DAG 数据模型或画布过滤语义。
