# nebula-mcp

`nebula-mcp` 是运行在本地 Codex 中的 MCP Server，通过 stdio 接入 Codex，并通过网络连接远端悦数图数据库 5.3。MCP Server 不需要部署到数据库服务器。

它负责连接、Schema 发现、GQL 校验与执行、结果解析和标准化规格输出。自然语言、Neo4j Cypher 或 nGQL 到悦数 GQL 的转换由 Codex 客户端使用 `gql-query-generator` 完成；Server 内不嵌入 LLM，也不在悦数数据库侧做语言转换。

## 安装

当目标版本的 GitHub Release 可用时，从该版本的资产下载 `install.py`。macOS/Linux 的 bash/zsh 运行：

```bash
python3 install.py
```

Windows PowerShell 使用 Release 页面中 `install.py` 的实际 URL：

```powershell
Invoke-WebRequest -Uri "<Release install.py URL>" -OutFile install.py
py -3 install.py
```

安装器需要 Python 3.10 或更高版本；它会下载并校验该 Release 的 wheel，在用户本地创建隔离环境并注册名为 `nebula` 的 MCP Server。安装器不收集数据库地址、用户名或密码。

若尚未安装 Codex CLI，安装仍会完成，但 `nebula` 尚未注册。安装器会输出稍后执行的精确命令，形式如下；安装 Codex CLI 后复制其输出的实际路径执行：

以下手工注册命令由安装器按当前 shell 正确转义：macOS/Linux 输出适用于 bash/zsh，Windows 输出适用于 PowerShell。

```text
codex mcp add nebula -- <安装器使用的系统 Python> <安装器输出的 launcher.py>
```

POSIX 上受管数据根和日志目录会被收敛到当前 uid 的 `0700`，marker、state、launcher 和日志文件为 `0600`。Windows 数据根严格位于当前用户 `%LOCALAPPDATA%\nebula-mcp` 并保留其继承 ACL，且 root leaf 若为 junction/reparse point 会在安装或卸载前拒绝；Windows 不使用 POSIX chmod，也不把 POSIX mode 检查冒充为 ACL 验证。

首次运行时若提示 `CONFIGURATION_REQUIRED`，表示 Server 已启动但尚未配置数据库；按下一节填写变量、保存并重启 MCP。

### 配置 Codex Desktop

1. 打开 `Settings > MCP servers > nebula`。
2. 在环境变量区域填写 `NEBULA_ADDRESSES`（一个或多个 `HOST:PORT`）、`NEBULA_USERNAME` 和 `NEBULA_PASSWORD`。
3. 推荐同时填写 `NEBULA_CONNECT_TIMEOUT_MS=30000`，并保留 `NEBULA_ALLOW_MUTATIONS=false`。
4. 保存设置并重启 MCP，然后在新对话中调用 `nebula_test_connection` 验证连接。

Codex 桌面当前不会为该字段提供密码遮罩：`NEBULA_PASSWORD` 在编辑页可见，并以明文保存在用户本地 `~/.codex/config.toml`。`nebula-mcp` 不使用 Keychain，也不实现自定义加密。不要共享该文件或把它加入项目版本控制；生产环境优先使用最小权限账号。Codex 的 MCP 列表即使对值做脱敏显示，也只是显示脱敏，不是加密。

Server 不自动读取工作区 `.env`。常用可选变量见 [`.env.example`](.env.example)：连接/请求/连接池等待超时、池大小、TLS、时区以及返回行、节点、边和字节上限。`NEBULA_MAX_ROWS` 只限制进入 MCP 上下文的结果，不能阻止数据库先计算大结果。

### 升级、冲突与卸载

- 升级时从新版本 Release 下载其 `install.py`，再次运行 `python3 install.py`。安装器不会 remove/add 已由它管理的 `nebula` 注册，因此会保留现有环境变量。
- 如果已存在同名 `nebula` MCP 但不是本安装器注册的命令，安装会停止。先用 `codex mcp get nebula` 核对；仅在确认替换后运行 `python3 install.py --replace-registration`。替换会删除该旧注册的环境变量，安装器不会合并或恢复它们，须先自行记录并在 Desktop 中重新填写。
- 卸载运行 `python3 install.py --uninstall`。它只移除 `nebula` 注册和本安装器管理的目录；若 Codex CLI 缺失或无法安全移除注册，安装文件会保留以避免留下无效注册。

Windows PowerShell 的升级与卸载分别运行 `py -3 install.py` 和 `py -3 install.py --uninstall`；冲突替换参数同样为 `py -3 install.py --replace-registration`。

## 推荐工作流

对于自然语言、Cypher 或 nGQL 请求，Codex 应按以下顺序工作：

1. 调用 `nebula_list_graphs` 选择目标图。
2. 调用 `nebula_get_graph_schema` 获取实际 Graph Type；未知属性必须保留为占位符，不得猜测。
3. 在 Codex 客户端使用 `$gql-query-generator` 生成悦数 5.3 GQL。
4. 调用 `nebula_validate_gql` 做静态校验，排除占位符、Cypher/nGQL 残留、多语句和安全策略问题。
5. 对需要数据库计划证据的候选语句设置 `run_explain=true`。EXPLAIN 只检查候选计划，不执行原查询。
6. 向用户展示候选 GQL 和证据边界，确认后调用 `nebula_execute_query`。
7. Codex 根据返回的事实、图/图表规格和 caveats 生成人工解释。

证据必须分开标记：

- 静态校验：只证明词法、方言残留和策略检查结果，不证明数据库可执行或业务语义正确。
- EXPLAIN 验证：证明数据库接受计划分析，不代表已经读取业务数据。
- 执行验证：只说明该语句在指定图与当次数据上实际执行；若结果被截断，分析范围仅为 `returned_rows`。

## 工具

| 工具 | 用途 |
|---|---|
| `nebula_test_connection` | 返回数据库版本和脱敏连接配置，不返回密码。 |
| `nebula_list_graphs` | 使用 `CALL show_graphs()` 分页发现持久图。 |
| `nebula_get_graph_schema` | 使用 `DESCRIBE GRAPH TYPE /schema/type` 返回结构化 Schema，可选返回受字节限制的 DDL。 |
| `nebula_validate_gql` | 静态校验候选 GQL，并可选执行 EXPLAIN；不执行原语句。 |
| `nebula_execute_query` | 只执行通过策略的单条只读 GQL，按参数返回 table、graph、analysis 和 charts。 |
| `nebula_execute_mutation` | 独立的破坏性工具；必须同时启用 Server 开关并逐次确认。 |

工具输入使用严格 Schema，未知字段会被拒绝。图、Schema 和 Graph Type 标识符只接受字母、数字和下划线，且不能以数字开头。

## 只读与 mutation 边界

默认配置是 `NEBULA_ALLOW_MUTATIONS=false`。`CREATE`、`DROP`、`ALTER`、`INSERT`、`UPDATE`、`DELETE` 等语句不能通过 `nebula_execute_query`。

即使管理员显式设置 `NEBULA_ALLOW_MUTATIONS=true`，写入也只能调用 `nebula_execute_mutation`，并为该次调用传入 `confirm_mutation=true`。MCP annotations 仅描述风险，不会自动放行。远端验收测试只执行只读语句，不使用 mutation/DDL 验证。

## 查询结果

统一结果包含 `status`、`query`、`table`、`graph`、`analysis`、`charts`、`explanation_context` 和 `truncation`：

- 图使用 `cytoscape-elements-v1`，稳定 ID 包含图上下文；边的 source/target 一定引用返回的节点元素。
- 图表使用 `vega-lite-v5`，最多返回 3 个确定性建议规格；没有合适字段时返回空列表。
- 非 JSON 原生值保留显式类型，包括日期时间、duration、embedding vector、bytes、set 和非有限浮点。
- `explanation_context` 只提供可复核事实、空结果状态、校验证据和 caveats；人工解释由 Codex 生成。
- 达到行数、字节、节点或边上限时，`truncation.reasons` 明确记录原因，统计不会被描述为完整总体。

调用方可用 `include_graph`、`include_analysis` 和 `include_charts` 控制是否生成相应内容；当前 `render_mode` 只支持 `spec`，不把 PNG 当作唯一结果。

## 开发与本地验证

开发者在仓库检出后可使用 editable 安装；这不是普通用户的 Release 安装方式：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

发布构建可在干净环境验证 wheel：

```bash
.venv/bin/python -m pip install build
.venv/bin/python -m build
python3 -m venv /tmp/nebula-mcp-wheel-venv
/tmp/nebula-mcp-wheel-venv/bin/python -m pip install dist/nebula_mcp-*.whl
/tmp/nebula-mcp-wheel-venv/bin/nebula-mcp --version
```

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/python -m nebula_mcp --help
```

真实远端测试需要在运行时提供 `NEBULA_ADDRESSES`、`NEBULA_USERNAME`、`NEBULA_PASSWORD`，且应使用只读账号。不要把凭据加入测试文件。

## 已知限制

- `nebula5-python` 5.3.0 的公开单次 `execute(timeout=...)` 参数在目标实现中没有形成可靠的逐调用 deadline。本项目只承诺连接配置中的 `NEBULA_REQUEST_TIMEOUT_MS`，不宣称可安全取消任意正在执行的查询。
- 静态校验采用保守词法策略，不是完整 GQL 解析器；未知 procedure 默认拒绝。
- 共享远端实例的数据可能变化，单次结果和耗时不能当作业务 SLA。
