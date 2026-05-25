## Why

结果浏览 API 仍按旧 `Briefing` 对象读取 `metadata_`，但当前持久化层已经把节点输出统一为 `EntityConfig(id, type, attributes)`。这会让 `/api/results` 在存在 briefing 输出时返回 500，并让前端把真实错误误显示为“暂无数据”。

## What Changes

- **BREAKING**: 结果浏览相关 API 使用统一输出 Entity 的字符串 `id` 作为简报和建议深链标识，不再假设数据库行号或旧模型实例。
- **BREAKING**: `Briefing` Web payload 使用 `metadata` 字段，不再暴露旧 Pydantic alias 产生的 `metadata_` 字段。
- 后端结果浏览 API SHALL 将 `briefing`、`briefings`、`advices` 和详情响应转换为前端可直接消费的扁平 payload。
- 后端 SHALL 从 `EntityConfig.attributes` 读取 `cycle_id`、`content`、`metadata`、`created_at` 等结果字段。
- 前端结果页 SHALL 区分 API 错误态与真实空数据态，避免把 500 显示为“暂无数据”。

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `result-explorer`: 规范结果浏览 API 在统一输出 Entity 模型下的 payload、深链标识和错误/空态行为。

## Impact

- Affected backend: `packages/core/src/stockimformation_core/web/routes.py`, `packages/core/src/stockimformation_core/storage/repository.py`
- Affected frontend: `apps/web-console/src/api/types.ts`, `apps/web-console/src/api/queries.ts`, `apps/web-console/src/features/results/*`
- Affected API contracts: `/api/results`, `/api/briefings/latest`, `/api/briefings`, `/api/briefings/{id}`, `/api/advices`, `/api/advices/{id}`
- Dependencies: none
