# nebula-mcp

`nebula-mcp` 是运行在本地 Codex 中的 MCP Server，通过 stdio 接入 Codex，并通过网络连接远端悦数图数据库 5.3。MCP Server 不需要部署到数据库服务器。

它负责连接、Schema 发现、GQL 校验与执行、结果解析和标准化规格输出。自然语言、Neo4j Cypher 或 nGQL 到悦数 GQL 的转换由 Codex 客户端使用 `gql-query-generator` 完成；Server 内不嵌入 LLM，也不在悦数数据库侧做语言转换。

## 安装

准备 Python 3.10+、Codex，以及可访问的悦数图数据库 5.3。MCP 安装在使用者电脑上，无需部署到数据库服务器。安装依赖需要访问 GitHub 和 Python 包源。

**推荐：安装最新版并注册到 Codex 原生 MCP 设置。**

macOS / Linux：

```bash
curl -fL https://github.com/MuYiYong/nebula-mcp/releases/latest/download/install.py -o install.py
python3 install.py --mode mcp
```

Windows PowerShell：

```powershell
Invoke-WebRequest -Uri "https://github.com/MuYiYong/nebula-mcp/releases/latest/download/install.py" -OutFile install.py
py -3 install.py --mode mcp
```

安装完成后，在 Codex 的 MCP 设置中填写数据库连接信息并重启该服务器，再执行“测试 Nebula 连接”。首次显示 `CONFIGURATION_REQUIRED` 是等待配置，不是安装失败。具体字段见下方“配置 Codex Desktop”；多套环境见“多套环境配置与切换”。

**分享给其他人：直接发送 [项目首页](https://github.com/MuYiYong/nebula-mcp) 或 [最新版下载](https://github.com/MuYiYong/nebula-mcp/releases/latest)。** 上述下载地址自动指向最新稳定版。升级时重新下载最新版 `install.py`，再执行同一安装命令，保留已有连接配置。

每个 Release 提供 `install.py`、Python wheel、源码包、Codex plugin ZIP 和 `SHA256SUMS`。安装器校验下载程序包的 SHA-256；希望固定版本时，从对应 Release 下载安装器。其他 MCP 客户端可安装 wheel 并配置 `nebula-mcp` 为 STDIO 命令。

### 本地分发与其他安装方式

拿到包含 `install.py`、wheel、plugin ZIP 和 `SHA256SUMS` 的完整分发文件夹后，在该目录运行：

```bash
python3 install.py --assets .
```

Windows 使用 `py -3 install.py --assets .`。安装器会校验本地资产的 SHA-256；Python 依赖仍需联网安装，或由本机 pip 缓存/镜像提供。安装文件中不包含数据库连接信息。无 Codex 的其他 MCP 客户端也可安装 wheel 后，以 `nebula-mcp` 命令作为 stdio Server。

当目标版本的 GitHub Release 可用时，从该版本的资产下载 `install.py`。macOS/Linux 的 bash/zsh 运行：

```bash
python3 install.py
```

Windows PowerShell 也可使用固定版本 Release 页面中 `install.py` 的实际 URL：

```powershell
Invoke-WebRequest -Uri "<Release install.py URL>" -OutFile install.py
py -3 install.py
```

安装器需要 Python 3.10 或更高版本。默认使用 Codex plugin 模式：它会下载并校验该 Release 的 wheel 与 plugin ZIP，在用户本地创建隔离环境，把插件中的 `mcpServers.nebula` 改写为安装器选择的绝对系统 Python 和受管 launcher，然后注册本地 marketplace 中的 `nebula-mcp@nebula-mcp-local`。安装器不收集数据库地址、用户名或密码，也不会把 `NEBULA_*` 值写入插件文件或 Codex 子进程参数。

若当前 Codex 不支持 plugin，可显式使用传统 MCP 注册模式：

```bash
python3 install.py --mode mcp
```

已有由旧版安装器管理的独立 `nebula` MCP 注册不会被默认 plugin 安装替换，以免同时启用两个 Server。确认迁移后运行 `python3 install.py --migrate-to-plugin`；安装器只会移除已证明属于本安装器的旧注册，遇到其他同名命令会停止。

若尚未安装 Codex CLI，安装仍会完成，但插件尚未注册。默认模式会输出稍后执行的两条精确命令：先运行 `codex plugin marketplace add ... --json`，再运行 `codex plugin add nebula-mcp@nebula-mcp-local --json`。安装 Codex CLI 后复制安装器的实际输出执行。

使用 `--mode mcp` 时，安装器则输出以下传统手工注册形式：

以下手工注册命令由安装器按当前 shell 正确转义：macOS/Linux 输出适用于 bash/zsh，Windows 输出适用于 PowerShell。

```text
codex mcp add nebula -- <安装器使用的系统 Python> <安装器输出的 launcher.py>
```

POSIX 上受管数据根和日志目录会被收敛到当前 uid 的 `0700`，marker、state、launcher 和日志文件为 `0600`。Windows 数据根严格位于当前用户 `%LOCALAPPDATA%\nebula-mcp` 并保留其继承 ACL，且 root leaf 若为 junction/reparse point 会在安装或卸载前拒绝；Windows 不使用 POSIX chmod，也不把 POSIX mode 检查冒充为 ACL 验证。

首次运行时若提示 `CONFIGURATION_REQUIRED`，表示 Server 已启动但尚未配置数据库。

### 配置 Codex Desktop

连接信息可以在 **Codex Desktop → 设置 → 插件 → MCP → 服务器 → nebula 右侧齿轮** 中填写。进入详情页的 **环境变量（Environment variables）**，填写或添加：

| 配置项 | 填写内容 |
|---|---|
| `NEBULA_ADDRESSES` | `HOST:PORT`，多个地址用逗号分隔 |
| `NEBULA_USERNAME` | 数据库用户名 |
| `NEBULA_PASSWORD` | 数据库密码 |
| `NEBULA_CONNECT_TIMEOUT_MS` | `30000` |
| `NEBULA_ALLOW_MUTATIONS` | `false`，默认只读 |
| `NEBULA_ENVIRONMENT` | 当前条目的环境名，例如 `default`、`dev`，用于结果标识 |

保存后使用 MCP 设置页的“重启”（Restart），再调用 `nebula_test_connection`。如刚新增配置条目仍未显示，重新打开设置或重启 Codex Desktop。

**“服务器”和“来自插件”是两种入口。** 独立的 `mcp_servers.nebula` 注册提供设置齿轮；只有插件提供的 `nebula` 不提供这些环境变量的编辑入口。原生设置页由 Codex 提供，插件不能为它增加自定义中文字段或密码掩码。当前原生环境变量编辑器按普通文本处理值，并会去掉值首尾的空白；需要保留密码首尾空格时，使用下面的无回显配置命令。

仅使用原生 MCP 注册的新安装可以选择 `python3 install.py --mode mcp`。已安装插件的用户需要建立同名独立注册，才能在“服务器”区域编辑；下面的 `--configure` 会创建该注册，插件可继续保留。不要把插件列表中的名称行当成可编辑的连接设置。

连接不变时，查询和选图复用同一个数据库 session。开发或其他客户端也可调用 `nebula_configure_connection` 在 MCP 内临时配置，无需重启；该工具的配置只在当前进程中保留，成功后替换旧 session，失败保留原连接。Codex Desktop 日常使用应优先在上述原生设置中保存连接信息。

如需从插件注册建立独立配置入口，或使用本地无回显密码输入，在本机终端运行：

```bash
python3 install.py --configure
python3 install.py --config-status
python3 install.py --clear-config
```

Windows 将 `python3` 换为 `py -3`。`--configure` 使用无回显密码输入，默认写入 `NEBULA_CONNECT_TIMEOUT_MS=30000` 和 `NEBULA_ALLOW_MUTATIONS=false`；`--config-status` 只显示设置项是否存在。保存后重启 MCP，使启动配置生效，再调用 `nebula_test_connection`。

持久化使用用户本地 `config.toml`，其中 `NEBULA_ADDRESSES`、`NEBULA_USERNAME`、`NEBULA_PASSWORD` 以明文存储；不使用 Keychain，也不实现自定义加密。不要共享该文件或提交到版本控制。状态脱敏不是加密。

其他 MCP 客户端可把同名环境变量传给 `nebula-mcp`。Server 不自动读取工作区 `.env`，完整参数见 [`.env.example`](.env.example)。`NEBULA_MAX_ROWS` 只限制进入 MCP 上下文的结果，不能阻止数据库先计算大结果。

### 多套环境配置与切换

推荐在原生设置中为每套环境建立独立的 MCP 服务器条目。**服务器名称由你定义**，例如 `dev_nebula`、`prod_nebula`、`test_nebula`；`nebula`、`nebula-secondary` 都只是示例名称，不要求保留这些名称，也不限制为两套环境。各条目复用同一个受管 launcher，地址、用户名、密码、超时等环境变量分别填写，不需要 JSON，也不需要重复安装程序。

在 Codex 的 MCP 设置中添加自定义服务器，选择 STDIO，并填写：

| 字段 | 填写方式 |
|---|---|
| 名称 | 自定义且不与现有条目重复，例如 `dev_nebula`；建议使用字母、数字、下划线和连字符 |
| 命令 | 复制已安装 `nebula` 条目的 Python 命令 |
| 参数 | 复制同一条目的 `launcher.py` 路径，作为一个完整参数；路径含空格也不要拆开 |
| 环境变量 | 分别填写上节的六个字段；建议 `NEBULA_ENVIRONMENT=dev_nebula`，与名称一致 |

每增加一套环境，重复添加一个不同名称的条目即可。服务器名称只用于 Codex 中识别工具；`NEBULA_ENVIRONMENT` 用于结果中的环境标识，两者不会自动同步。复制连接字段时，应为新环境填写实际的地址和账号。

也可通过 Codex CLI 创建同样的原生条目，再在设置页填写连接信息。以下是命令结构，Python 和 launcher 路径替换为安装器输出的实际路径：

```text
codex mcp add dev_nebula --env NEBULA_ENVIRONMENT=dev_nebula -- <系统 Python> <launcher.py 路径>
codex mcp add prod_nebula --env NEBULA_ENVIRONMENT=prod_nebula -- <系统 Python> <launcher.py 路径>
codex mcp add test_nebula --env NEBULA_ENVIRONMENT=test_nebula -- <系统 Python> <launcher.py 路径>
```

此方式可持续添加新名称。现有安装器的 `--configure`、`--config-status` 和 `--clear-config` 仍只操作默认名称 `nebula`；自定义条目使用原生设置或 `codex mcp` 管理。

切换时，在 MCP 服务器列表关闭当前条目、开启目标条目，按客户端提示重启；保存配置修改后也需重启相应服务器。开关不是互斥选择器，建议一次只启用一套，避免向模型同时提供多套数据库工具。尚未填好连接字段的条目应保持关闭。原生设置页不提供由 MCP 自定义的环境下拉框。

插件模式用户应注意同名独立条目的优先级：删除独立 `nebula` 注册后，插件的同名服务器可能重新出现。全部采用自定义名称时，可在原生设置中关闭不再使用的默认或插件服务器。删除一个自定义条目可使用 `codex mcp remove <名称>`；它不卸载共用程序，其他条目继续使用同一 launcher。

#### 高级：单个 MCP 进程内切换

如果需要同一进程通过工具切换环境，仍支持以下 JSON 配置；这不是原生页面开关方案，二者择一配置。

原生设置只显示已保存的环境变量，不会根据 MCP 工具自动生成配置字段。已有单连接安装若看不到下面两个字段，需要在同一编辑器中添加。

在同一原生环境变量编辑器中添加 `NEBULA_ENVIRONMENTS`，值为 JSON。每个名称对应一套完整的 `NEBULA_*` 配置，不继承另一环境的地址、账号或写入权限。例如（所有值均为字符串）：

```json
{"dev":{"NEBULA_ADDRESSES":"DEV_HOST:9669","NEBULA_USERNAME":"USER","NEBULA_PASSWORD":"PASSWORD","NEBULA_CONNECT_TIMEOUT_MS":"30000"},"prod":{"NEBULA_ADDRESSES":"PROD_HOST:9669","NEBULA_USERNAME":"USER","NEBULA_PASSWORD":"PASSWORD","NEBULA_ALLOW_MUTATIONS":"false"}}
```

从单连接改为多环境时，可把原有连接字段完整放入 `default` 对象，并设置 `NEBULA_ENVIRONMENT=default`，然后继续添加其他环境。启用 `NEBULA_ENVIRONMENTS` 后，以各环境对象中的连接信息为准；外层的单连接字段不再参与连接，迁移后应移除这些重复字段，避免编辑错位置。

可再设置 `NEBULA_ENVIRONMENT=dev` 作为启动环境；配置多套但不指定默认环境时，先选择再连接，不自动猜测。环境名称支持字母、数字、下划线和连字符。保存后重启 MCP 以加载配置，之后对话中说“列出环境”或“切换到 prod”，即可调用对应工具，无需重启。单套 `NEBULA_ADDRESSES/USERNAME/PASSWORD` 配置仍可使用；其名称取 `NEBULA_ENVIRONMENT`，未指定时为 `default`。

切换成功会建立新 session，清除此前选图及待执行语句；不会把旧环境待执行语句自动移到新环境。历史图仍可查看；切换后执行的查询使用新环境。结果卡片显示所属环境。配置中含密码，应直接填写到原生设置；它仍按 Codex 的本地配置存储方式保存，工具列表和结果不会返回密码。

### 升级、冲突与卸载

- plugin 模式升级时从新版本 Release 下载其 `install.py`，再次运行 `python3 install.py`。marketplace 和 plugin add 均为幂等操作；新 wheel 与插件先校验、暂存，再切换受管版本。
- 传统 `--mode mcp` 升级不会 remove/add 已由安装器管理的 `nebula` 注册，因此会保留现有环境变量。
- 旧独立 MCP 到 plugin 的迁移必须显式使用 `--migrate-to-plugin`。如果同名 `nebula` MCP 不是本安装器注册的命令，迁移会停止且不会删除冲突。
- `--replace-registration` 只用于 `python3 install.py --mode mcp` 的传统冲突替换。替换会删除该旧注册的环境变量，安装器不会合并或恢复它们，须先自行记录并重新配置。
- 卸载运行 `python3 install.py --uninstall`。plugin 安装会先移除插件，再移除本地 marketplace，最后删除本安装器管理的目录；任何 Codex 移除步骤失败时保留安装文件和 ownership marker 以便重试。传统 MCP 安装仍先核验并移除受管 `nebula` 注册。

Windows PowerShell 的升级与卸载分别运行 `py -3 install.py` 和 `py -3 install.py --uninstall`；传统 MCP 回退使用 `py -3 install.py --mode mcp`，迁移使用 `py -3 install.py --migrate-to-plugin`。

## 推荐工作流

连接后，直接输入：

> 使用 Nebula MCP，执行 MATCH (n) RETURN n LIMIT 20

如果没有选图或目标图不存在，MCP 返回 `GRAPH_SELECTION_REQUIRED` 并保留最近一条受阻的只读查询。客户端列出可用图并请用户输入图名；收到图名后调用 `nebula_select_graph`，在原 session 中执行 `SESSION SET GRAPH`，然后自动执行刚才的查询，不需要再次粘贴语句。图选错或无权限时不会执行查询，可重新选择。后续查询沿用所选图。

用户选择新图也会替换受阻查询中显式指定的旧图引用，其余查询部分和展示选项保持不变。一次只保留最近一条受阻只读查询；新的成功查询会清除它，写操作不会自动续跑。若 session 失效会返回错误，不会自动创建新 session 冒充原有上下文。

Codex 先区分输入类型，再执行对应流程：

- **显式 GQL**：调用 `nebula_validate_gql` 后原样交给 `nebula_execute_query`；不得为了生成图而改写该语句，也不得追加第二条“可视化 GQL”。
- **自然语言标量请求**：保留只返回数值或聚合值的意图，不为补图强行投影图实体。
- **其他自然语言、Cypher 或 nGQL 请求**：调用 `nebula_list_graphs` 选择目标图，调用 `nebula_get_graph_schema` 获取实际 Graph Type，再在 Codex 客户端使用 `$gql-query-generator` 生成悦数 5.3 GQL；语义允许时优先投影 Node、Edge 或 Path，以便查询结果可以形成图。未知属性必须保留为占位符，不得猜测。

生成的 GQL 只有在目标图明确、没有剩余占位符且 `nebula_validate_gql` 的只读校验通过时才可自动调用 `nebula_execute_query`。需要数据库计划证据时设置 `run_explain=true`；EXPLAIN 只检查候选计划，不执行原查询。

查询成功后，Codex 必须展示 `query.display_statement` 中的 GQL，并同时消费所有已启用的非空结果：有图元素时呈现图，`charts` 非空时呈现每个图表，并始终根据 `explanation_context` 生成人工解释。表格不能替代图表或解释。调用 `nebula_render_result` 自动选择图或表格作为初始视图；兼容工具 `nebula_render_graph` 仍仅接受非空图。人工解释应结合具体实体、关系方向、数值和对比解释含义与洞察，区分观察和推测，并说明 LIMIT、过滤和缺失数据带来的边界，不能只复述行数。

证据必须分开标记：

- 静态校验：只证明词法、方言残留和策略检查结果，不证明数据库可执行或业务语义正确。
- EXPLAIN 验证：证明数据库接受计划分析，不代表已经读取业务数据。
- 执行验证：只说明该语句在指定图与当次数据上实际执行；若结果被截断，分析范围仅为 `returned_rows`。

## 工具

| 工具 | 用途 |
|---|---|
| `nebula_configure_connection` | 在 MCP 内配置并验证连接，无需重启，失败保留原连接。 |
| `nebula_select_graph` | 在同一 session 中选图并自动续跑受阻只读查询。 |
| `nebula_render_result` | 显示图或表格，并保留图表、解释和实际 GQL。 |
| `nebula_test_connection` | 返回数据库版本和脱敏连接配置，不返回密码。 |
| `nebula_list_graphs` | 使用 `CALL show_graphs()` 分页发现持久图。 |
| `nebula_get_graph_schema` | 使用 `DESCRIBE GRAPH TYPE /schema/type` 返回结构化 Schema，可选返回受字节限制的 DDL。 |
| `nebula_validate_gql` | 静态校验候选 GQL，并可选执行 EXPLAIN；不执行原语句。 |
| `nebula_execute_query` | 只执行通过策略的单条只读 GQL，按参数返回 table、graph、analysis 和 charts。 |
| `nebula_execute_mutation` | 独立的破坏性工具；必须同时启用 Server 开关并逐次确认。 |
| `nebula_list_environments` | 列出已配置环境名称和当前环境，不返回凭据。 |
| `nebula_switch_environment` | 测试目标环境连接，成功后切换；失败保留原连接。 |
| `nebula_render_graph` | 为非空图结果关联交互式 MCP Apps 视图；不执行数据库查询。 |

工具输入使用严格 Schema，未知字段会被拒绝。图、Schema 和 Graph Type 标识符只接受字母、数字和下划线，且不能以数字开头。

## 只读与 mutation 边界

默认配置是 `NEBULA_ALLOW_MUTATIONS=false`。`CREATE`、`DROP`、`ALTER`、`INSERT`、`UPDATE`、`DELETE` 等语句不能通过 `nebula_execute_query`。

即使管理员显式设置 `NEBULA_ALLOW_MUTATIONS=true`，写入也只能调用 `nebula_execute_mutation`，并为该次调用传入 `confirm_mutation=true`。MCP annotations 仅描述风险，不会自动放行。远端验收测试只执行只读语句，不使用 mutation/DDL 验证。

## 查询结果

统一结果包含 `status`、`query`、`table`、`graph`、`analysis`、`charts`、`explanation_context` 和 `truncation`：

- `query.display_statement` 用于展示、复制和查询记录，不包含自动添加的 PROFILE；`query.executed_statement` 保留真正发送给数据库的实际执行 GQL。用户显式写入的 PROFILE/EXPLAIN 原样保留，不重复包装。
- 只读查询默认加 PROFILE，一次执行同时获得结果和计划；内部连接探测、选图、目录/Schema 工具和更新工具保持原行为。`profile` 返回有界的算子运行信息；数据库未提供计划时明确显示空状态，不补发查询。
- 点边 JSON 中超出 JavaScript 安全整数范围的数值以十进制字符串表示，避免大整数 ID 或属性被舍入。
- 图使用 `cytoscape-elements-v1`，稳定 ID 包含图上下文；边的 source/target 一定引用返回的节点元素。
- 图表使用 `vega-lite-v5`，最多返回 3 个确定性建议规格；没有合适字段时返回空列表。
- 非 JSON 原生值保留显式类型，包括日期时间、duration、embedding vector、bytes、set 和非有限浮点。
- `explanation_context` 只提供可复核事实、空结果状态、校验证据和 caveats；人工解释由 Codex 生成。
- 达到行数、字节、节点或边上限时，`truncation.reasons` 明确记录原因，统计不会被描述为完整总体。

调用方可用 `include_graph`、`include_analysis` 和 `include_charts` 控制是否生成相应内容；当前 `render_mode` 只支持 `spec`，不把 PNG 当作唯一结果。
三个 include 开关均默认开启且相互独立。图中没有节点/边时可以不呈现图；但非空 `charts` 应呈现为图表，成功查询应同时附上基于 `explanation_context` 的人工解释。
支持 MCP Apps 的客户端可通过 `nebula_render_result` 查看图、表格、图表、PROFILE、人工解释和 GQL，并可切换自动、层级、环形或网格布局。点击点或边会在画布下方单行显示属性；点标题展示主键，边标题展示起点主键、终点主键、方向及已定义的 multiedge key。业务键通过只读 Schema 元数据识别，未返回时明确标注，不用内部 ID 替代。PROFILE 展示执行指标，不展示原始 JSON；语句右侧复制图标点击成功后显示“已复制”。不支持该 UI 的客户端仍可使用相同 structured content。

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

## 自动发布

推送到 `main` 后，GitHub Actions 自动运行 Python/UI 测试、类型和静态检查，以及 Linux/Windows 安装器兼容性验证。所有检查通过后构建安装包并发布 GitHub Release；PR 只验证不发布，也支持从 Actions 手动重跑主分支。

Release 标题为 `v年.月.日 Build小时分钟`，例如 `v26.09.19 Build1409`；标签为 `v26.09.19_Build1409`。时间取源提交的北京时间，重跑同一提交保持不变。Python 包使用兼容安装器的内部版本，例如 `0.5.2+build.202609191409`，确保每次构建升级到独立版本目录。

发布先上传草稿并回读校验，再公开；已公开版本不被重跑覆盖。同一分钟不同提交发生标签冲突时发布会失败，需要新的提交时间，不能覆盖旧标签。开发与发布检查不需要数据库凭据，CI 不代表已连接用户的数据库或已验收每个客户端的图形界面。
