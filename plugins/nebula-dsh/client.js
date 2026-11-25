window.__ModuleLoader__.load({
  id: 'dsh-nebula-mcp',
  factory(require) {
    const { createElement: h, useEffect, useId, useRef, useState } = require('react')
    const id = 'nebula-graph'
    const endpoint = '/api/nebula-dsh/settings'
    const guide = 'https://github.com/MuYiYong/nebula-mcp#deepseek-harness'
    const zh = {
      title: '悦数图数据库（NebulaGraph 5.x）',
      intro: '为当前 DSH 配置档设置一个只读连接。所有 Agent 预设共用，不会修改 Codex 配置。',
      runtime: 'Python 运行时', mcp: 'MCP 状态', checking: '正在检查…', ready: '已安装',
      missing: '未安装', invalid: '安装数据无效', unsupported: '请升级运行时',
      disabled: '未启用', connecting: '正在启动…', reconnecting: '正在重连…',
      connected: 'MCP 已就绪', failed: 'MCP 启动失败', closed: '已停止',
      'waiting-credentials': '等待密码', 'registration-error': '无法注册 MCP',
      install: '查看运行时安装说明',
      db: 'MCP 已就绪不代表数据库已连通。保存并启用后，可以在新对话中说“用 Nebula MCP 测试数据库连接”。',
      connection: '数据库连接', addresses: '数据库地址', addressHint: '格式为 HOST:PORT；多个地址用逗号分隔。',
      username: '用户名', password: '密码', passwordHint: '仅保存在本机的 DSH 凭据库，不会回显。请勿在对话中发送密码。',
      keep: '已保存密码。地址、用户名和 TLS 不变时，留空可保留原密码。',
      tls: '启用 TLS（与数据库服务端配置一致）', enabled: '在当前配置档启用 MCP',
      save: '保存连接', restart: '检查运行时 / 重启 MCP', clear: '移除连接', confirm: '确认移除', cancel: '取消',
      removeHint: '移除后将删除已保存的连接和密码，并停止提供此 MCP 工具。',
      saved: '连接设置已保存。', cleared: '已移除连接。', refreshed: '已重新检查运行时。',
      reload: '重新载入设置', loading: '正在载入设置…',
      errors: {
        addresses: '请输入有效地址：HOST:PORT，端口为 1–65535。', username: '请输入有效用户名。',
        password: '请输入有效密码（不含控制字符或首尾空格）。', 'new-password': '更改地址、用户名或 TLS 时，请重新输入密码。',
        conflict: '设置已在其他窗口更改。请重新载入设置后再保存。',
        cleanup: '连接设置已更新，但清理旧凭据时出错。请重新载入设置。',
        generic: '无法访问悦数图数据库设置。确认插件已启用后重试。',
      },
    }
    const en = {
      title: 'YueShu graph database (NebulaGraph 5.x)',
      intro: 'Configure one read-only connection shared by all agent presets in this DSH profile. This does not change Codex.',
      runtime: 'Python runtime', mcp: 'MCP status', checking: 'Checking…', ready: 'Installed',
      missing: 'Not installed', invalid: 'Invalid installation', unsupported: 'Update required',
      disabled: 'Not enabled', connecting: 'Starting…', reconnecting: 'Reconnecting…',
      connected: 'MCP ready', failed: 'MCP failed to start', closed: 'Stopped',
      'waiting-credentials': 'Waiting for password', 'registration-error': 'Could not register MCP',
      install: 'Runtime installation instructions',
      db: 'MCP ready does not mean the database is reachable. After saving and enabling, ask Nebula MCP to test the database connection in a new chat.',
      connection: 'Database connection', addresses: 'Database addresses', addressHint: 'Use HOST:PORT. Separate multiple addresses with commas.',
      username: 'Username', password: 'Password', passwordHint: 'Stored locally in DSH credentials and never displayed here. Do not send it in chat.',
      keep: 'Password saved. Leave blank to keep it only if the addresses, username, and TLS are unchanged.',
      tls: 'Enable TLS (match the database server)', enabled: 'Enable MCP for this profile',
      save: 'Save connection', restart: 'Check runtime / restart MCP', clear: 'Remove connection', confirm: 'Confirm removal', cancel: 'Cancel',
      removeHint: 'This removes the saved connection and password and stops providing its MCP tools.',
      saved: 'Connection settings saved.', cleared: 'Connection removed.', refreshed: 'Runtime checked.',
      reload: 'Reload settings', loading: 'Loading settings…',
      errors: {
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
    Object.assign(zh, { nav: '悦数图数据库', working: '正在处理…', unavailable: '状态不可用', failed: 'MCP 连接失败', 'host-restart-required': '请重启 DeepSeek Harness', 'errors.forbidden': '只有已登录的 DSH 所有者可管理此连接。', 'errors.store': '无法读取或更新本机连接设置。' })
    Object.assign(en, { nav: 'YueShu graph database', working: 'Working…', unavailable: 'Status unavailable', failed: 'MCP connection failed', 'host-restart-required': 'Restart DeepSeek Harness', 'errors.forbidden': 'Only the signed-in DSH owner can manage this connection.', 'errors.store': 'Could not read or update local connection settings.' })
    const css = `
      .nebula-settings { max-inline-size: 42rem; padding: 1.5rem clamp(1rem, 4vw, 2rem); color: var(--dsw-alias-label-primary); }
      .nebula-settings h2 { margin: 0; font-size: 1.25rem; }
      .nebula-settings p { margin: .5rem 0; line-height: 1.55; }
      .nebula-settings .hint { color: var(--dsw-alias-label-secondary); overflow-wrap: anywhere; }
      .nebula-settings .status { border: 1px solid var(--dsw-alias-border-l1); border-radius: .75rem; padding: .875rem 1rem; margin-block: 1.25rem; background: var(--dsw-alias-bg-layer-1); }
      .nebula-settings dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: .5rem 1rem; margin: 0; }
      .nebula-settings dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
      .nebula-settings a { text-decoration: underline; color: var(--dsw-alias-brand-primary); }
      .nebula-settings fieldset { display: grid; gap: .875rem; border: 0; padding: 0; margin: 0; min-inline-size: 0; }
      .nebula-settings legend { padding: 0; margin-block-end: .75rem; font-weight: 650; }
      .nebula-settings .field { display: grid; gap: .25rem; }
      .nebula-settings input:not([type=checkbox]) { inline-size: 100%; box-sizing: border-box; min-block-size: 3rem; border: 1px solid var(--dsw-alias-border-l2); border-radius: .5rem; background: var(--dsw-alias-bg-base); color: inherit; font: inherit; font-size: 1rem; padding-inline: .75rem; }
      .nebula-settings input[aria-invalid=true] { border-color: var(--dsw-alias-state-error-primary); }
      .nebula-settings .check { display: flex; align-items: center; gap: .5rem; min-block-size: 3rem; }
      .nebula-settings input[type=checkbox] { accent-color: var(--dsw-alias-brand-primary); }
      .nebula-settings .actions { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem; margin-block: .5rem; }
      .nebula-settings button { min-block-size: 3rem; padding: .4rem .8rem; font: inherit; color: inherit; border-radius: .5rem; border: 1px solid var(--dsw-alias-border-l2); background: var(--dsw-alias-bg-layer-1); cursor: pointer; }
      .nebula-settings button.primary { background: var(--dsw-alias-button-primary-fill); color: var(--dsw-alias-label-primary-foreground); }
      .nebula-settings button:disabled { opacity: .65; cursor: default; }
      .nebula-settings :focus-visible { outline: 2px solid var(--dsw-alias-brand-primary); outline-offset: 2px; }
      .nebula-settings .error { color: var(--dsw-alias-state-error-primary); }
    `

    async function request(signal, body) {
      const response = await fetch(endpoint, {
        method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal,
        ...(body && { headers: { 'content-type': 'application/json', 'x-dsh-nebula-settings': '1' }, body: JSON.stringify(body) }),
      })
      const value = await response.json()
      if (!response.ok) throw new Error(typeof value?.error === 'string' ? value.error : 'generic')
      return value
    }
    function Icon({ size = 16 }) {
      return h('svg', { width: size, height: size, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', 'aria-hidden': true },
        h('path', { d: 'm6 12 4-6 4 7z', strokeWidth: '1.3' }),
        [ [10, 5], [5, 13], [15, 14] ].map(([cx, cy]) => h('circle', { key: cx, cx, cy, r: '2', fill: 'currentColor', stroke: 'none' })))
    }
    function Page({ t }) {
      const prefix = useId()
      const lifetime = useRef(null)
      const form = useRef(null)
      const heading = useRef(null)
      const inFlight = useRef(false)
      const generation = useRef(0)
      const [base, setBase] = useState(null)
      const [live, setLive] = useState(null)
      const [busy, setBusy] = useState('')
      const [note, setNote] = useState('')
      const [error, setError] = useState('')
      const [offline, setOffline] = useState('')
      const [confirm, setConfirm] = useState(false)
      const [reload, setReload] = useState(0)
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
              setBase(current => current ?? result)
              setOffline('')
            } catch (err) {
              if (!controller.signal.aborted && !inFlight.current && version === generation.current) {
                setOffline(errorCodes.has(err.message) ? err.message : 'generic')
              }
            } finally {
              if (!controller.signal.aborted) timer = setTimeout(poll, 2500)
            }
          } else timer = setTimeout(poll, 2500)
        }
        void poll()
        return () => { controller.abort(); clearTimeout(timer) }
      }, [reload])
      async function mutate(action, data) {
        if (inFlight.current || !lifetime.current || (!base && action !== 'restart')) return
        const signal = lifetime.current.signal
        inFlight.current = true
        generation.current++
        setBusy(action)
        setNote('')
        setError('')
        try {
          const value = await request(signal, { ...data, action, revision: base?.revision })
          if (signal.aborted) return
          setLive(value)
          setOffline('')
          if (action !== 'restart') {
            setBase(value)
            setConfirm(false)
            heading.current?.focus()
          } else setBase(current => current ?? value)
          setNote(action === 'save' ? 'saved' : action === 'clear' ? 'cleared' : 'refreshed')
        } catch (err) {
          if (signal.aborted) return
          const key = err.message
          setError(key)
          const field = key === 'new-password' ? 'password' : key
          if (['addresses', 'username', 'password'].includes(field)) {
            requestAnimationFrame(() => form.current?.elements.namedItem(field)?.focus())
          }
        } finally {
          inFlight.current = false
          if (!signal.aborted) setBusy('')
        }
      }
      const text = key => t(key)
      const err = key => t('errors.' + (errorCodes.has(key) ? key : 'generic'))
      const saved = base?.connection
      const field = (name, props, hint) => {
        const fieldId = prefix + name
        const invalid = error === name || (name === 'password' && error === 'new-password')
        return h('div', { className: 'field' }, h('label', { htmlFor: fieldId }, text(name)),
          h('input', { id: fieldId, name, ...props, onInput: () => { if (invalid) setError('') },
            'aria-invalid': invalid, 'aria-describedby': [hint && fieldId + '-hint', invalid && fieldId + '-error'].filter(Boolean).join(' ') || undefined }),
          hint && h('small', { className: 'hint', id: fieldId + '-hint' }, hint),
          invalid && h('span', { className: 'error', id: fieldId + '-error' }, err(error)))
      }
      const reset = () => { setBase(null); setError(''); setNote(''); setConfirm(false); setReload(value => value + 1) }
      const runtime = offline ? null : live?.runtime
      const changedElsewhere = base && live && base.revision !== live.revision
      return h('section', { className: 'nebula-settings' }, h('style', null, css),
        h('h2', { ref: heading, tabIndex: -1 }, text('title')), h('p', { className: 'hint' }, text('intro')),
        h('div', { className: 'status' }, h('dl', { 'aria-live': 'polite' },
          h('dt', null, text('runtime')), h('dd', null, text(runtime?.state ?? (offline ? 'unavailable' : 'checking')), runtime?.version && ' · ' + runtime.version),
          h('dt', null, text('mcp')), h('dd', null, text(offline ? 'unavailable' : live?.mcp.state ?? 'checking'))),
          h('div', { className: 'actions' },
            h('button', { type: 'button', disabled: Boolean(busy), onClick: () => void mutate('restart') }, text(busy === 'restart' ? 'checking' : 'restart')),
            runtime?.state !== 'ready' && h('a', { href: guide, target: '_blank', rel: 'noreferrer' }, text('install'))),
          h('p', { className: 'hint' }, text('db'))),
        !base ? !offline && h('p', null, text('loading')) : h('form', {
          key: base.revision, ref: form, method: 'post', onSubmit(event) {
            event.preventDefault()
            const fields = new FormData(event.currentTarget)
            void mutate('save', { addresses: fields.get('addresses'), username: fields.get('username'),
              password: fields.get('password'), tls: fields.has('tls'), enabled: fields.has('enabled') })
          },
        }, h('fieldset', { disabled: Boolean(busy || changedElsewhere) }, h('legend', null, text('connection')),
          field('addresses', { defaultValue: saved?.addresses, required: true, maxLength: 2000, autoComplete: 'off', spellCheck: false, placeholder: 'db.example.net:9669' }, text('addressHint')),
          field('username', { defaultValue: saved?.username, required: true, maxLength: 256, autoComplete: 'off', spellCheck: false }),
          field('password', { type: 'password', required: !base.passwordSaved, maxLength: 2048, autoComplete: 'new-password' },
            text('passwordHint') + (base.passwordSaved ? ' ' + text('keep') : '')),
          h('label', { className: 'check' }, h('input', { type: 'checkbox', name: 'tls', defaultChecked: saved?.tls ?? true }), text('tls')),
          h('label', { className: 'check' }, h('input', { type: 'checkbox', name: 'enabled', defaultChecked: saved?.enabled ?? true }), text('enabled')),
          h('div', { className: 'actions' },
            h('button', { type: 'submit', className: 'primary' }, text(busy === 'save' ? 'working' : 'save')),
            saved && h('button', { type: 'button', 'aria-expanded': confirm, 'aria-controls': prefix + '-remove',
              id: prefix + '-remove-trigger', onClick: () => setConfirm(open => !open) }, text('clear'))),
          h('div', { id: prefix + '-remove', hidden: !confirm }, h('p', null, text('removeHint')),
            h('div', { className: 'actions' }, h('button', { type: 'button', onClick: () => void mutate('clear') }, text(busy === 'clear' ? 'working' : 'confirm')),
              h('button', { type: 'button', onClick: () => { document.getElementById(prefix + '-remove-trigger')?.focus(); setConfirm(false) } }, text('cancel')))))),
        h('div', { role: 'status' }, (busy || note) && h('p', null, text(busy ? (busy === 'restart' ? 'checking' : 'working') : note)),
          (offline || error || changedElsewhere) && h('p', { className: 'error' }, err(offline || error || 'conflict'))),
        (offline || changedElsewhere || error === 'conflict' || error === 'cleanup') && h('button', { type: 'button', disabled: Boolean(busy), onClick: reset }, text('reload')))
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
