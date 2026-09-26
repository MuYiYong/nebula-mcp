# nebula-mcp

在 Codex 中连接悦数图数据库 5.3，执行 GQL，查看表格、交互图、PROFILE 和结果解释。MCP 安装在使用者电脑上，无需部署到数据库服务器。

## 安装

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

## 配置连接

打开 Codex 的 **设置 → MCP 服务器 → nebula**，在环境变量中填写：

| 字段 | 内容 |
|---|---|
| `NEBULA_ADDRESSES` | 数据库地址 `HOST:PORT`；多个地址用逗号分隔 |
| `NEBULA_USERNAME` | 数据库用户名 |
| `NEBULA_PASSWORD` | 数据库密码 |
| `NEBULA_CONNECT_TIMEOUT_MS` | `30000` |
| `NEBULA_ALLOW_MUTATIONS` | `false`，默认只读 |
| `NEBULA_ENVIRONMENT` | 环境名称，例如 `dev_nebula`，用于结果标识 |

保存并重启该 MCP，然后在对话中输入“测试 Nebula 连接”。如果暂时看不到新条目，重新打开设置或重启 Codex。

连接信息保存在本机 Codex 配置中，包含明文密码，请勿分享该配置文件。需要在本地终端无回显输入密码时，可运行 `python3 install.py --configure`；该命令只配置默认的 `nebula` 条目。

### 多套环境

每套环境添加一个独立的 STDIO MCP 服务器，名称由你定义，例如 `dev_nebula`、`prod_nebula`、`test_nebula`，不限制为两套。

1. 在 MCP 设置中添加自定义服务器，填写一个不重复的名称。
2. 复制已安装 `nebula` 的命令和参数，复用同一程序，无需重复安装。`launcher.py` 路径应作为一个完整参数，含空格时不要拆开。
3. 分别填写该环境的地址、用户名和密码；建议 `NEBULA_ENVIRONMENT` 与服务器名称一致。
4. 保存后按客户端提示重启对应服务器，测试连接。

切换时关闭当前条目、开启目标条目。若同时启用多套，请在查询请求中明确指定服务器名称。尚未配置的条目，以及不再使用的默认或插件条目，应保持关闭。

## 使用

直接输入 GQL：

> 使用 dev_nebula，执行 MATCH (n) RETURN n LIMIT 20

用自然语言提出查询：

> 使用 dev_nebula，先查看图和 Schema，再查找指定球员的队友关系。

未选图时，客户端会列出可用图并请你选择；选择后自动继续刚才的查询，不需要重复发送。后续查询沿用所选图。

自然语言、Cypher 或 nGQL 转换可配合客户端的 [gql-query-generator 技能](https://github.com/MuYiYong/nebula-gql-skills)。已有 GQL 可以直接执行，不需要额外安装该技能。

查询结果可显示表格、交互图、图表、PROFILE 和解释。点击点或边查看属性与主键；复制图标复制原始 GQL 并提示“已复制”。自动添加的 PROFILE 不出现在复制的语句中。客户端不支持 MCP Apps 时，仍可查看文本和表格结果。

默认只读。需要写入时，应使用具备相应权限的账号，将 `NEBULA_ALLOW_MUTATIONS` 设为 `true`，重启 MCP，并在每次写入时明确确认。请按业务需要限制数据库账号权限。

## 升级

重新执行上面的下载与安装命令即可。安装器会保留已管理服务器的连接配置；自定义条目共用同一启动程序，升级后重启相关 MCP。

## 卸载

如添加了多个自定义条目，先在 Codex 中删除共用此程序的条目，再卸载程序：

```bash
python3 install.py --uninstall
```

Windows 使用 `py -3 install.py --uninstall`。卸载会删除受管 MCP 程序；仅删除某个环境时，在 Codex 中删除对应条目即可，不必卸载程序。

## 常见问题

- **CONFIGURATION_REQUIRED**：程序已启动，但连接信息尚未填完整。检查地址、用户名和密码。
- **连接失败**：检查数据库服务、端口、网络和账号权限；保存配置后重启相应 MCP。
- **没有交互图**：语句需要返回点、边或路径；聚合值通常只显示表格或图表。客户端也需要支持 MCP Apps。
- **结果被截断**：仅展示了部分数据，解释和统计也仅针对返回部分；请收紧查询范围。
- **安装时提示同名冲突**：先检查已有条目的启动命令，避免覆盖其他程序的配置。

[高级安装与配置](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/configuration.md) · [工具用途与兼容性](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/tools.md)
