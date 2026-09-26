# Nebula MCP Codex Plugin

这个插件把本地 `nebula-mcp` Server 接入 Codex，并提供悦数 5.3 图查询、标准化图表结果和交互式图视图。数据库连接仍由本地 Server 发起，插件不包含远端数据库凭据。

仓库中的通用配置使用已位于 `PATH` 的命令：

```json
{
  "mcpServers": {
    "nebula": {
      "command": "nebula-mcp",
      "args": []
    }
  }
}
```

正式 Release 的安装器会把受管插件副本改写为安装器生成的绝对 launcher 命令，因此普通用户不需要自行维护 Python 或脚本路径。

要在 Codex 页面配置持久连接，先运行发行安装器 `python3 install.py --mode mcp`（Windows 为 `py -3 install.py --mode mcp`）。插件分组中的 `nebula` 没有环境变量编辑按钮；安装完成后，在“设置 → 插件 → MCP → 服务器”分组打开独立 `nebula` 的齿轮，填写 `NEBULA_ADDRESSES`、`NEBULA_USERNAME`、`NEBULA_PASSWORD`，保存并重启。操作步骤和其他字段见[项目 README](https://github.com/MuYiYong/nebula-mcp#配置连接)。

如需只在当前 MCP 进程临时配置连接，可调用 `nebula_configure_connection`；工具参数可能由宿主留存。持久配置请使用上面的 Codex 页面，或运行发行安装器 `python3 install.py --configure` 在本地无回显输入密码。查询和选图复用同一个数据库 session。本地 `config.toml` 明文保存连接信息（包括 `NEBULA_PASSWORD`），不要共享文件，也不要提交真实值。默认只读。

之后直接说“使用 Nebula MCP，执行 MATCH (n) RETURN n LIMIT 20”。缺图时先提示选择，用户给出图名后执行 `SESSION SET GRAPH` 并自动续跑原查询。

查询成功后，支持 MCP Apps 的客户端可以显示图、表格、Vega-Lite 图表、事实解释和实际执行 GQL；不支持 UI 的客户端仍可读取相同的 structured content。
