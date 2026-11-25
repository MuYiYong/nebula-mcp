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

安装后，在对话中说“使用 Nebula MCP，配置数据库连接”，由 `nebula_configure_connection` 接收地址、账号、密码和 TLS/超时参数。连接信息仅在 MCP 进程内保存，查询和选图复用同一个数据库 session。密码不会返回，但工具参数可能由宿主留存。

需要持久化或本地无回显密码输入时，运行发行安装器 `python3 install.py --configure`；它会把连接写入本机 Codex `config.toml`（包含明文密码，不要共享该文件，不要提交真实值）。默认只读。

| 字段 | 内容 |
|---|---|
| `NEBULA_ADDRESSES` | 数据库地址 `HOST:PORT`；多个地址用逗号分隔 |
| `NEBULA_USERNAME` | 数据库用户名 |
| `NEBULA_PASSWORD` | 数据库密码 |
| `NEBULA_CONNECT_TIMEOUT_MS` | `30000` |
| `NEBULA_ALLOW_MUTATIONS` | `false`，默认只读 |
| `NEBULA_ENVIRONMENT` | 环境名称，例如 `dev_nebula` |

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
