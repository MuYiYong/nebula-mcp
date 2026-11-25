# nebula-mcp

在 [Codex](#codex) 或 [DeepSeek Harness](#deepseek-harness) 中连接悦数图数据库（NebulaGraph 5.x），执行 GQL。当前 SDK 面向悦数图数据库 5.3，不支持开源版 NebulaGraph 3.x。MCP 安装在运行客户端的机器上，无需部署到数据库服务器。

## Codex

### 安装

准备 Python 3.10+、Codex，以及可访问的悦数图数据库 5.3。安装需要访问 GitHub 和 Python 包源。

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

安装器会校验并安装程序包，将 `nebula` 注册为独立 MCP 服务器。如果未找到 Codex CLI，按安装器输出的命令完成注册。下载或分享固定版本请使用 [GitHub Releases](https://github.com/MuYiYong/nebula-mcp/releases)。

### 配置连接

如果 Codex 中的 `nebula` 只出现在 **“来自插件”** 分组，且这一行没有齿轮按钮，就不能在该插件条目上编辑连接参数。请先按上面的安装命令运行 `python3 install.py --mode mcp`（Windows 为 `py -3 install.py --mode mcp`）；已经安装过插件也可以运行。完成后重新打开 Codex 设置，在 **插件 → MCP → 服务器** 分组找到带齿轮的独立 `nebula`，点击齿轮，在环境变量中填写：

新建的独立条目会预置以下字段名；地址、用户名和密码留空，其他字段采用表中的默认值。已有条目升级时保留原配置，不会重置这些字段。

| 字段 | 内容 |
|---|---|
| `NEBULA_ADDRESSES` | 数据库地址 `HOST:PORT`；多个地址用逗号分隔 |
| `NEBULA_USERNAME` | 数据库用户名 |
| `NEBULA_PASSWORD` | 数据库密码 |
| `NEBULA_CONNECT_TIMEOUT_MS` | `30000` |
| `NEBULA_ALLOW_MUTATIONS` | `false`，默认只读 |
| `NEBULA_ENVIRONMENT` | 环境名称，例如 `dev_nebula`，用于结果标识 |

保存并重启该 MCP，然后在新对话中输入“测试 Nebula 连接”。如果仍只看到“来自插件”的条目，先重启 Codex，再确认安装命令没有报错；不要在无齿轮的插件条目上寻找环境变量编辑入口。插件条目可以继续保留，连接配置以“服务器”分组中的独立 `nebula` 为准。

连接信息保存在本机 Codex `config.toml` 中，包含明文密码；页面编辑密码时也可能可见，请勿分享该文件或把它加入版本库。若更希望在终端无回显输入密码，可使用[高级配置命令](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/configuration.md#连接配置命令)，但页面配置不需要运行该命令。

#### 多套环境

每套环境添加一个独立的 STDIO MCP 服务器，名称由你定义，例如 `dev_nebula`、`prod_nebula`、`test_nebula`，不限制为两套。

根据当前公开的 Codex 插件接口，本项目不能在原生 MCP 设置页的 `nebula` 齿轮旁添加“复制集群”按钮。添加另一套环境时，请在同一设置页新建独立 MCP 服务器并按下面步骤配置。

1. 在 MCP 设置中添加自定义服务器，填写一个不重复的名称。
2. 复制已安装 `nebula` 的命令和参数，复用同一程序，无需重复安装。`launcher.py` 路径应作为一个完整参数，含空格时不要拆开。
3. 分别填写该环境的地址、用户名和密码；建议 `NEBULA_ENVIRONMENT` 与服务器名称一致。
4. 保存后按客户端提示重启对应服务器，测试连接。

切换时关闭当前条目、开启目标条目。若同时启用多套，请在查询请求中明确指定服务器名称。尚未配置的条目，以及不再使用的默认或插件条目，应保持关闭。

### 使用

直接输入 GQL：

> 使用 dev_nebula，执行 MATCH (n) RETURN n LIMIT 20

用自然语言提出查询：

> 使用 dev_nebula，先查看图和 Schema，再查找指定球员的队友关系。

未选图时，客户端会列出可用图并请你选择；选择后自动继续刚才的查询，不需要重复发送。后续查询沿用所选图。

自然语言、Cypher 或 nGQL 转换可配合客户端的 [gql-query-generator 技能](https://github.com/MuYiYong/nebula-gql-skills)。已有 GQL 可以直接执行，不需要额外安装该技能。

查询结果可显示表格、交互图、图表、PROFILE 和解释。点击点或边查看属性与主键；复制图标复制原始 GQL 并提示“已复制”。自动添加的 PROFILE 不出现在复制的语句中。客户端不支持 MCP Apps 时，仍可查看文本和表格结果。

默认只读。需要写入时，应使用具备相应权限的账号，将 `NEBULA_ALLOW_MUTATIONS` 设为 `true`，重启 MCP，并在每次写入时明确确认。请按业务需要限制数据库账号权限。

### 升级

重新执行上面的下载与安装命令即可。安装器会保留已管理服务器的连接配置；自定义条目共用同一启动程序，升级后重启相关 MCP。

### 卸载

如添加了多个自定义条目，先在 Codex 中删除共用此程序的条目，再卸载程序。如果 DSH 也使用该安装器提供的运行时，请勿执行以下命令，否则 DSH 也会失去运行时：

```bash
python3 install.py --uninstall
```

Windows 使用 `py -3 install.py --uninstall`。卸载会删除受管 MCP 程序；仅删除某个环境时，在 Codex 中删除对应条目即可，不必卸载程序。

### 常见问题

- **CONFIGURATION_REQUIRED**：程序已启动，但连接信息尚未填完整。检查地址、用户名和密码。
- **连接失败**：检查数据库服务、端口、网络和账号权限；保存配置后重启相应 MCP。
- **没有交互图**：语句需要返回点、边或路径；聚合值通常只显示表格或图表。客户端也需要支持 MCP Apps。
- **结果被截断**：仅展示了部分数据，解释和统计也仅针对返回部分；请收紧查询范围。
- **安装时提示同名冲突**：先检查已有条目的启动命令，避免覆盖其他程序的配置。

## DeepSeek Harness

### 安装 DSH 组合包（运行时自动准备）

需要 DeepSeek Harness（DSH）`0.2.2-rc.5` 或符合 `^0.2.2-rc.5` 的更新版本。插件首次启动会自动准备受管运行时（便携 Python + 当前 Release 的 wheel/依赖），不需要系统 Python 3.10+ 或手动运行安装器。

1. 在 DSH 的 **插件 → 实验性插件** 启用 **自定义插件索引**，再到 **发现 → 添加索引源**，填入 [MuYiYong/dsh-marketplace 的索引地址](https://raw.githubusercontent.com/MuYiYong/dsh-marketplace/main/index.json)。搜索并安装 `dsh-nebula-mcp`，设置中显示为 **NebulaGraph**。
2. 首次启动会自动准备运行时：插件下载便携 Python（python-build-standalone），执行当前 Release 的 `install.py --mode runtime --yes`，再下载 wheel 和依赖。首次需要网络，通常 1–3 分钟；已安装受管运行时的机器直接复用。

网络受限时，可按 [高级安装与配置](docs/configuration.md#dsh-runtime) 手动运行 `python3 install.py --mode runtime`（需要 Python 3.10+）。`--mode runtime` 不检测/修改 Codex；Release 说明里的 `--mode mcp` 是 Codex 入口，DSH 不要用。

### 在 DSH 中连接和测试

1. 打开 **设置 → NebulaGraph**（位于 **Agent 预设** 下方）。每个 DSH 配置档可保存最多 20 个命名的 NebulaGraph 5.x 连接，所有 Agent 预设共享一个当前连接，仅限只读 GQL。旧版单连接升级后显示为 `Default`，密码和启用状态保持不变。
2. **连接** 列表的每一行显示连接名称、用户名和数据库地址；用单选按钮选择当前连接，切换立即生效。当前连接由单选选中状态和该连接的强调色区分，不再额外显示“当前”标签。一次只有一个连接注册为 MCP 工具；如果旧实例无法确认退出，不会启动替代实例。
3. 点击连接行展开该连接的设置，在行内编辑名称、地址（`HOST:PORT`，同一集群的多个地址用逗号分隔）、用户名、密码和 TLS；TLS 默认不启用，需要时再勾选。输入停止约半秒后自动保存，密码在离开输入框后保存；展开后可点 **测试连接**，实际登录该连接并显示服务器版本和耗时，测试不会切换当前连接。测试成功后，该连接行的描述会显示 `v版本`（例如 `root · 192.168.15.240:39669 · v5.3.2`）；版本保存在当前 DSH Web 地址的浏览器本地存储，刷新或重启同一地址后仍保留。未测试、测试失败或清除站点数据后显示 `-`，重新测试即可。点击 **新建连接** 会直接在列表末尾出现一行新连接（默认名可改），行摘要随下方名称、用户名和地址实时更新；填写完整并确认密码后自动保存，没有单独的创建/取消按钮。新行也可以先点 **测试连接**（使用当前输入，不落库）；放弃这行草稿点行尾垃圾桶。已有当前连接时不会自动切换，勾选它的单选按钮即可切换；如果还没有当前连接，创建成功会自动启用。每个连接的密码单独保存在本机 DSH 凭据库，不会回显；修改地址、用户名或 TLS 时必须重输该连接的密码。请勿把密码发到对话中。
4. 有修改等待自动保存时，展开其他连接和移除会暂时停用；自动保存完成或放弃后即可继续，单选按钮仍可切换当前连接；点击新建会先提交待保存内容再展开新行。**移除连接** 会删除该连接及其密码；移除当前连接后没有生效的连接，不会自动切换到其他数据库。

页面不展示 Python 运行时或 MCP 状态。首次安装后插件会在后台准备运行时，可能需要 1–3 分钟；如果查询工具暂时不可用，先确认已在列表中选中连接，并在 DSH Host 日志中查看 `[nebula-dsh]` 引导信息。MCP 可用不代表数据库已连通；可在连接行内点 **测试连接**，或在会话中挂载 `nebula_graph` 调用 `nebula_test_connection`。Codex 和 DSH 可能共用受管运行时，只停用其中一端时请勿删除共享运行时。

DSH 内置 MCP 客户端当前把工具结果展示为文本，不渲染上游 MCP Apps 的交互图/表；`nebula_render_result` 返回的查询解释、表格文本和结构化结果仍会保留。

[高级安装与配置](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/configuration.md) · [工具用途与兼容性](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/tools.md)
