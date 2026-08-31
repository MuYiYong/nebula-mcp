# nebula-mcp 设计规格

日期：2026-08-30
状态：已批准设计边界，待实现

## 1. 目标

构建一个运行在 macOS Codex 本地的 Python MCP Server，通过 stdio 与 Codex 通信，并通过官方悦数 5.3 Python SDK 远程连接悦数图数据库。Server 提供连接检查、Schema 发现、GQL 校验与执行，以及查询结果的表格、图结构、统计分析和图表规格。

## 2. 已批准边界

1. 图和图表优先返回标准化、版本化的 graph/chart spec；图片仅作为可选派生输出，不作为信息源。
2. 自然语言、Neo4j Cypher、nGQL 到悦数 5.3 GQL 的转换由 Codex 客户端使用 `gql-query-generator` 完成，不在数据库侧执行，也不在 MCP Server 内嵌第二个 LLM。
3. 查询执行默认只读。更新、DDL 和其他可能改变状态的语句必须通过环境开关和独立高风险工具显式开启。

## 3. 非目标

- 不把 MCP Server 部署到远端数据库主机。
- 不在悦数图数据库中安装生成式模型、Procedure 或 UDP 来完成自然语言转换。
- 不实现交互式 Web 前端；首版输出数据规格，由 Codex 或其他客户端渲染。
- 不依赖旧版 nebula-python `dict_for_vis()`；目标 SDK v5.3.0 未提供该稳定接口。
- 不把静态语句分类器当作数据库授权系统；数据库账号最小权限仍是最终边界。
- 不在 Server 中保存跨调用查询结果句柄或隐式会话状态。

## 4. 总体架构

```text
用户
  │ 自然语言 / Cypher / nGQL / GQL
  ▼
Codex + gql-query-generator
  │ 读取 Schema → 生成候选 GQL → 展示审阅
  ▼
nebula-mcp（本地 stdio）
  ├─ 配置与 NebulaPool 生命周期
  ├─ Schema 发现
  ├─ 静态校验与 EXPLAIN
  ├─ 只读/变更执行策略
  └─ 单遍结果解析与分析
  │ 官方 nebula5-python 5.3.0 / gRPC
  ▼
远端悦数图数据库 5.3
```

MCP Server 使用当前官方 Python MCP SDK v2 的 `MCPServer`。Server lifespan 创建并关闭 `NebulaPool`，避免每次工具调用重新认证。stdio 的 stdout 只承载 MCP 协议帧，日志写 stderr。

## 5. 客户端转换工作流

1. Codex 调用 `nebula_list_graphs` 确定目标图。
2. Codex 调用 `nebula_get_graph_schema` 获取结构化 Graph Type；必要时请求受限长度的 DDL。
3. Codex 使用本地 `gql-query-generator` 识别输入方言并生成候选悦数 5.3 GQL。
4. Codex 调用 `nebula_validate_gql` 检查占位符、方言残留、风险和可选 EXPLAIN。
5. Codex向用户展示候选 GQL、改写说明和验证状态。
6. 用户或 Agent 明确调用只读执行工具；变更语句只能调用独立变更工具。
7. Codex根据 MCP 返回的事实、graph spec、chart spec 和 caveats 生成人工解释。

MCP Server instructions 会描述该顺序，但不会声称能直接调用宿主机的本地 skill。

## 6. 配置

### 6.1 必需环境变量

| 变量 | 含义 |
|---|---|
| `NEBULA_ADDRESSES` | 一个或多个逗号分隔的 `host:port` |
| `NEBULA_USERNAME` | 数据库用户名 |
| `NEBULA_PASSWORD` | 数据库密码；不得写入日志或结果 |

### 6.2 可选环境变量

| 变量 | 默认值 | 作用 |
|---|---:|---|
| `NEBULA_DEFAULT_SCHEMA` | 空 | 默认 Schema |
| `NEBULA_DEFAULT_GRAPH` | 空 | 默认持久图 |
| `NEBULA_CONNECT_TIMEOUT_MS` | `5000` | 连接超时 |
| `NEBULA_REQUEST_TIMEOUT_MS` | `60000` | SDK 连接级请求超时 |
| `NEBULA_POOL_WAIT_TIMEOUT_MS` | `60000` | 等待连接池超时 |
| `NEBULA_POOL_MIN_SIZE` | `1` | 最小连接数 |
| `NEBULA_POOL_MAX_SIZE` | `10` | 最大连接数 |
| `NEBULA_TLS_ENABLED` | `false` | 是否启用 TLS |
| `NEBULA_TIMEZONE` | 空 | 会话时区 |
| `NEBULA_ALLOW_MUTATIONS` | `false` | 是否允许变更工具执行 |
| `NEBULA_MAX_ROWS` | `100` | 默认返回行数上限 |
| `NEBULA_MAX_NODES` | `500` | graph spec 节点上限 |
| `NEBULA_MAX_EDGES` | `1000` | graph spec 边上限 |
| `NEBULA_MAX_BYTES` | `1048576` | structured content 字节上限 |
| `NEBULA_LOG_LEVEL` | `INFO` | stderr 日志级别 |

配置在启动时一次性校验。项目提供 `.env.example`，但 Server 不自动加载工作区 `.env`。Codex 通过 `codex mcp add ... --env KEY=VALUE` 注入配置。

## 7. MCP 工具

### 7.1 `nebula_test_connection`

- 性质：只读、幂等、访问外部系统。
- 输入：无秘密参数，使用启动配置。
- 输出：连接状态、服务版本、地址数量、TLS 状态和脱敏用户名。
- 禁止：返回密码、完整认证异常或含秘密的连接串。

### 7.2 `nebula_list_graphs`

- 性质：只读、幂等。
- 输入：`schema?`、`limit`、`offset`。
- 输出：`schema`、`name`、`graph_type`、`owner`、分页元数据。
- 实现：使用已在 5.3 实机验证的 `CALL show_graphs()`，并在 MCP 层限制结果。

### 7.3 `nebula_get_graph_schema`

- 性质：只读、幂等。
- 输入：`schema`、`graph_type`、`include_ddl=false`、`max_ddl_bytes?`。
- 输出：Node/Edge Type、type pattern、labels、主键或 multiedge key、properties；可选 DDL 和 `ddl_truncated`。
- 实现：`DESCRIBE GRAPH TYPE /schema/type`；可选 `SHOW CREATE GRAPH TYPE /schema/type`。

### 7.4 `nebula_validate_gql`

- 性质：只读、幂等；不执行原语句。
- 输入：`statement`、`graph?`、`run_explain=false`。
- 输出：方言判断、占位符、方言残留、语句类别、只读策略结果、LIMIT 风险、EXPLAIN 状态与计划摘要。
- hard-stop：残留 `WITH`、`UNWIND`、Cypher 变长边、`toSet`、列表推导、nGQL `GO/FETCH/LOOKUP`、Neo4j 专有 procedure，以及无法明确分类的多语句输入。
- 边界：静态通过不等于可执行；EXPLAIN 通过不等于已在业务数据执行。

### 7.5 `nebula_execute_query`

- 性质：只读意图、非幂等性取决于外部数据变化。
- 输入：`statement`、`graph?`、`max_rows?`、`include_graph=true`、`include_analysis=true`、`render_mode="spec"`。
- 前置：必须通过只读策略；非白名单 procedure、DDL/DML、多语句被拒绝。
- 输出：第 9 节定义的统一结果对象；默认只返回 graph/chart spec。

### 7.6 `nebula_execute_mutation`

- 性质：可能破坏、非只读、通常非幂等。
- 输入：`statement`、`graph?`、`confirm_mutation`。
- 前置：`NEBULA_ALLOW_MUTATIONS=true` 且 `confirm_mutation=true`。
- 输出：状态、受影响节点/边、数据库耗时和警告；不把 mutation 结果伪装成只读查询。
- 默认行为：工具保持可发现但返回明确的 `policy_denied`，便于 Agent 解释如何启用；Server 不根据 annotations 自动放行。

## 8. 查询安全

1. 默认使用只读数据库账号；用户给出的 root 仅用于受控只读验证。
2. Server 词法扫描忽略字符串与注释，拒绝多语句、DDL/DML 关键字和未知 procedure。
3. 只读 procedure 使用显式 allowlist，不接受任意 `CALL`。
4. 变更执行必须经过环境开关、独立工具和确认参数三重门槛。
5. Pydantic v2 输入模型使用 `extra="forbid"`、长度和数值范围约束。
6. 标识符通过白名单校验后才用于构造 `USE`、DESCRIBE 或 SHOW CREATE；用户语句本身不通过 shell。
7. 结果上限只保护 MCP 上下文，不等同于数据库计算成本；缺少 LIMIT 的非聚合查询产生风险警告。

## 9. 统一查询结果

所有结果使用顶层对象，便于 MCP output schema 校验：

```json
{
  "status": {},
  "query": {},
  "table": {},
  "graph": {},
  "analysis": {},
  "charts": [],
  "explanation_context": {},
  "truncation": {}
}
```

### 9.1 `status`

包含 `ok`、悦数状态码与脱敏消息、SDK `latency_us`、受影响节点/边和阶段耗时。工具执行错误通过 `CallToolResult(is_error=true)` 返回，协议错误仅用于未知工具或非法协议请求。

### 9.2 `table`

包含 `columns`、有限 `rows`、`returned_row_count`、`result_row_count` 和 `truncated`。对非 JSON 原生值使用版本化类型包装：日期时间保留 ISO 值，duration 保留组成和值，embedding vector 保留 dimension/values，bytes 使用 base64，set 转换为确定顺序数组。

### 9.3 `graph`

默认格式为 `cytoscape-elements-v1`：

```json
{
  "format": "cytoscape-elements-v1",
  "elements": {
    "nodes": [{"data": {"id": "graph:node-id", "type": "Corp", "labels": [], "properties": {}}}],
    "edges": [{"data": {"id": "graph:src:type:rank:dst", "source": "...", "target": "...", "type": "Invest", "properties": {}}}]
  },
  "paths": []
}
```

节点键包含 graph 上下文，边键包含 graph、src、type、rank、dst。Path 同时保留 SDK 原始 `length` 和 MCP 计算的 `hop_count=len(edges)`。

### 9.4 `analysis`

只返回确定性描述统计：数值列 count/null/min/max/mean/median，类别列 top-k，图结构的节点/边类型分布、度数和连通分量。若结果被截断，所有统计显式标记 `scope="returned_rows"`，不得解释为总体。

### 9.5 `charts`

默认格式为 `vega-lite-v5`。Server 根据可用字段建议有限的 bar、line、scatter 或 histogram spec；每个 spec 包含选择理由、数据范围和截断状态。没有合适数值或类别维度时返回空数组，不制造无意义图表。

### 9.6 `explanation_context`

包含 `facts`、`caveats`、`empty_result`、`validation_evidence` 和建议关注点。Codex 基于这些证据生成中文人工解释；Server 不返回伪装成模型结论的模板化业务判断。

### 9.7 可选图片

`render_mode="spec"` 是默认值。未来或可选实现可使用 `spec_and_png`，把 PNG 放在 MCP `ImageContent`，但 structured content 始终保留原始 spec，图片不作为唯一结果。

## 10. ResultSet 解析约束

- `ResultSet.as_primitive_by_row()` 是消耗游标的 generator；执行层只遍历一次，同时构建 table、graph 和 analysis。
- Node primitive 使用 `id/type/labels/properties`。
- Edge primitive 使用 `src_id/dst_id/rank/type/labels/properties/direction`。
- SDK Path `length` 当前等于 nodes 数量，不解释为跳数；跳数使用 edges 数量。
- primitive 缺少 graph name，Server 从请求上下文补充。
- 达到任一上限后停止纳入 MCP 输出并记录截断原因；不得把截断样本标记为完整数据。

## 11. 错误模型

统一错误类别：

- `configuration_error`
- `connection_error`
- `authentication_error`
- `validation_error`
- `policy_denied`
- `database_error`
- `result_limit`
- `serialization_error`
- `render_error`

每个错误包含安全消息、`retryable` 和建议下一步；数据库状态码可返回，内部堆栈、密码和完整连接详情不返回。

## 12. 测试与验证

1. 配置与秘密脱敏单元测试。
2. GQL 词法扫描、方言残留、只读/变更分类和多语句测试。
3. Node、Edge、Path、日期时间、duration、vector、set/map/bytes 的 JSON-safe 编码测试。
4. 单遍 ResultSet 解析、去重、稳定 ID、截断和分析范围测试。
5. Cytoscape graph spec 与 Vega-Lite chart spec JSON Schema 测试。
6. MCP stdio 协议测试：initialize、tools/list、resources/list/read、tools/call、output schema、error result。
7. 真实远端只读测试：连接、版本、列图、Graph Type、标量、Node、Edge、Path。
8. mutation 默认拒绝测试；真实远端验证不执行写语句。
9. 10 个稳定、独立、只读 MCP Agent 评测问题，与单元/协议测试分开保存。

## 13. 交付物

- Python 包与 `pyproject.toml`。
- 6 个 MCP 工具及 Schema resource/instructions。
- `.env.example`、Codex stdio 注册命令和安全说明。
- 单元、协议、远端只读测试与评测文件。
- README：安装、配置、NL/Cypher 转换工作流、工具示例、输出协议和已知 SDK 限制。

## 14. 已知限制

- nebula5-python v5.3.0 的公开 `NebulaClient.execute(timeout=...)` 未实际使用传入的 per-call timeout；首版只承诺连接级 `request_timeout_ms`，不宣称可靠的逐调用取消。
- 静态校验和 EXPLAIN 不能证明业务语义正确。
- `max_rows` 只限制 MCP 返回数据，不能阻止数据库先计算大结果；查询生成阶段仍需合理过滤和 LIMIT。
- 共享远端实例的数据可能变化，不把单次实机计数当作稳定性能或业务结论。

## 15. 验收条件

- 在 macOS Codex 中可通过 stdio 启动并列出工具。
- 使用环境变量连接悦数 5.3，秘密不进入仓库或结果。
- 只读查询返回表格、Cytoscape graph spec、Vega-Lite chart spec 和解释事实。
- Codex 使用 `gql-query-generator` 完成客户端转换，并在执行前展示候选 GQL 与验证状态。
- mutation 默认被拒绝，显式开启后仍需独立工具确认。
- 所有自动化测试通过，远端只读验证成功，且 README 中的命令可复现。
