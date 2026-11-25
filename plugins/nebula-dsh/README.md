# 悦数图数据库（NebulaGraph 5.x）

`dsh-nebula-mcp` 为 DeepSeek Harness（DSH）提供悦数图数据库的只读 GQL 查询。当前 SDK 面向悦数图数据库 5.3，不支持开源版 NebulaGraph 3.x。

## 安装

1. 使用 DSH `0.2.2-rc.5` 或符合 `^0.2.2-rc.5` 的更新版本，在 **插件 → 发现** 从 [MuYiYong/dsh-marketplace](https://github.com/MuYiYong/dsh-marketplace) 安装 `dsh-nebula-mcp`。如未看到 **发现**，先在 **实验性插件** 启用 **自定义插件索引**。
2. 组合包不含 Python 运行时。请等待 [nebula-mcp Releases](https://github.com/MuYiYong/nebula-mcp/releases) 发布明确包含 DSH 支持和 `--mode runtime` 的版本。以运行 DSH 的系统用户下载该 Release 的 `install.py` 和 `SHA256SUMS`，[核对安装器的 SHA-256](https://github.com/MuYiYong/nebula-mcp/blob/main/docs/configuration.md#dsh-runtime) 后，用 Python 3.10+ 另行安装：macOS / Linux 运行 `python3 install.py --mode runtime`，Windows PowerShell 运行 `py -3 .\install.py --mode runtime`。该模式不检测 Codex，不修改 Codex 的注册、插件或已保存的配置。

## 配置和使用

- 打开 DSH **设置**，选择 **Agent 预设** 正下方的 **悦数图数据库（NebulaGraph 5.x）**。每个 DSH 配置档仅支持一个只读连接，该档中的所有 Agent 预设共用。
- 填写地址（`HOST:PORT`，多个地址用逗号分隔）、用户名、密码和 TLS，勾选 **在当前配置档启用 MCP** 并保存。已保存的密码只留在本机 DSH 凭据库，输入框仍为空。修改地址、用户名或 TLS 时必须重新输入密码。请勿在对话中发送密码。
- 安装或更新运行时后，在状态卡中点击 **检查运行时 / 重启 MCP**，让 DSH 重新检查安装路径。**MCP 已就绪**仅表示 MCP 工具可用；在新会话里挂载 `nebula_graph`，调用 `nebula_test_connection` 检查数据库连通性。
- 仅停用时可关闭启用开关；如需删除已保存的连接和密码，先点击 **移除连接**，再按需卸载组合包。同一用户的 Codex 若也通过本项目安装器安装，可能仍在使用共享运行时；请勿仅为移除 DSH 而删除它。

[完整安装和故障排查](https://github.com/MuYiYong/nebula-mcp#deepseek-harness)
