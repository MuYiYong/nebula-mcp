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

## 配置连接（Git marketplace）

通过发行安装器注册的条目不使用此页面；配置方式见[高级安装与配置](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/configuration.md#codex-插件模式)。

1. 在 Codex 中选择 **配置悦数连接（打开本机浏览器）**，或打开启用该插件的对话，只说「配置悦数连接」。工具不需要参数；如出现工具确认，请确认打开浏览器。
2. 默认浏览器打开临时本机表单。填写 `HOST:PORT`、用户名和密码，按需启用 TLS，点 **测试并保存**。不要在对话里输入密码。
3. 页面显示成功后，关闭标签页并回到 Codex 继续查询。新设置即刻用于当前会话；重启和升级后仍会加载。

再次打开时会预填非密码字段；密码留空沿用已保存的密码。测试失败保留旧连接。设置页编辑当前连接，首次使用保存为 `default`。旧版保存的命名连接仍可用 `nebula_list_environments` 和 `nebula_switch_environment` 查看和切换。

`codex-connections.json` 位于受管运行时数据目录，包含明文密码（POSIX 下权限 `0600`），不会同步，请勿共享。独立的同名 MCP 条目可能优先于插件；那个条目的配置与此页面分开保存。更多信息见 [高级安装与配置](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/configuration.md#在-codex-内配置并持久化)。

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
