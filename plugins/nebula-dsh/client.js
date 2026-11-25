window.__ModuleLoader__.load({
  id: 'dsh-nebula-mcp',
  factory(require) {
    const { createElement: h, useEffect, useId, useRef, useState } = require('react')
    const id = 'nebula-graph'
    const endpoint = '/api/nebula-dsh/settings'
    const testEndpoint = '/api/nebula-dsh/test'
    const zh = {
      title: 'NebulaGraph', nav: 'NebulaGraph', readOnly: '只读',
      intro: '保存多个只读连接，选择一个作为当前连接。所有 Agent 预设共用。',
      connection: '连接', connectionHint: '选择当前连接；点击连接可展开设置。',
      switchTo: '切换到此连接', expand: '展开设置', collapse: '收起设置',
      noActiveHint: '当前没有生效的连接；选择任意连接即可启用。',
      current: '当前', newConnection: '新建连接',
      empty: '还没有保存的连接。点击「新建连接」添加。',
      editTitle: '连接设置',
      connectionName: '连接名称', nameHint: '例如：生产库',
      addresses: '数据库地址', addressHint: 'HOST:PORT；多个地址用逗号分隔。',
      username: '用户名', password: '密码', passwordHint: '只保存在本机，不会回显。',
      keep: '留空保留已保存的密码；修改地址、用户名或 TLS 时需重新输入。',
      passwordSaved: '已保存', tls: '启用 TLS',
      save: '保存', saving: '保存中…', discard: '放弃更改', cancel: '取消',
      test: '测试连接', testing: '测试中…', testOk: '连接正常', testFailed: '连接失败',
      testUnavailable: '无法执行连接测试。', saveFailed: '保存失败', version: '服务器版本',
      remove: '移除', removing: '移除中…',
      removeHint: '移除后，该连接及其密码将从本机删除。',
      removeActiveHint: '这是当前连接；移除后将没有生效的连接。',
      dirtyHint: '更改会自动保存；完成或放弃后才能展开其他连接。',
      cap: '最多可保存 20 个连接。',
      loading: '正在载入连接设置…',
      offline: '无法连接设置服务。', offlineStale: '显示的是上次读取的设置。',
      retry: '重试', retrying: '重试中…', reload: '重新载入',
      switched: '已切换', saved: '已保存', removed: '已移除', created: '已创建', enabled: '已保存并启用',
      synced: '已同步', unsynced: '未保存', staleState: '已过期', inactive: '未启用',
      checkingState: '载入中', unavailable: '不可用', failedState: '操作失败',
      switching: '正在切换…',
      errors: {
        name: '请输入 1 至 64 个字符的连接名称。', 'duplicate-name': '已存在同名连接，请换一个名称。',
        limit: '已达到 20 个连接的上限。', 'not-found': '这条连接已不存在，请重新载入。',
        addresses: '请输入有效地址：HOST:PORT，端口为 1–65535。', username: '请输入有效用户名。',
        password: '请输入有效密码（不含控制字符或首尾空格）。', 'new-password': '更改地址、用户名或 TLS 时，请重新输入密码。',
        conflict: '设置已在其他窗口更改。请重新载入设置后再保存。',
        cleanup: '连接设置已更新，但清理旧凭据时出错。请重新载入设置。',
        generic: '无法访问悦数图数据库设置。确认插件已启用后重试。',
      },
    }
    const en = {
      title: 'NebulaGraph', nav: 'NebulaGraph', readOnly: 'Read only',
      intro: 'Save multiple read-only connections and choose one as the current connection. Every Agent preset shares it.',
      connection: 'Connections', connectionHint: 'Choose the current connection; click a connection to edit it.',
      switchTo: 'Set as current connection', expand: 'Edit connection', collapse: 'Close settings',
      noActiveHint: 'No connection is active. Select one below to enable it.',
      current: 'Current', newConnection: 'New connection',
      empty: 'No saved connections yet. Use New connection to add one.',
      editTitle: 'Connection settings',
      connectionName: 'Connection name', nameHint: 'e.g. Production',
      addresses: 'Database addresses', addressHint: 'HOST:PORT; separate multiple addresses with commas.',
      username: 'Username', password: 'Password', passwordHint: 'Stored locally and never shown.',
      keep: 'Leave blank to keep the saved password. Re-enter it after changing addresses, username, or TLS.',
      passwordSaved: 'Saved', tls: 'Enable TLS',
      save: 'Save', saving: 'Saving…', discard: 'Discard changes', cancel: 'Cancel',
      test: 'Test connection', testing: 'Testing…', testOk: 'Connection OK', testFailed: 'Connection failed',
      testUnavailable: 'Could not run the connection test.', saveFailed: 'Save failed', version: 'Server version',
      remove: 'Remove', removing: 'Removing…',
      removeHint: 'Removing deletes this connection and its password from this machine.',
      removeActiveHint: 'This is the current connection. Removing it leaves no active connection.',
      dirtyHint: 'Changes save automatically; finish or discard them before opening another connection.',
      cap: 'You can save up to 20 connections.',
      loading: 'Loading connection settings…',
      offline: 'Could not reach the settings service.', offlineStale: 'Showing the last loaded settings.',
      retry: 'Retry', retrying: 'Retrying…', reload: 'Reload',
      switched: 'Switched', saved: 'Saved', removed: 'Removed', created: 'Created', enabled: 'Saved and enabled',
      synced: 'Synced', unsynced: 'Unsaved', staleState: 'Out of date', inactive: 'Not enabled',
      checkingState: 'Loading', unavailable: 'Unavailable', failedState: 'Action failed',
      switching: 'Switching…',
      errors: {
        name: 'Enter a connection name of 1–64 characters.', 'duplicate-name': 'A connection with this name already exists.',
        limit: 'You have reached the 20-connection limit.', 'not-found': 'This connection no longer exists. Reload the settings.',
        addresses: 'Enter valid HOST:PORT addresses with ports from 1–65535.', username: 'Enter a valid username.',
        password: 'Enter a valid password without control characters or leading or trailing spaces.', 'new-password': 'Re-enter the password when changing addresses, username, or TLS.',
        conflict: 'Settings changed in another window. Reload them before saving.',
        cleanup: 'Settings changed, but the old credential could not be removed. Reload settings.',
        generic: 'Could not access YueShu settings. Check that the plugin is enabled and try again.',
      },
    }
    for (const messages of [zh, en]) {
      for (const [key, value] of Object.entries(messages.errors)) messages['errors.' + key] = value
    }
    const errorCodes = new Set([...Object.keys(en.errors), 'forbidden', 'store'])
    delete zh.errors
    delete en.errors
    Object.assign(zh, { 'errors.forbidden': '只有已登录的 DSH 所有者可管理此连接。', 'errors.store': '无法读取或更新本机连接设置。' })
    Object.assign(en, { 'errors.forbidden': 'Only the signed-in DSH owner can manage this connection.', 'errors.store': 'Could not read or update local connection settings.' })
    const css = `
      .nebula-settings {
        box-sizing: border-box;
        inline-size: 100%;
        max-inline-size: 760px;
        margin-inline: auto;
        padding: 0 0 24px;
        color: var(--dsw-alias-label-primary);
        font-size: 14px;
        line-height: 1.6;
        container: nebula-settings / inline-size;
      }
      .nebula-settings *, .nebula-settings *::before, .nebula-settings *::after { box-sizing: border-box; }
      .nebula-settings h1, .nebula-settings h2, .nebula-settings h3, .nebula-settings p { margin: 0; }
      .ns-hero { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 12px; padding: 4px 0 18px; }
      .ns-mark {
        display: grid; place-items: center; flex: none; inline-size: 38px; block-size: 38px;
        border: 0.5px solid color-mix(in srgb, var(--dsw-alias-brand-primary) 22%, var(--dsw-alias-border-l1));
        border-radius: 11px;
        background: color-mix(in srgb, var(--dsw-alias-brand-primary) 10%, var(--dsw-alias-bg-layer-1));
        color: var(--dsw-alias-brand-primary);
      }
      .ns-heroText { flex: 1 1 16rem; min-inline-size: 0; }
      .ns-kicker {
        margin-block-end: 2px;
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        font-size: 9.5px; line-height: 14px; letter-spacing: 0.14em; text-transform: uppercase;
        color: var(--dsw-alias-label-tertiary);
      }
      .ns-title { font-size: 18px; line-height: 26px; font-weight: 500; overflow-wrap: anywhere; }
      .ns-intro { max-inline-size: 38rem; margin-block-start: 2px; font-size: 13px; line-height: 20px; color: var(--dsw-alias-label-secondary); }
      .ns-heroAside { display: flex; flex: none; flex-direction: column; align-items: flex-end; gap: 6px; margin-inline-start: auto; padding-block-start: 2px; }
      .ns-tag {
        display: inline-flex; align-items: center; block-size: 20px; padding: 0 6px;
        border: 0.5px solid var(--dsw-alias-border-l1); border-radius: 4px;
        font-size: 11px; line-height: 16px; color: var(--dsw-alias-label-tertiary); white-space: nowrap;
      }
      .ns-status { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; line-height: 16px; color: var(--dsw-alias-label-tertiary); white-space: nowrap; }
      .ns-dot { flex: none; inline-size: 6px; block-size: 6px; border-radius: 50%; background: currentColor; }
      .ns-status[data-tone=success] { color: color-mix(in srgb, var(--dsw-alias-state-success-primary) 68%, var(--dsw-alias-label-primary)); }
      .ns-status[data-tone=warn] { color: var(--dsw-alias-label-secondary); }
      .ns-status[data-tone=error] { color: var(--dsw-alias-state-error-primary); }
      .ns-status[data-tone=progress] { color: var(--dsw-alias-label-secondary); }
      .ns-status[data-tone=progress] .ns-dot { background: var(--dsw-alias-brand-primary); }
      .ns-body { display: flex; flex-direction: column; gap: 16px; }
      .ns-card {
        position: relative; overflow: hidden;
        border: 0.5px solid var(--dsw-alias-border-l1); border-radius: 8px;
        background: var(--dsw-alias-bg-layer-1);
      }
      .ns-card::before {
        content: ''; position: absolute; inset: 0 0 auto; z-index: 1; block-size: 1px;
        background: linear-gradient(90deg, color-mix(in srgb, var(--dsw-alias-label-primary) 18%, transparent), transparent 58%);
        pointer-events: none;
      }
      .ns-cardHead { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 14px 16px 10px; }
      .ns-connectionsHead { border-block-end: 0.5px solid var(--dsw-alias-border-l1); }
      .ns-cardHeadMain { flex: 1 1 14rem; min-inline-size: 0; }
      .ns-sectionTitle { font-size: 14px; line-height: 20px; font-weight: 600; }
      .ns-hint { margin-block-start: 2px; font-size: 12px; line-height: 18px; color: var(--dsw-alias-label-tertiary); }
      .ns-cap { flex: none; }
      .ns-radioList { display: flex; flex-direction: column; }
      .ns-radioItem { --ns-acc: var(--dsw-alias-brand-primary); }
      .ns-radioItem[data-accent="1"] { --ns-acc: color-mix(in srgb, #5b9dff 70%, var(--dsw-alias-label-primary)); }
      .ns-radioItem[data-accent="2"] { --ns-acc: color-mix(in srgb, #3fbf7f 70%, var(--dsw-alias-label-primary)); }
      .ns-radioItem[data-accent="3"] { --ns-acc: color-mix(in srgb, #e0a33a 72%, var(--dsw-alias-label-primary)); }
      .ns-radioItem[data-accent="4"] { --ns-acc: color-mix(in srgb, #a78bfa 72%, var(--dsw-alias-label-primary)); }
      .ns-radioItem[data-accent="5"] { --ns-acc: color-mix(in srgb, #f08fb0 72%, var(--dsw-alias-label-primary)); }
      .ns-radioItem[data-accent="6"] { --ns-acc: color-mix(in srgb, #4fd1c5 72%, var(--dsw-alias-label-primary)); }
      .ns-radioItem + .ns-radioItem { border-block-start: 0.5px solid var(--dsw-alias-border-l1); }
      .ns-radioRow {
        display: flex; align-items: center; gap: 10px;
        padding: 10px 16px 10px 13px; border-inline-start: 3px solid var(--ns-acc);
      }
      .ns-radioRow[data-current] { background: color-mix(in srgb, var(--ns-acc) 7%, transparent); }
      .ns-radioRow[data-expanded] { background: color-mix(in srgb, var(--ns-acc) 10%, transparent); }
      .ns-radio { flex: none; inline-size: 16px; block-size: 16px; margin: 0; accent-color: var(--ns-acc); cursor: pointer; }
      .ns-radio:disabled { opacity: 0.5; cursor: not-allowed; }
      .ns-radio:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; }
      .ns-rowToggle {
        display: flex; flex: 1; align-items: center; gap: 8px; min-inline-size: 0;
        margin: 0; padding: 0; border: 0; background: none; color: inherit;
        font: inherit; text-align: start; cursor: pointer;
      }
      .ns-rowToggle:disabled { cursor: default; }
      .ns-rowToggle:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; border-radius: 6px; }
      .ns-rowText { display: flex; flex: 1; flex-direction: column; gap: 1px; min-inline-size: 0; }
      .ns-radioName { font-size: 14px; line-height: 20px; font-weight: 500; overflow-wrap: anywhere; }
      .ns-radioMeta {
        display: flex; align-items: baseline; gap: 4px; min-inline-size: 0;
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        font-size: 11px; line-height: 16px; color: var(--dsw-alias-label-tertiary);
      }
      .ns-user {
        flex: 0 0 auto; max-inline-size: 40%; overflow: hidden;
        color: var(--dsw-alias-label-secondary);
        text-overflow: ellipsis; white-space: nowrap;
      }
      .ns-sep { flex: none; opacity: 0.6; }
      .ns-radioAddr {
        flex: 1 1 auto; min-inline-size: 0; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap;
      }
      .ns-version { flex: none; font-variant-numeric: tabular-nums; }
      .ns-chevron { flex: none; color: var(--dsw-alias-label-tertiary); transition: transform 0.15s ease; }
      .ns-rowToggle[aria-expanded=true] .ns-chevron { transform: rotate(180deg); }
      .ns-iconButton {
        display: inline-flex; flex: none; align-items: center; justify-content: center;
        inline-size: 30px; block-size: 30px; padding: 0;
        border: 0.5px solid transparent; border-radius: 8px; background: transparent;
        color: var(--dsw-alias-label-tertiary); cursor: pointer;
      }
      .ns-iconButton:disabled { opacity: 0.4; cursor: not-allowed; }
      .ns-iconButton:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; }
      .ns-confirmRow {
        display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
        padding: 10px 16px 12px; border-block-start: 0.5px solid var(--dsw-alias-border-l1);
        background: color-mix(in srgb, var(--dsw-alias-state-error-primary) 5%, transparent);
        font-size: 12px; line-height: 18px; color: var(--dsw-alias-label-secondary);
      }
      .ns-confirmText { flex: 1 1 14rem; min-inline-size: 0; }
      .ns-confirmName { font-weight: 600; color: var(--dsw-alias-label-primary); }
      .ns-actions { display: flex; flex: none; flex-wrap: wrap; gap: 6px; margin-inline-start: auto; }
      .ns-empty { padding: 22px 16px; font-size: 13px; line-height: 20px; color: var(--dsw-alias-label-tertiary); text-align: center; }
      .ns-editor {
        border-block-start: 0.5px solid var(--ns-acc);
        background: color-mix(in srgb, var(--ns-acc) 4%, var(--dsw-alias-bg-layer-2));
        padding: 12px 16px 16px;
      }
      .ns-editorForm { display: flex; flex-direction: column; gap: 12px; }
      .ns-draftHead { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 12px 16px 10px; }
      .ns-draftHead .ns-cardHeadMain { flex: 1 1 14rem; min-inline-size: 0; }
      .ns-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px 14px; }
      .ns-field { display: flex; flex-direction: column; gap: 5px; min-inline-size: 0; }
      .ns-label { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; line-height: 18px; font-weight: 500; color: var(--dsw-alias-label-secondary); }
      .ns-inlineTag { block-size: auto; padding: 0 5px; font-size: 10px; line-height: 15px; }
      .ns-input {
        box-sizing: border-box; inline-size: 100%; block-size: 34px; padding: 0 10px;
        border: 0.5px solid var(--dsw-alias-border-l2); border-radius: 8px;
        background: var(--dsw-alias-bg-base); color: var(--dsw-alias-label-primary);
        font: inherit; font-size: 13px; line-height: 20px;
      }
      .ns-input::placeholder { color: var(--dsw-alias-label-tertiary); }
      .ns-input:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 1px; }
      .ns-input[aria-invalid=true] { border-color: var(--dsw-alias-state-error-primary); }
      .ns-input:disabled { opacity: 0.6; cursor: not-allowed; }
      .ns-fieldHint { font-size: 11.5px; line-height: 17px; color: var(--dsw-alias-label-tertiary); overflow-wrap: anywhere; }
      .ns-fieldError { font-size: 11.5px; line-height: 17px; color: var(--dsw-alias-state-error-primary); overflow-wrap: anywhere; }
      .ns-check { display: flex; align-items: center; gap: 8px; min-block-size: 34px; font-size: 13px; cursor: pointer; }
      .ns-check input { flex: none; inline-size: 16px; block-size: 16px; margin: 0; accent-color: var(--dsw-alias-brand-primary); }
      .ns-check input:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; }
      .ns-check input:disabled { opacity: 0.5; cursor: not-allowed; }
      .ns-editorFoot { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; }
      .ns-editorSpacer { flex: 1 1 auto; }
      .ns-editorHint { flex: 1 1 100%; min-inline-size: 0; }
      .ns-saveState {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 11.5px; line-height: 16px; color: var(--dsw-alias-label-tertiary);
      }
      .ns-saveState[data-tone=success] { color: color-mix(in srgb, var(--dsw-alias-state-success-primary) 68%, var(--dsw-alias-label-primary)); }
      .ns-saveState[data-tone=warn] { color: var(--dsw-alias-label-secondary); }
      .ns-saveState[data-tone=error] { color: var(--dsw-alias-state-error-primary); }
      .ns-saveState[data-tone=progress] { color: var(--dsw-alias-label-secondary); }
      .ns-saveState[data-tone=progress] .ns-dot { background: var(--dsw-alias-brand-primary); }
      .ns-testResult {
        display: flex; gap: 6px; align-items: flex-start;
        margin-block-start: 2px; font-size: 12px; line-height: 18px;
        color: var(--dsw-alias-label-secondary); overflow-wrap: anywhere;
      }
      .ns-testResult[data-tone=success] { color: color-mix(in srgb, var(--dsw-alias-state-success-primary) 68%, var(--dsw-alias-label-primary)); }
      .ns-testResult[data-tone=error] { color: var(--dsw-alias-state-error-primary); }
      .ns-testResult[data-tone=progress] { color: var(--dsw-alias-label-tertiary); }
      .ns-linkButton {
        padding: 0; border: 0; background: none; color: var(--dsw-alias-label-secondary);
        font: inherit; font-size: 12px; text-decoration: underline; cursor: pointer;
      }
      .ns-linkButton:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; }
      .ns-button {
        display: inline-flex; flex: none; align-items: center; justify-content: center; gap: 6px;
        block-size: 32px; padding: 0 14px; border: 0.5px solid var(--dsw-alias-border-l2);
        border-radius: 16px; background: transparent; color: var(--dsw-alias-label-primary);
        font: inherit; font-size: 13px; line-height: 20px; white-space: nowrap; cursor: pointer;
      }
      .ns-button:focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; }
      .ns-button:disabled { opacity: 0.45; cursor: not-allowed; }
      .ns-small { block-size: 28px; padding: 0 10px; border-radius: 14px; font-size: 12px; line-height: 18px; }
      .ns-primary { border-color: transparent; background: var(--dsw-alias-label-primary); color: var(--dsw-alias-bg-base); }
      .ns-primary:disabled { opacity: 0.35; }
      .ns-danger {
        border-color: color-mix(in srgb, var(--dsw-alias-state-error-primary) 32%, var(--dsw-alias-border-l2));
        background: color-mix(in srgb, var(--dsw-alias-state-error-primary) 8%, transparent);
        color: var(--dsw-alias-state-error-primary);
      }
      .ns-banner {
        display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
        padding: 12px 14px; border: 0.5px solid var(--dsw-alias-border-l1); border-radius: 8px;
        background: var(--dsw-alias-bg-layer-2);
        font-size: 12.5px; line-height: 19px; color: var(--dsw-alias-label-secondary);
      }
      .ns-bannerText { flex: 1 1 16rem; min-inline-size: 0; }
      .ns-bannerText .ns-hint { display: block; margin-block-start: 2px; }
      .ns-banner > .ns-button { margin-inline-start: auto; }
      .ns-loading { display: flex; align-items: center; gap: 8px; padding: 22px 16px; font-size: 13px; line-height: 20px; color: var(--dsw-alias-label-tertiary); }
      .ns-spinner {
        flex: none; inline-size: 14px; block-size: 14px; border: 2px solid var(--dsw-alias-border-l2);
        border-block-start-color: var(--dsw-alias-brand-primary); border-radius: 50%;
        animation: ns-spin 0.8s linear infinite;
      }
      @keyframes ns-spin { to { transform: rotate(360deg); } }
      @container nebula-settings (min-width: 34rem) {
        .ns-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .ns-wide { grid-column: 1 / -1; }
      }
      @media (hover: hover) {
        .ns-button:not(:disabled):hover { background: color-mix(in srgb, var(--dsw-alias-label-primary) 6%, transparent); }
        .ns-primary:not(:disabled):hover { opacity: 0.88; }
        .ns-danger:not(:disabled):hover { background: color-mix(in srgb, var(--dsw-alias-state-error-primary) 14%, transparent); }
        .ns-iconButton:not(:disabled):hover { background: color-mix(in srgb, var(--dsw-alias-state-error-primary) 8%, transparent); color: var(--dsw-alias-state-error-primary); }
        .ns-radioRow:not([data-current]):not([data-expanded]):not([data-disabled]):hover { background: color-mix(in srgb, var(--dsw-alias-label-primary) 3%, transparent); }
      }
      @media (pointer: coarse) {
        .ns-button { block-size: 40px; }
        .ns-small { block-size: 36px; }
        .ns-input { block-size: 40px; }
        .ns-radio { inline-size: 18px; block-size: 18px; }
        .ns-check { min-block-size: 40px; }
      }
      @media (prefers-reduced-motion: reduce) {
        .ns-spinner { animation: none; }
        .ns-chevron { transition: none; }
      }
    `
    const EMPTY_FORM = { name: '', addresses: '', username: '', password: '', tls: false }
    const VERSION_STORE = 'dsh-nebula-mcp/versions-v1'

    function readStoredVersions() {
      try {
        if (typeof window === 'undefined' || !window.localStorage) return {}
        const raw = window.localStorage.getItem(VERSION_STORE)
        if (!raw) return {}
        const parsed = JSON.parse(raw)
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
        const stored = {}
        for (const [key, value] of Object.entries(parsed)) {
          if (key === 'new' || typeof value !== 'string') continue
          const version = value.trim().slice(0, 64)
          if (key && version) stored[key] = version
        }
        return stored
      } catch {
        return {}
      }
    }
    const formOf = connection => connection === null || connection === undefined ? { ...EMPTY_FORM } : {
      name: connection.name, addresses: connection.addresses, username: connection.username,
      password: '', tls: connection.tls,
    }
    const sameForm = (left, right) => left.name === right.name && left.addresses === right.addresses &&
      left.username === right.username && left.password === right.password && left.tls === right.tls
    const fieldForError = key => key === 'new-password' ? 'password' : key === 'duplicate-name' ? 'name' :
      ['name', 'addresses', 'username', 'password'].includes(key) ? key : null

    async function requestTest(signal, payload) {
      const response = await fetch(testEndpoint, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal,
        headers: { 'content-type': 'application/json', 'x-dsh-nebula-settings': '1' },
        body: JSON.stringify(payload),
      })
      const value = await response.json().catch(() => null)
      if (!response.ok) throw new Error(typeof value?.error === 'string' ? value.error : 'test')
      if (typeof value?.ok !== 'boolean') throw new Error('test')
      return value
    }

    const accentFor = connectionId => {
      if (connectionId === null || connectionId === undefined || connectionId === 'new') return 0
      let hash = 0
      for (let index = 0; index < connectionId.length; index++) {
        hash = (hash * 31 + connectionId.charCodeAt(index)) >>> 0
      }
      return hash % 6 + 1
    }

    async function request(signal, body) {
      const response = await fetch(endpoint, {
        method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal,
        ...(body && { headers: { 'content-type': 'application/json', 'x-dsh-nebula-settings': '1' }, body: JSON.stringify(body) }),
      })
      const value = await response.json()
      if (!response.ok) throw new Error(typeof value?.error === 'string' ? value.error : 'generic')
      if (typeof value?.revision !== 'string' || !Array.isArray(value.connections)) throw new Error('generic')
      return value
    }

    function Icon({ size = 16 }) {
      return h('svg', { width: size, height: size, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', 'aria-hidden': true },
        h('path', { d: 'm6 12 4-6 4 7z', strokeWidth: '1.3' }),
        [ [10, 5], [5, 13], [15, 14] ].map(([cx, cy]) => h('circle', { key: cx, cx, cy, r: '2', fill: 'currentColor', stroke: 'none' })))
    }

    function Trash() {
      return h('svg', {
        width: 15, height: 15, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
        strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true,
      }, h('path', { d: 'M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-9 0 1 12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2l1-12' }))
    }

    function Chevron() {
      return h('svg', {
        className: 'ns-chevron', width: 14, height: 14, viewBox: '0 0 24 24',
        fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
        strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true,
      }, h('path', { d: 'm6 9 6 6 6-6' }))
    }

    function Page({ t }) {
      const prefix = useId()
      const lifetime = useRef(null)
      const inFlight = useRef(false)
      const generation = useRef(0)
      const initialized = useRef(false)
      const formRef = useRef(null)
      const newButton = useRef(null)
      const trashRefs = useRef(new Map())
      const toggleRefs = useRef(new Map())
      const editToken = useRef(0)
      const testToken = useRef(0)

      const [base, setBase] = useState(null)
      const [live, setLive] = useState(null)
      const [offline, setOffline] = useState('')
      const [retrying, setRetrying] = useState(false)
      const [busy, setBusy] = useState('')
      const [note, setNote] = useState('')
      const [error, setError] = useState('')
      const [expandedId, setExpandedId] = useState(null)
      const [form, setForm] = useState(EMPTY_FORM)
      const [baseline, setBaseline] = useState(EMPTY_FORM)
      const [confirm, setConfirm] = useState(null)
      const [testState, setTestState] = useState(null)
      const [versions, setVersions] = useState(readStoredVersions)
      const [passwordCommitted, setPasswordCommitted] = useState(false)
      const [reload, setReload] = useState(0)

      const connections = base?.connections ?? []
      const active = connections.find(row => row.id === base?.activeId) ?? null
      const editing = expandedId !== null && expandedId !== 'new'
        ? connections.find(row => row.id === expandedId) ?? null
        : null
      const draft = expandedId === 'new'
      const expanded = editing !== null || draft
      const dirty = expanded && !sameForm(form, baseline)
      const targetChanged = Boolean(editing && (
        form.addresses.trim() !== editing.addresses ||
        form.username.trim() !== editing.username ||
        form.tls !== editing.tls
      ))
      const passwordNeeded = editing ? !editing.passwordSaved || targetChanged : true
      const passwordReady = (passwordNeeded ? form.password !== '' : true) && (form.password === '' || passwordCommitted)
      const valid = form.name.trim() !== '' && form.addresses.trim() !== '' &&
        form.username.trim() !== '' && passwordReady
      const changedElsewhere = Boolean(base && live && base.revision !== live.revision)
      const stale = changedElsewhere || ['conflict', 'cleanup', 'not-found'].includes(error)
      const blocked = Boolean(busy) || stale
      const canCreate = connections.length < 20
      const loading = !base && !offline
      const err = key => t('errors.' + (errorCodes.has(key) ? key : 'generic'))
      const dirtyId = prefix + '-dirty'

      function clearFeedback() { setError(''); setNote('') }

      function resetEditorState() {
        editToken.current++
        testToken.current++
        setPasswordCommitted(false)
        setTestState(null)
      }

      function rememberVersion(key, version) {
        const value = typeof version === 'string' && version.trim() ? version.trim().slice(0, 64) : null
        setVersions(current => ({ ...current, [key]: value }))
      }

      function forgetVersion(key) {
        setVersions(current => {
          if (!(key in current)) return current
          const next = { ...current }
          delete next[key]
          return next
        })
      }

      function focusName(select) {
        requestAnimationFrame(() => {
          const input = formRef.current?.elements.namedItem('name')
          input?.focus()
          if (select && typeof input?.select === 'function') input.select()
        })
      }

      function openEditor(connectionId) {
        const row = connections.find(item => item.id === connectionId)
        if (!row || blocked || dirty) return
        const values = formOf(row)
        setExpandedId(connectionId)
        setForm(values)
        setBaseline(values)
        setConfirm(null)
        resetEditorState()
        clearFeedback()
        focusName()
      }

      function nextDraftName() {
        const base = t('newConnection')
        const used = new Set(connections.map(row => row.name.normalize('NFC').toLocaleLowerCase()))
        if (!used.has(base.toLocaleLowerCase())) return base
        for (let index = 2; index < 100; index++) {
          const candidate = base + ' ' + index
          if (!used.has(candidate.toLocaleLowerCase())) return candidate
        }
        return base.slice(0, 64)
      }

      async function openNew() {
        if (!canCreate || blocked || draft) return
        if (dirty) {
          if (!valid) {
            focusFormField()
            return
          }
          const token = editToken.current
          if (!(await persist())) return
          if (editToken.current !== token) return
        }
        setExpandedId('new')
        setForm({ ...EMPTY_FORM, name: nextDraftName() })
        setBaseline({ ...EMPTY_FORM })
        setConfirm(null)
        resetEditorState()
        clearFeedback()
        focusName(true)
      }

      function closeEditor(focus) {
        if (expandedId === 'new') forgetVersion('new')
        setExpandedId(null)
        setConfirm(null)
        clearFeedback()
        setForm({ ...EMPTY_FORM })
        setBaseline({ ...EMPTY_FORM })
        resetEditorState()
        if (focus) requestAnimationFrame(focus)
      }

      function toggleRow(connectionId) {
        if (blocked || dirty) return
        if (expandedId === connectionId) {
          closeEditor(() => toggleRefs.current.get(connectionId)?.focus())
          return
        }
        openEditor(connectionId)
      }

      function removeDraft() {
        if (!draft || busy !== '') return
        closeEditor(() => newButton.current?.focus())
      }

      function set(field, value) {
        editToken.current++
        setForm(current => ({ ...current, [field]: value }))
        if (['addresses', 'username', 'password', 'tls'].includes(field)) {
          const key = editing?.id ?? (draft ? 'new' : null)
          if (key !== null) forgetVersion(key)
        }
        if (field === 'password') setPasswordCommitted(false)
        if (error !== '' && !['conflict', 'cleanup', 'not-found'].includes(error)) setError('')
        if (note !== '') setNote('')
        if (confirm !== null) setConfirm(null)
        if (testState !== null) {
          testToken.current++
          setTestState(null)
        }
      }

      function discard() {
        if (blocked) return
        editToken.current++
        setForm({ ...baseline })
        setPasswordCommitted(false)
        if (!['conflict', 'cleanup', 'not-found'].includes(error)) setError('')
        setNote('')
      }

      function select(connectionId) {
        if (!base || blocked || base.activeId === connectionId) return
        setConfirm(null)
        void mutate('activate', { id: connectionId })
      }

      function toggleConfirm(connectionId) {
        if (blocked || dirty) return
        setConfirm(current => current === connectionId ? null : connectionId)
        clearFeedback()
      }

      function removeRow(connectionId) {
        setConfirm(null)
        void mutate('clear', { id: connectionId })
      }

      async function persist() {
        if (inFlight.current || !base || !editing || !valid || !dirty || busy !== '' || stale || !lifetime.current) return false
        const signal = lifetime.current.signal
        const snapshot = { ...form }
        const token = editToken.current
        const id = editing.id
        const password = passwordCommitted ? snapshot.password : ''
        inFlight.current = true
        generation.current++
        setBusy('save')
        setError('')
        setNote('')
        try {
          const value = await request(signal, {
            action: 'save', revision: base.revision, id,
            name: snapshot.name, addresses: snapshot.addresses, username: snapshot.username,
            password, tls: snapshot.tls,
          })
          if (signal.aborted) return false
          setLive(value)
          setOffline('')
          setBase(value)
          testToken.current++
          setTestState(null)
          const row = value.connections.find(item => item.id === id)
          if (!row) return false
          const values = formOf(row)
          if (editToken.current === token) {
            setForm(values)
            setBaseline(values)
          } else {
            setBaseline({ ...values })
            setForm(current => current.password !== '' && current.password === snapshot.password
              ? { ...current, password: '' }
              : current)
          }
          setPasswordCommitted(false)
          return true
        } catch (failure) {
          if (signal.aborted) return false
          const key = failure.message
          setError(errorCodes.has(key) ? key : 'generic')
          const field = fieldForError(key)
          if (field !== null) requestAnimationFrame(() => {
            if (!signal.aborted) formRef.current?.elements.namedItem(field)?.focus()
          })
          return false
        } finally {
          inFlight.current = false
          if (!signal.aborted) setBusy('')
        }
      }

      function currentValues() {
        const elements = formRef.current?.elements
        const read = name => {
          const control = elements?.namedItem(name)
          return control && 'value' in control ? control.value : form[name]
        }
        const tls = elements?.namedItem('tls')
        return {
          name: read('name'), addresses: read('addresses'), username: read('username'),
          password: read('password'), tls: tls && 'checked' in tls ? tls.checked : form.tls,
        }
      }

      function focusFormField() {
        const values = currentValues()
        for (const name of ['name', 'addresses', 'username']) {
          if (!values[name].trim()) {
            formRef.current?.elements.namedItem(name)?.focus()
            return
          }
        }
        if (!values.password && (!editing || passwordNeeded)) {
          formRef.current?.elements.namedItem('password')?.focus()
        }
      }

      function create() {
        if (!draft || busy !== '') return
        const values = currentValues()
        if (!values.name.trim() || !values.addresses.trim() || !values.username.trim() || !values.password) return
        setPasswordCommitted(true)
        setConfirm(null)
        void mutate('save', values)
      }

      async function runTest() {
        if (busy !== '' || stale || !lifetime.current) return
        if (editing) {
          if (dirty) return
          const id = editing.id
          const token = ++testToken.current
          setTestState({ id, state: 'testing' })
          try {
            const value = await requestTest(lifetime.current.signal, { id })
            if (lifetime.current.signal.aborted || token !== testToken.current) return
            rememberVersion(id, value.ok === true ? value.version : null)
            setTestState({
              id,
              state: value.ok === true ? 'ok' : 'failed',
              version: typeof value.version === 'string' ? value.version : '',
              latencyMs: typeof value.latencyMs === 'number' ? value.latencyMs : null,
              message: typeof value.message === 'string' ? value.message : '',
            })
          } catch {
            if (lifetime.current.signal.aborted || token !== testToken.current) return
            rememberVersion(id, null)
            setTestState({ id, state: 'failed', message: t('testUnavailable') })
          }
          return
        }
        if (!draft) return
        const values = currentValues()
        if (!values.addresses.trim() || !values.username.trim() || !values.password) {
          focusFormField()
          return
        }
        const token = ++testToken.current
        setTestState({ id: 'new', state: 'testing' })
        try {
          const value = await requestTest(lifetime.current.signal, {
            draft: { addresses: values.addresses, username: values.username, password: values.password, tls: values.tls },
          })
          if (lifetime.current.signal.aborted || token !== testToken.current) return
          rememberVersion('new', value.ok === true ? value.version : null)
          setTestState({
            id: 'new',
            state: value.ok === true ? 'ok' : 'failed',
            version: typeof value.version === 'string' ? value.version : '',
            latencyMs: typeof value.latencyMs === 'number' ? value.latencyMs : null,
            message: typeof value.message === 'string' ? value.message : '',
          })
        } catch {
          if (lifetime.current.signal.aborted || token !== testToken.current) return
          rememberVersion('new', null)
          setTestState({ id: 'new', state: 'failed', message: t('testUnavailable') })
        }
      }

      function expandSavedRow(row) {
        if (!row) return
        setVersions(current => {
          if (!('new' in current)) return current
          const next = { ...current }
          const draftVersion = next.new
          delete next.new
          if (draftVersion) next[row.id] = draftVersion
          return next
        })
        const values = formOf(row)
        setExpandedId(row.id)
        setForm(values)
        setBaseline(values)
        setConfirm(null)
        resetEditorState()
      }

      async function mutate(action, data) {
        if (inFlight.current || !base || !lifetime.current) return
        const signal = lifetime.current.signal
        const before = base
        const wasExpanded = expandedId
        inFlight.current = true
        generation.current++
        setBusy(action)
        setError('')
        setNote('')
        try {
          const value = await request(signal, { ...data, action, revision: before.revision })
          if (signal.aborted) return
          setLive(value)
          setOffline('')
          if (action === 'save' && data.id === undefined) {
            const created = value.connections.find(row => !before.connections.some(prior => prior.id === row.id))
            setBase(value)
            if (!value.activeId && created) {
              try {
                const activated = await request(signal, { action: 'activate', id: created.id, revision: value.revision })
                if (signal.aborted) return
                setLive(activated)
                setBase(activated)
                expandSavedRow(activated.connections.find(row => row.id === created.id))
                setNote('enabled')
                focusName()
                return
              } catch (failure) {
                if (signal.aborted) return
                expandSavedRow(value.connections.find(row => row.id === created.id))
                setError(errorCodes.has(failure.message) ? failure.message : 'generic')
                return
              }
            }
            if (created) {
              expandSavedRow(created)
              setNote('created')
              focusName()
            } else {
              closeEditor(null)
              setNote('created')
            }
            return
          }
          setBase(value)
          if (action === 'clear') {
            forgetVersion(data.id)
            if (wasExpanded === data.id) closeEditor(() => newButton.current?.focus())
            setNote('removed')
            return
          }
          if (action === 'activate') {
            setNote('switched')
            return
          }
          const row = value.connections.find(item => item.id === data.id)
          if (row) {
            const values = formOf(row)
            setForm(values)
            setBaseline(values)
          }
          setNote('saved')
        } catch (failure) {
          if (signal.aborted) return
          const key = failure.message
          setError(errorCodes.has(key) ? key : 'generic')
          const field = fieldForError(key)
          if (field !== null) requestAnimationFrame(() => {
            if (!signal.aborted) formRef.current?.elements.namedItem(field)?.focus()
          })
        } finally {
          inFlight.current = false
          if (!signal.aborted) setBusy('')
        }
      }

      function reset() {
        generation.current++
        initialized.current = false
        setBase(null)
        setLive(null)
        setOffline('')
        setRetrying(false)
        setBusy('')
        setError('')
        setNote('')
        setConfirm(null)
        setExpandedId(null)
        setForm({ ...EMPTY_FORM })
        setBaseline({ ...EMPTY_FORM })
        setVersions({})
        resetEditorState()
        setReload(value => value + 1)
      }

      function retry() {
        if (inFlight.current || retrying) return
        generation.current++
        setRetrying(true)
        setReload(value => value + 1)
      }

      useEffect(() => {
        const controller = new AbortController()
        lifetime.current = controller
        let timer
        async function poll() {
          if (!inFlight.current) {
            const version = generation.current
            try {
              const result = await request(controller.signal)
              if (controller.signal.aborted || inFlight.current || version !== generation.current) return
              setLive(result)
              if (!initialized.current) {
                initialized.current = true
                setBase(result)
              }
              setOffline('')
              setRetrying(false)
            } catch (failure) {
              if (!controller.signal.aborted && !inFlight.current && version === generation.current) {
                setOffline(errorCodes.has(failure.message) ? failure.message : 'generic')
                setRetrying(false)
              }
            } finally {
              if (!controller.signal.aborted) timer = setTimeout(poll, 2500)
            }
          } else timer = setTimeout(poll, 2500)
        }
        void poll()
        return () => { controller.abort(); clearTimeout(timer) }
      }, [reload])

      useEffect(() => {
        if (!editing || !dirty || !valid || busy !== '' || stale || error !== '') return
        const timer = setTimeout(() => { void persist() }, 550)
        return () => clearTimeout(timer)
      }, [editing, form, dirty, valid, busy, stale, error])

      useEffect(() => {
        if (!draft || !valid || busy !== '' || stale || error !== '' || testState?.state === 'testing') return
        const timer = setTimeout(() => { create() }, 550)
        return () => clearTimeout(timer)
      }, [draft, form, valid, busy, stale, error, testState?.state])

      useEffect(() => {
        try {
          if (typeof window === 'undefined' || !window.localStorage) return
          const persisted = {}
          for (const [key, value] of Object.entries(versions)) {
            if (key === 'new' || typeof value !== 'string' || !value) continue
            persisted[key] = value
          }
          window.localStorage.setItem(VERSION_STORE, JSON.stringify(persisted))
        } catch {
          // Storage can be disabled; the in-memory map still works for this session.
        }
      }, [versions])

      useEffect(() => {
        if (!base) return
        const ids = new Set(base.connections.map(row => row.id))
        setVersions(current => {
          let changed = false
          const next = {}
          for (const [key, value] of Object.entries(current)) {
            if (key === 'new' || ids.has(key)) next[key] = value
            else changed = true
          }
          return changed ? next : current
        })
      }, [base])

      let statusKey = 'synced'
      let tone = 'success'
      if (busy !== '') {
        statusKey = busy === 'save' ? 'saving' : busy === 'activate' ? 'switching' : 'removing'
        tone = 'progress'
      } else if (!base) {
        statusKey = offline ? 'unavailable' : 'checkingState'
        tone = offline ? 'error' : 'progress'
      } else if (stale) {
        statusKey = 'staleState'
        tone = 'error'
      } else if (offline) {
        statusKey = 'staleState'
        tone = 'warn'
      } else if (error !== '' && fieldForError(error) === null) {
        statusKey = 'failedState'
        tone = 'error'
      } else if (dirty) {
        statusKey = 'unsynced'
        tone = 'warn'
      } else if (note !== '') {
        statusKey = note
        tone = 'success'
      } else if (!active) {
        statusKey = 'inactive'
        tone = 'warn'
      }

      let saveKey = 'saved'
      let saveTone = 'success'
      if (busy === 'save') {
        saveKey = 'saving'
        saveTone = 'progress'
      } else if (error !== '' && !stale) {
        saveKey = 'saveFailed'
        saveTone = 'error'
      } else if (draft) {
        saveKey = 'unsaved'
        saveTone = 'warn'
      } else if (dirty) {
        saveKey = 'unsaved'
        saveTone = 'warn'
      }

      const field = (name, label, options = {}) => {
        const fieldId = prefix + '-' + name
        const invalid = fieldForError(error) === name
        const hint = options.hint
        return h('div', { className: 'ns-field' + (options.wide ? ' ns-wide' : '') },
          h('label', { className: 'ns-label', htmlFor: fieldId }, label,
            name === 'password' && editing?.passwordSaved && h('span', { className: 'ns-tag ns-inlineTag' }, t('passwordSaved'))),
          h('input', {
            id: fieldId, name, className: 'ns-input', value: form[name],
            type: options.type ?? 'text', required: options.required, maxLength: options.maxLength,
            autoComplete: options.autoComplete ?? 'off', spellCheck: false, placeholder: options.placeholder,
            'aria-invalid': invalid ? 'true' : undefined,
            'aria-describedby': [hint && fieldId + '-hint', invalid && fieldId + '-error'].filter(Boolean).join(' ') || undefined,
            onChange: event => set(name, event.currentTarget.value),
            onBlur: options.onBlur, onKeyDown: options.onKeyDown,
          }),
          hint && h('span', { className: 'ns-fieldHint', id: fieldId + '-hint' }, hint),
          invalid && h('span', { className: 'ns-fieldError', id: fieldId + '-error', role: 'alert' }, err(error)))
      }

      const editorForm = expanded ? h('form', {
        ref: formRef, className: 'ns-editorForm', onSubmit: event => event.preventDefault(),
        'aria-describedby': dirty ? dirtyId : undefined,
      },
        h('div', { className: 'ns-grid' },
          field('name', t('connectionName'), { required: true, maxLength: 64, placeholder: t('nameHint'), autoComplete: 'off' }),
          field('username', t('username'), { required: true, maxLength: 256, autoComplete: 'off' }),
          field('addresses', t('addresses'), {
            required: true, maxLength: 2000, placeholder: 'db.example.net:9669',
            autoComplete: 'off', hint: t('addressHint'), wide: true,
          }),
          field('password', t('password'), {
            type: 'password', maxLength: 2048, autoComplete: 'new-password', wide: true,
            required: !editing?.passwordSaved,
            hint: editing?.passwordSaved ? t('keep') : t('passwordHint'),
            onBlur: () => { if (form.password !== '') setPasswordCommitted(true) },
            onKeyDown: event => {
              if (event.key === 'Enter' && !event.nativeEvent.isComposing) event.currentTarget.blur()
            },
          }),
          h('label', { className: 'ns-check ns-wide' },
            h('input', {
              type: 'checkbox', name: 'tls', checked: form.tls,
              onChange: event => set('tls', event.currentTarget.checked),
            }),
            h('span', null, t('tls')))),
        h('div', { className: 'ns-editorFoot' },
          (editing || draft) && h('button', {
            type: 'button', className: 'ns-button ns-small',
            disabled: Boolean(busy) || stale || (editing ? dirty : false) || testState?.state === 'testing',
            onClick: () => void runTest(),
          }, t(testState?.state === 'testing' ? 'testing' : 'test')),
          (editing || draft) && h('span', { className: 'ns-saveState', 'data-tone': saveTone, role: 'status' },
            h('span', { className: 'ns-dot', 'aria-hidden': true }), t(saveKey)),
          h('span', { className: 'ns-editorSpacer' }),
          (editing || draft) && saveKey === 'saveFailed' && h('button', {
            type: 'button', className: 'ns-linkButton',
            onClick: () => {
              setError('')
              if (editing) void persist()
              else create()
            },
          }, t('retry')),
          editing && dirty && h('button', {
            type: 'button', className: 'ns-button ns-small', disabled: Boolean(busy), onClick: discard,
          }, t('discard')),
          editing && dirty && h('p', { className: 'ns-hint ns-editorHint', id: dirtyId }, t('dirtyHint'))),
        testState && ((editing && testState.id === editing.id) || (draft && testState.id === 'new')) && h('p', {
          className: 'ns-testResult', role: 'status',
          'data-tone': testState.state === 'ok' ? 'success' : testState.state === 'failed' ? 'error' : 'progress',
        }, testState.state === 'testing'
          ? t('testing')
          : testState.state === 'ok'
            ? [t('testOk'), testState.version ? 'v' + testState.version : '', testState.latencyMs !== null && testState.latencyMs !== undefined ? testState.latencyMs + ' ms' : ''].filter(Boolean).join(' · ')
            : [t('testFailed'), testState.message || t('testUnavailable')].filter(Boolean).join(' · ')))
        : null

      const renderRow = row => {
        const current = row.id === base.activeId
        const isExpanded = expandedId === row.id
        const confirming = confirm === row.id
        const editorId = prefix + '-editor-' + row.id
        const rowDisabled = blocked || dirty
        const version = versions[row.id] ?? null
        const versionLabel = version ? 'v' + version : '-'
        return h('div', { key: row.id, className: 'ns-radioItem', 'data-accent': accentFor(row.id) },
          h('div', {
            className: 'ns-radioRow',
            'data-current': current ? 'true' : undefined,
            'data-expanded': isExpanded ? 'true' : undefined,
            'data-disabled': rowDisabled ? 'true' : undefined,
          },
            h('input', {
              className: 'ns-radio', type: 'radio', name: prefix + '-active',
              checked: current, disabled: blocked,
              'aria-label': (current ? t('current') : t('switchTo')) + ' ' + row.name,
              onChange: () => select(row.id),
            }),
            h('button', {
              type: 'button', className: 'ns-rowToggle',
              ref: node => {
                if (node === null) toggleRefs.current.delete(row.id)
                else toggleRefs.current.set(row.id, node)
              },
              disabled: rowDisabled,
              'aria-expanded': isExpanded ? 'true' : 'false',
              'aria-controls': isExpanded ? editorId : undefined,
              title: t(isExpanded ? 'collapse' : 'expand'),
              onClick: () => toggleRow(row.id),
            },
              h('span', { className: 'ns-rowText' },
                h('span', { className: 'ns-radioName' }, row.name),
                h('span', {
                  className: 'ns-radioMeta',
                  title: [row.username, row.addresses, versionLabel].join(' · '),
                },
                  h('span', { className: 'ns-user' }, row.username),
                  h('span', { className: 'ns-sep', 'aria-hidden': 'true' }, '·'),
                  h('span', { className: 'ns-radioAddr' }, row.addresses),
                  h('span', { className: 'ns-sep', 'aria-hidden': 'true' }, '·'),
                  h('span', { className: 'ns-version', title: t('version') }, versionLabel))),
              h(Chevron)),
            h('button', {
              type: 'button', className: 'ns-iconButton', disabled: rowDisabled,
              title: t('remove') + ' ' + row.name,
              'aria-label': t('remove') + ' ' + row.name,
              ref: node => {
                if (node === null) trashRefs.current.delete(row.id)
                else trashRefs.current.set(row.id, node)
              },
              onClick: () => toggleConfirm(row.id),
            }, h(Trash))),
          confirming && h('div', {
            className: 'ns-confirmRow', role: 'group', 'aria-label': t('remove') + ' ' + row.name,
          },
            h('span', { className: 'ns-confirmText' },
              h('span', { className: 'ns-confirmName' }, row.name), ' · ',
              t(current ? 'removeActiveHint' : 'removeHint')),
            h('div', { className: 'ns-actions' },
              h('button', {
                type: 'button', className: 'ns-button ns-small ns-danger', disabled: busy !== '',
                onClick: () => removeRow(row.id),
              }, t('remove')),
              h('button', {
                type: 'button', className: 'ns-button ns-small', autoFocus: true, disabled: busy !== '',
                onClick: () => {
                  setConfirm(null)
                  requestAnimationFrame(() => trashRefs.current.get(row.id)?.focus())
                },
              }, t('cancel')))),
          isExpanded && editorForm && h('div', {
            className: 'ns-editor', id: editorId, role: 'group',
            'aria-label': t('editTitle') + ' ' + row.name,
          }, editorForm))
      }

      const draftName = form.name.trim() || t('newConnection')
      const draftVersion = versions.new ?? null
      const draftVersionLabel = draftVersion ? 'v' + draftVersion : '-'
      const draftView = draft && h('div', { key: 'new', className: 'ns-radioItem ns-draftItem', 'data-accent': 0 },
        h('div', { className: 'ns-radioRow', 'data-expanded': 'true' },
          h('input', {
            className: 'ns-radio', type: 'radio', name: prefix + '-active',
            disabled: true, 'aria-label': t('newConnection'),
          }),
          h('div', { className: 'ns-rowText' },
            h('span', { className: 'ns-radioName' }, draftName),
            h('span', {
              className: 'ns-radioMeta',
              title: [form.username.trim(), form.addresses.trim(), draftVersionLabel].filter(Boolean).join(' · '),
            },
              form.username.trim() && h('span', { className: 'ns-user' }, form.username.trim()),
              form.username.trim() && form.addresses.trim() && h('span', { className: 'ns-sep', 'aria-hidden': 'true' }, '·'),
              form.addresses.trim() && h('span', { className: 'ns-radioAddr' }, form.addresses.trim()),
              (form.username.trim() || form.addresses.trim()) && h('span', { className: 'ns-sep', 'aria-hidden': 'true' }, '·'),
              h('span', { className: 'ns-version', title: t('version') }, draftVersionLabel))),
          h('button', {
            type: 'button', className: 'ns-iconButton', disabled: busy !== '',
            title: t('remove') + ' ' + draftName,
            'aria-label': t('remove') + ' ' + draftName,
            onClick: removeDraft,
          }, h(Trash))),
        h('div', {
          className: 'ns-editor', id: prefix + '-editor-new', role: 'group', 'aria-label': draftName,
        }, editorForm))

      const bannerButton = (label, action, disabled) => h('button', {
        type: 'button', className: 'ns-button ns-small', disabled, onClick: action,
      }, label)

      return h('div', {
        className: 'nebula-settings', role: 'region', 'aria-labelledby': prefix + '-title',
        'aria-busy': busy !== '' ? 'true' : undefined,
      },
        h('style', null, css),
        h('header', { className: 'ns-hero' },
          h('div', { className: 'ns-mark' }, h(Icon, { size: 22 })),
          h('div', { className: 'ns-heroText' },
            h('div', { className: 'ns-kicker' }, 'MCP'),
            h('h1', { className: 'ns-title', id: prefix + '-title' }, t('title')),
            h('p', { className: 'ns-intro' }, t('intro'))),
          h('div', { className: 'ns-heroAside' },
            h('span', { className: 'ns-tag' }, t('readOnly')),
            h('span', { className: 'ns-status', 'data-tone': tone, role: 'status', 'aria-live': 'polite' },
              h('span', { className: 'ns-dot', 'aria-hidden': true }), t(statusKey)))),
        loading
          ? h('div', { className: 'ns-card' }, h('div', { className: 'ns-loading', role: 'status' },
              h('span', { className: 'ns-spinner', 'aria-hidden': true }), t('loading')))
          : !base
            ? h('div', { className: 'ns-banner', role: 'alert' },
                h('span', { className: 'ns-bannerText' }, err(offline)),
                bannerButton(t(retrying ? 'retrying' : 'retry'), retry, retrying))
            : h('div', { className: 'ns-body' },
                stale && h('div', { className: 'ns-banner', role: 'alert' },
                  h('span', { className: 'ns-bannerText' }, err(error === 'cleanup' ? 'cleanup' : error === 'not-found' ? 'not-found' : 'conflict')),
                  bannerButton(t('reload'), reset, busy !== '')),
                base && offline !== '' && !stale && h('div', { className: 'ns-banner', role: 'alert' },
                  h('span', { className: 'ns-bannerText' }, err(offline),
                    h('span', { className: 'ns-hint' }, t('offlineStale'))),
                  bannerButton(t(retrying ? 'retrying' : 'retry'), retry, busy !== '' || retrying)),
                error !== '' && !stale && fieldForError(error) === null && h('div', { className: 'ns-banner', role: 'alert' },
                  h('span', { className: 'ns-bannerText' }, err(error))),
                h('section', { className: 'ns-card', 'aria-labelledby': prefix + '-connections' },
                  h('div', { className: 'ns-cardHead ns-connectionsHead' },
                    h('div', { className: 'ns-cardHeadMain' },
                      h('h2', { className: 'ns-sectionTitle', id: prefix + '-connections' }, t('connection')),
                      h('p', { className: 'ns-hint' }, active ? t('connectionHint') : connections.length ? t('noActiveHint') : t('connectionHint'))),
                    !canCreate
                      ? h('span', { className: 'ns-hint ns-cap' }, t('cap'))
                      : !draft && h('button', {
                          type: 'button', ref: newButton, className: 'ns-button ns-small',
                          disabled: blocked, onClick: () => void openNew(),
                        }, t('newConnection'))),
                  h('div', { className: 'ns-radioList' },
                    connections.length === 0 && !draft && h('div', { className: 'ns-empty' }, t('empty')),
                    connections.map(renderRow),
                    draftView))))
    }


    return {
      inject: ['slots', 'locale'],
      apply(ctx) {
        const t = ctx.locale.bind(id)
        ctx.effect(() => ctx.locale.register(id, { zh, en }), 'nebula-dsh: locale')
        ctx.slots.inject('settings.section', () => ctx.slots.register({
          name: 'settings.section', id, order: 20.5, locale: id, label: () => t('nav'),
        }, () => h(Page, { t })))
        ctx.slots.inject('settings.section.icon', () => ctx.slots.register({ name: 'settings.section.icon', id }, Icon))
      },
    }
  },
})
