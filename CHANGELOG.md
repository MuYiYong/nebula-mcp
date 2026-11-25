# Changelog

## Unreleased

- Codex marketplace users can ask for “配置悦数连接” to open a temporary setup page in their system browser. Credentials no longer go through Codex tool arguments in marketplace mode. The tested connection takes effect immediately and is saved on this machine; a failed test leaves the working connection untouched. Existing saved connections are loaded without migration. Standalone Codex and DeepSeek Harness configuration are unchanged.
- The Codex standalone `nebula` MCP registration (`install.py --mode mcp`) now explicitly prefills the editable TLS field as `false`. The connection address, username, and password start blank, while the timeout, read-only setting, and environment name retain their defaults. The installer can add the native entry alongside an existing marketplace installation, without replacing an unrelated native server. The setup guide distinguishes the native editor from the marketplace plugin entry, which cannot expose custom setting fields or placeholders.
- Codex marketplace connections are stored in the managed runtime’s `codex-connections.json` (mode 0600 on POSIX). The launcher reloads the active connection after a restart; switching an existing named environment also persists the selection. Installer-managed `config.toml` and `NEBULA_ENVIRONMENTS` remain supported in ordinary MCP mode.
- Added the Codex plugin launcher (`plugins/nebula-mcp/bin/launch.mjs`). It reuses the same managed runtime as the DSH bundle, prepares a portable Python in the background on first use, and then starts the stdio MCP server. The Codex plugin can now be installed from the new [codex-marketplace](https://github.com/MuYiYong/codex-marketplace) with `codex plugin add nebula-mcp@codex-marketplace`; the release ZIP and installer plugin mode remain supported.
- The Codex plugin MCP mapping now uses `node bin/launch.mjs` with the plugin root as cwd. Updated the installer archive allowlist, release packaging, and tests for the two new launcher files.
- Added the `dsh-nebula-mcp` bundle for DeepSeek Harness `^0.2.2-rc.5`, to be distributed through the [MuYiYong marketplace](https://github.com/MuYiYong/dsh-marketplace). It adds one profile-wide, read-only YueShu graph database (悦数图数据库, NebulaGraph 5.x) connection below Agent presets, with the password held in the local DSH credential store. The current SDK targets YueShu 5.3; it does not support open-source NebulaGraph 3.x.
- Added a separate `--mode runtime` installation path on macOS, Linux, and Windows. It verifies the release wheel and installs the shared Python runtime without detecting Codex or changing its registrations, plugin state, or saved configuration. Existing Codex installation modes remain unchanged. Use a release that includes the new mode and DSH runtime entry point.

## 2026-09-26

- Simplified the README around installation, configuration, usage, upgrade, and removal; moved advanced configuration and maintainer guidance to separate documents.
- Removed unused one-hop expansion backend and frontend merge code, plus an obsolete design draft. Kept all 12 published tools, documenting optional environment tools and the legacy graph-rendering entry.

- Query results include automatic PROFILE metrics while preserving the original GQL statement for display and copying.
- Graph inspection shows schema-backed node primary keys, edge endpoints and direction, and explicit multiedge keys. Large integers retain precision in the browser.
- Property values use compact rows; the copy icon confirms completion. Removed PROFILE JSON disclosure and one-hop expansion.
- Result explanation instructions emphasize meaning, evidence, insights, and sample limitations.
- Independent Codex MCP registrations support user-defined environment names and separate connection settings; one process can also select configured environments.
- The managed installer supports local release folders and explicit connection setup, status, and clearing.
- Main-branch pushes now build and publish calendar-named GitHub Releases after verification. Stable download links simplify installation and sharing.

The release targets YueShu 5.3. Client support for embedded MCP Apps varies; browser preview validation does not establish rendering support in every client.
