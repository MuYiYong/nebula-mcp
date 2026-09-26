# 工具用途与兼容性

工具通常由客户端自动调用，无需用户记住名称。当前公开的 12 个工具均有实际实现。

## 日常查询与展示

| 工具 | 实际用途 |
|---|---|
| `nebula_test_connection` | 检查连接，返回数据库版本和脱敏配置。 |
| `nebula_list_graphs` | 发现可用图，帮助用户选择查询范围。 |
| `nebula_get_graph_schema` | 读取图类型、字段和主键，支持生成正确 GQL。 |
| `nebula_select_graph` | 在当前会话选图，自动续跑最近一条因缺少图而受阻的只读查询。 |
| `nebula_validate_gql` | 检查只读策略与语句问题；可选 EXPLAIN，不执行原查询。 |
| `nebula_execute_query` | 执行只读 GQL，返回表格、图、图表、分析和 PROFILE。 |
| `nebula_render_result` | 将已有结果和客户端撰写的解释展示为 MCP App；不额外查询数据库。 |
| `nebula_execute_mutation` | 独立执行写入，必须启用 NEBULA_ALLOW_MUTATIONS 并逐次确认。 |

校验、执行和展示承担不同职责，不是三次查询。生成 GQL 和解释由客户端完成；MCP Server 本身不调用模型。显式 GQL 不得为了生成图而改写，聚合查询也不应额外查询关系来补图。

## 可选配置能力

| 工具 | 使用场景 |
|---|---|
| `nebula_configure_connection` | 临时配置当前进程，成功后替换连接，失败保留原连接；不持久化。适用于不便编辑启动配置的客户端。 |
| `nebula_list_environments` | 列出此进程通过 NEBULA_ENVIRONMENTS 配置的环境；单环境时仅显示该环境。 |
| `nebula_switch_environment` | 切换上述命名环境，先验证连接，再清除旧会话的选图和待执行查询；失败保留旧连接。 |

这两个环境工具不能切换 Codex 中的独立 MCP 服务器。常用 dev_nebula / prod_nebula 等独立条目时，在原生设置中管理各条目即可。详细配置见 [高级配置](configuration.md)。

## 兼容入口

`nebula_render_graph` 保留给已有客户端调用，仅接受非空图。其作用已由 nebula_render_result 覆盖，新调用统一使用后者，不应对同一结果同时调用两个展示工具。保留它是为了兼容已发布接口，不是第二套渲染器。

## 已移除的功能

一跳扩展不再属于公开工具，也没有图内点击执行入口。对应的服务方法、输入输出模型和前端增量图合并模块已经清理。点击点或边只查看属性，需要后续查询时通过正常 GQL 查询完成。

## 返回结果参考

结果包含 GQL、表格、图元素、图表、PROFILE、解释事实和截断标识。图与图表规格分别为 cytoscape-elements-v1 和 vega-lite-v5。

query.display_statement 用于展示和复制，query.executed_statement 记录实际发送给数据库的语句（包含自动 PROFILE）。超出 JavaScript 安全范围的整数以字符串传输，避免主键精度丢失。结果达到上限时分析仅针对已返回样本。
