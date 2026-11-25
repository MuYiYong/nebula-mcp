# Nebula MCP Codex Plugin

这个插件把本地 `nebula-mcp` Server 接入 Codex，并提供悦数 5.3 图查询、标准化图表结果和交互式图视图。数据库连接仍由本地 Server 发起，插件不包含远端数据库凭据。

插件启动命令是 `node bin/launch.mjs`。launcher 与 DeepSeek Harness 组合包共用受管运行时（便携 Python + `nebula-mcp` wheel）；运行时已存在时直接启动，不存在时会在后台准备，然后启动 stdio MCP Server。首次启动需要网络，通常 1–3 分钟。

`plugins/nebula-mcp/.mcp.json` 指向仓库内的 launcher：

```json
{
  "mcpServers": {
    "nebula": {
      "command": "node",
      "args": ["bin/launch.mjs"],
      "cwd": "."
    }
  }
}
```

## 安装

### 通过 Codex marketplace（推荐）

```bash
codex plugin marketplace add MuYiYong/codex-marketplace
codex plugin add nebula-mcp@codex-marketplace
```

需要 Node.js 18+（launcher 使用内置 `fetch`）。安装完成后重新打开 Codex，在“插件”页启用 **Nebula MCP**。

如果首次连接时 Codex 提示 MCP 启动超时，说明后台仍在准备运行时；稍等片刻后重新打开对话或重启 Codex 即可。引导日志位于：

- macOS：`~/Library/Caches/nebula-mcp-bootstrap/bootstrap.log`
- Linux：`$XDG_CACHE_HOME/nebula-mcp-bootstrap/bootstrap.log`（默认 `~/.cache/...`）
- Windows：`%LOCALAPPDATA%\nebula-mcp-bootstrap\bootstrap.log`

也可以先手动预热运行时：

```bash
node <插件目录>/bin/launch.mjs --prepare
```

### 通过发行安装器

从 [GitHub Releases](https://github.com/MuYiYong/nebula-mcp/releases) 下载 `install.py`：

```bash
python3 install.py --mode plugin
```

安装器会安装受管运行时，并把插件副本的 `.mcp.json` 改写为安装器生成的绝对 launcher 命令，因此普通用户不需要自行维护 Python 或脚本路径。该模式仍要求系统 Python 3.10+ 用于执行安装器。

## 配置连接

### 在 Codex 桌面设置中填写

市场插件出现在 **From plugins**，该条目不可编辑。要在桌面 GUI 配置，请先用 [发行安装器](https://github.com/MuYiYong/nebula-mcp/releases) 执行 `python3 install.py --mode mcp` 注册独立的 `nebula`（Windows 使用 `py -3 install.py --mode mcp`）。已有独立条目可直接使用，不需要重新注册或卸载市场插件。

在 **设置 → MCP servers → nebula → 编辑** 中填写下表的环境变量，保存后点 **Restart**。Codex 不支持插件自定义 placeholder，但独立条目可预填空行和默认值。密码由 Codex 明文保存在本机配置中，请勿在对话中发送。独立条目优先于同名市场插件条目，不会读取后者已保存的连接。

| 字段 | 独立 MCP 的初始值 / 填写方式 |
|---|---|
| `NEBULA_ADDRESSES` | 留空；填写 `HOST:PORT`，多个地址用逗号分隔 |
| `NEBULA_USERNAME` | 留空；填写数据库用户名 |
| `NEBULA_PASSWORD` | 留空；填写数据库密码 |
| `NEBULA_TLS_ENABLED` | `false`；数据库要求 TLS 时设为 `true` |
| `NEBULA_CONNECT_TIMEOUT_MS` | `30000`（毫秒） |
| `NEBULA_ALLOW_MUTATIONS` | `false`，默认只读 |
| `NEBULA_ENVIRONMENT` | `default`，可改为 `dev_nebula` 等环境名 |

### 仅使用市场插件时的持久化配置

原有 `nebula_configure_connection` 工具仍可用。连接测试成功后，配置会保存到受管运行时数据目录的 `codex-connections.json`；下次启动 MCP 时自动加载。工具参数可能被宿主记录；如不想在对话中提供密码，请用上面的桌面设置。

- 默认保存为 `default`；传入 `name` 可保存多套连接（例如 `dev`、`prod`）。
- `nebula_list_environments` 查看已保存连接，`nebula_switch_environment` 切换；当前选择也会保存。
- 配置文件权限为 `0600`，包含明文密码，请勿共享，也不要提交到版本库。

配置文件路径：macOS `~/Library/Application Support/nebula-mcp/codex-connections.json`；Linux `$XDG_DATA_HOME/nebula-mcp/...`（默认 `~/.local/share/...`）；Windows `%LOCALAPPDATA%\nebula-mcp\...`。

## 使用

之后直接说“使用 Nebula MCP，执行 MATCH (n) RETURN n LIMIT 20”。缺图时先提示选择，用户给出图名后执行 `SESSION SET GRAPH` 并自动续跑原查询。

查询成功后，支持 MCP Apps 的客户端可以显示图、表格、Vega-Lite 图表、事实解释和实际执行 GQL；不支持 UI 的客户端仍可读取相同的 structured content。

## 升级

```bash
codex plugin marketplace upgrade
codex plugin add nebula-mcp@codex-marketplace
```

`codex-marketplace` 固定插件仓库的完整 commit，升级后重新安装即可切换版本。

## 卸载

```bash
codex plugin remove nebula-mcp@codex-marketplace
```

卸载只删除 Codex 的插件缓存，不会删除共享运行时。若确认 DeepSeek Harness 或其他 Codex 插件也不再使用该运行时，再运行 `python3 install.py --uninstall`。

## 手动验证

不经过 Codex 时，可以直接用 MCP initialize 请求验证 launcher：

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | node bin/launch.mjs
```
