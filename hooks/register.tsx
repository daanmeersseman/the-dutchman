import { atom, read, update } from 'claude-code'
import type { Hook, Register } from 'claude-code'

import type { Config, Reminder, Result, State, Status, Tip, View } from '../types'

type Api = Parameters<Hook<'session.start'>>[0]
type Outcome = { ok: boolean; message: string }

// Test mode: analyse and announce the tips at every session start; Apply shows the diff and writes nothing.
const DRY = false
const DAY = 86_400_000
const PANE = 'dutchman'
const TITLE = 'The Dutchman'
const RESULT = 'result-v5' // bump when the tip shape changes, so an old cached result is not shown
const STATE = 'state-v2'
const CONFIG = 'config-v1'
const ANNOUNCED = 'announced-at'
const REFRESH = { daily: DAY, weekly: 7 * DAY, manual: Infinity } as const
// How long after an announcement the next may come; a little under the period, so a session at the same hour counts.
const OFTEN = { session: 0, daily: DAY - 3_600_000, weekly: 7 * DAY - 3_600_000, monthly: 30 * DAY - 3_600_000 } as const
const fsPath = (u: URL) => decodeURIComponent(u.pathname).replace(/^\/([A-Za-z]:)/, '$1')
const ANALYZE = fsPath(new URL('../scripts/analyze.py', import.meta.url))
const ACTIONS = fsPath(new URL('../scripts/actions.py', import.meta.url))

const DEFAULTS: Config = { minSaving: 5, notify: 'pane', contextAt: 250_000, days: 30, refresh: 'daily', cacheStake: 5, often: 'weekly' }

const view = atom({ plugin: 'dutchman', key: 'view' } as const, {
  result: null, state: {}, open: null, busy: null, message: null, preview: null, plan: null, tab: 'open', config: DEFAULTS, setup: null,
} as View)

const money = (n: number) => `$${n < 10 ? n.toFixed(2) : Math.round(n)}`

// ---------- state ----------

async function setStatus($: Api, id: string, status: Status['status'] | undefined, tip?: Tip): Promise<void> {
  const state = ((await $.store.get(STATE)) ?? {}) as State
  if (status) state[id] = { status, at: await $.clock.now(), ...(tip ? { tip } : {}) }
  else delete state[id]
  await $.store.set(STATE, state)
  await update($, view, v => ({ ...v, state }))
  if (status === 'applied' && tip?.reminder) reminders.set(tip.reminder.id, tip.reminder)
  if (!status && tip?.reminder) reminders.delete(tip.reminder.id)
}

const say = ($: Api, patch: Partial<View>) => update($, view, v => ({ ...v, busy: null, isError: false, ...patch }))

// ---------- config ----------

const getConfig = async ($: Api): Promise<Config> => ({ ...DEFAULTS, ...(((await $.store.get(CONFIG)) ?? {}) as Partial<Config>) })

// Saves the change; analyses again when it changes what the analysis finds.
async function setConfig($: Api, patch: Partial<Config>): Promise<void> {
  const old = await getConfig($)
  const config = { ...old, ...patch }
  await $.store.set(CONFIG, config)
  await update($, view, v => ({ ...v, config }))
  if ((old.days !== config.days || old.contextAt !== config.contextAt || old.cacheStake !== config.cacheStake)) await analyze($)
}

// A tip shows when it is worth the user's threshold; one without an amount always shows.
const worth = (t: Tip, c: Config) => (t.saving ?? t.measured ?? Infinity) >= c.minSaving

// ---------- python ----------

// Runs a script of the plugin with python, else python3. Undefined when neither runs it.
async function python($: Api, args: string[], stdin?: string): Promise<string | undefined> {
  for (const py of ['python', 'python3']) {
    try {
      const r = await $.process.run([py, '-I', ...args], { timeoutMs: 300_000, ...(stdin ? { stdin } : {}) })
      if (r.exitCode === 0) return r.stdout
      $.ui.log(`dutchman: ${py} exited ${r.exitCode}: ${r.stderr.slice(-500)}`, { to: 'debug' })
    } catch (err) {
      $.ui.log(`dutchman: ${py}: ${String(err)}`, { to: 'debug' })
    }
  }
  return undefined
}

async function analyze($: Api): Promise<Result | undefined> {
  const c = await getConfig($)
  await update($, view, v => ({ ...v, busy: `Reading your logs of the last ${c.days} days…` }))
  const out = await python($, [ANALYZE, '--cwd', await $.session.cwd(), '--days', String(c.days),
    '--context-limit', String(c.contextAt), '--cache-stake', String(c.cacheStake)])
  if (!out) {
    await say($, { message: 'Python 3 did not run the analysis. Is python on the PATH?', isError: true })
    return undefined
  }
  const res = { ...JSON.parse(out), at: await $.clock.now() } as Result
  for (const e of res.errors ?? []) $.ui.log(`dutchman: detector failed: ${e}`, { to: 'debug' })
  await $.store.set(RESULT, res)
  await say($, { result: res })
  return res
}

async function actions($: Api, args: string[], tip?: Tip): Promise<Outcome> {
  const out = await python($, [ACTIONS, ...args], tip ? JSON.stringify(tip.actions) : undefined)
  return out ? (JSON.parse(out) as Outcome) : { ok: false, message: 'Python 3 did not run, so nothing changed.' }
}

const older = (have: string, need: string) => {
  const [a, b] = [have, need].map(v => v.split('.').map(Number))
  for (let i = 0; i < 3; i++) if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) < (b[i] ?? 0)
  return false
}

// ---------- apply and undo ----------

async function apply($: Api, t: Tip): Promise<void> {
  if (t.min_version) {
    const v = await $.session.version()
    if (older(v.base ?? v.version, t.min_version))
      return say($, { message: `Needs Claude Code ${t.min_version} or newer; you have ${v.version}. Update first.`, isError: true })
  }
  let items: string[] = []
  if (t.choose) {
    // shortcut: ask shows at most 4 items; a longer list needs a Select in the pane
    const a = await $.ui.ask(t.choose.question, { header: 'The Dutchman', options: t.choose.items.slice(0, 4), multiSelect: true })
      .catch(() => '')
    items = a.split(',').map(s => s.trim()).filter(s => t.choose!.items.includes(s))
    if (items.length === 0) return say($, { message: 'Nothing picked, nothing changed.' })
  }
  const args = ['apply', t.id, ...(items.length ? ['--items', items.join(',')] : [])]
  await update($, view, v => ({ ...v, busy: `Applying "${t.title}"…`, preview: null }))
  if (DRY) {
    const r = t.actions.length ? await actions($, [...args, '--dry'], t) : { ok: true, message: '' }
    const rem = t.reminder ? `Would turn on the reminder: "${t.reminder.text.replace('{k}', '260')}"` : ''
    return say($, { message: 'Test mode: nothing was written.', preview: [r.message, rem].filter(Boolean).join('\n\n') })
  }
  const r = t.actions.length ? await actions($, args, t) : { ok: true, message: '' }
  if (r.ok) await setStatus($, t.id, 'applied', t)
  await say($, {
    open: null,
    isError: !r.ok,
    message: r.ok
      ? `Applied "${t.title}". ${r.message}${t.reminder ? ' Reminder on.' : ''}${t.restart ? ' Takes effect in new sessions.' : ''}`
      : r.message,
  })
}

// What Apply would do on this machine, short: the changed lines per file, then what else happens.
async function showPlan($: Api, t: Tip): Promise<void> {
  if ((await read($, view)).plan?.id === t.id) return void update($, view, v => ({ ...v, plan: null })) // second press hides it
  await update($, view, v => ({ ...v, busy: 'Checking your files…' }))
  // A tip with a choice shows its first item; the real choice comes at Apply.
  const items = t.choose ? ['--items', t.choose.items[0]] : []
  const r = t.actions.length ? await actions($, ['apply', t.id, ...items, '--plan'], t) : { ok: true, message: '' }
  const k = t.reminder?.id === 'context-size' ? (await getConfig($)).contextAt / 1000 : undefined
  const notes = [
    !r.ok && `Would fail: ${r.message}`,
    r.ok && r.message.startsWith('No change') && r.message,
    t.choose && `Shown for ${t.choose.items[0]}. Apply asks which of the ${t.choose.items.length} to change.`,
    t.reminder && (t.reminder.idle_ms !== undefined
      ? `A notification after ${Math.round(t.reminder.idle_ms / 60_000)} minutes idle: "${t.reminder.text.replace('{k}', '…')}"`
      : `A toast at ${k ?? '…'}k tokens: "${t.reminder.text.replace('{k}', String(k ?? '…'))}"`),
    t.actions.length > 0 && 'Backed up first to ~/.claude/dutchman/backups. Undo puts it back.',
  ].filter((x): x is string => !!x)
  const diff = r.ok && !r.message.startsWith('No change') ? r.message : ''
  await say($, { plan: { id: t.id, diff, notes } })
}

async function undo($: Api, t: Tip): Promise<void> {
  await update($, view, v => ({ ...v, busy: `Undoing "${t.title}"…` }))
  const r = t.actions.length ? await actions($, ['undo', t.id]) : { ok: true, message: '' }
  if (r.ok) await setStatus($, t.id, undefined, t)
  await say($, { isError: !r.ok, message: r.ok ? `Undone "${t.title}". ${r.message}${t.reminder ? ' Reminder off.' : ''}` : r.message })
}

// ---------- reminders, while the session runs ----------

// Per loaded module, which is per session.
const reminders = new Map<string, Reminder>()
const fired = new Map<string, number>() // context-size reminder: the last threshold toasted
let idleTimer: { cancel: () => void } | undefined
let hasPrompted = false

async function loadReminders($: Api): Promise<void> {
  const state = ((await $.store.get(STATE)) ?? {}) as State
  reminders.clear()
  for (const s of Object.values(state)) if (s.status === 'applied' && s.tip?.reminder) reminders.set(s.tip.reminder.id, s.tip.reminder)
}

async function checkReminders($: Api): Promise<void> {
  idleTimer?.cancel()
  if (reminders.size === 0) return
  const tokens = (await $.session.usage().catch(() => undefined))?.context.tokens
  if (!tokens) return
  const k = String(Math.round(tokens / 1000))
  const { contextAt } = await getConfig($)
  for (const r of reminders.values()) {
    const at = r.id === 'context-size' ? contextAt || undefined : r.at // 0: the user turned it off
    if (at !== undefined) {
      const step = r.every ?? Infinity
      const level = tokens < at ? 0 : at + Math.floor((tokens - at) / step) * step
      if (level > 0 && level > (fired.get(r.id) ?? 0)) {
        fired.set(r.id, level)
        $.ui.toast(r.text.replace('{k}', k), { timeoutMs: 20_000 })
      }
    }
    if (r.on_resume) continue // only at session start, see resumeReminders
    if (r.idle_ms !== undefined && tokens >= (r.min_tokens ?? 0))
      idleTimer = $.clock.after(r.idle_ms, () => {
        void $.ui.notify(r.text.replace('{k}', k), { title: TITLE }).catch(() => $.ui.toast(r.text.replace('{k}', k)))
      })
  }
}

// A session that opens with a big context was resumed: the reminder says so once, before the first turn.
async function resumeReminders($: Api): Promise<void> {
  const rs = [...reminders.values()].filter(r => r.on_resume)
  if (rs.length === 0) return
  const tokens = (await $.session.usage().catch(() => undefined))?.context.tokens
  if (!tokens) return
  for (const r of rs) if (tokens >= (r.min_tokens ?? 0)) $.ui.toast(r.text.replace('{k}', String(Math.round(tokens / 1000))), { timeoutMs: 30_000 })
}

// ---------- the pane ----------

const isOpenTip = (s: State, c: Config, t: Tip) => !s[t.id] && worth(t, c)

function earlier(v: View): Tip[] {
  const res = v.result
  const dismissed = (res?.tips ?? []).filter(t => v.state[t.id]?.status === 'dismissed')
  const applied = Object.values(v.state).flatMap(s => (s.status === 'applied' && s.tip ? [s.tip] : []))
  return [...applied, ...dismissed]
}

// The outcome goes to the store too: the debug log is only written with --debug.
// focus: a pane without the keyboard spends the first click on taking it, so a choice needs two clicks.
async function openPane($: Api, focus = false): Promise<void> {
  const error = await $.ui.open({ id: PANE, title: TITLE, ...(focus ? { focus: true as const } : {}) }).then(() => null, err => String(err))
  if (error) $.ui.log(`dutchman: open: ${error}`, { to: 'debug' })
  await $.store.set('last-open', { at: await $.clock.now(), error })
}

// Once per session, as soon as there is somewhere to show it. The desktop app attaches after
// session.start, so this runs from both session.start and session.attach.
let greeted = false
let analysis: Promise<Result | undefined> = Promise.resolve(undefined)

async function greet($: Api): Promise<void> {
  if (greeted) return
  const surfaces = await $.session.surfaces()
  await $.store.set('last-start', { at: await $.clock.now(), surfaces: surfaces.length })
  if (surfaces.length === 0) return
  greeted = true
  if (!(await $.store.get(CONFIG))) {
    // First session: the welcome screen, once. The defaults hold until Save, also when the pane is closed.
    await $.store.set(CONFIG, DEFAULTS)
    await update($, view, v => ({ ...v, setup: DEFAULTS }))
    return openPane($, true)
  }
  // The last result announces at once; a fresh analysis can take a minute, and a late notice is missed.
  const res = ((await $.store.get(RESULT)) as Result | undefined) ?? (await analysis)
  const c = await getConfig($)
  if (!res || c.notify === 'command') return
  // At most once per period the user picked, and not once the user is working.
  const state = ((await $.store.get(STATE)) ?? {}) as State
  const news = res.tips.filter(t => isOpenTip(state, c, t))
  const now = await $.clock.now()
  const last = ((await $.store.get(ANNOUNCED)) ?? 0) as number
  if (news.length === 0 || (hasPrompted && !DRY) || (!DRY && now - last < OFTEN[c.often])) return
  await $.store.set(ANNOUNCED, now)
  if (c.notify === 'pane') return openPane($)
  // The app puts the plugin's name above a toast, so the text starts with the money. A promised saving and a
  // measured cost ("at stake") stay apart: only an exact or estimated saving is called a saving.
  const save = news.reduce((n, t) => n + (t.saving ?? 0), 0)
  const stake = news.reduce((n, t) => n + (t.saving === null ? t.measured ?? 0 : 0), 0)
  const head = save > 0 && stake > 0 ? `Save ~${money(save)}/mo, and ${money(stake)}/mo more at stake`
    : save > 0 ? `Save ~${money(save)}/mo on Claude Code`
    : stake > 0 ? `${money(stake)}/mo of your Claude Code bill is at stake`
    : 'Claude Code settings that cost you more than needed'
  const n = news.length
  $.ui.toast(`${head}. ${n} tip${n > 1 ? 's' : ''} to bring it down: type /dutchman.`, { timeoutMs: 30_000 })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await $.command.register({ name: 'dutchman', description: 'Cost-saving tips measured on your own logs: /dutchman [refresh|setup]' })
    analysis = (async () => {
      await loadReminders($)
      void resumeReminders($).catch(() => {})
      const state = ((await $.store.get(STATE)) ?? {}) as State
      const cached = (await $.store.get(RESULT)) as Result | undefined
      await update($, view, v => ({ ...v, state, result: cached ?? null }))
      const config = await getConfig($)
      await update($, view, v => ({ ...v, config }))
      const stale = !cached || (await $.clock.now()) - cached.at > REFRESH[config.refresh]
      return DRY || stale ? analyze($) : cached
    })()
    analysis.catch(err => $.ui.log(`dutchman: ${String(err)}`, { to: 'debug' }))
    void greet($).catch(err => $.ui.log(`dutchman: ${String(err)}`, { to: 'debug' }))
    return result
  })

  on('session.attach', async ($, e, next) => {
    const r = await next(e)
    void greet($).catch(err => $.ui.log(`dutchman: ${String(err)}`, { to: 'debug' }))
    return r
  })

  on('turn.start', async ($, e, next) => {
    hasPrompted = true
    idleTimer?.cancel()
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (!e.agentId) void checkReminders($).catch(() => {})
    return r
  })

  on('command.run', { command: 'dutchman' }, async ($, e) => {
    const arg = e.args.trim()
    if (arg === 'setup') {
      const setup = await getConfig($)
      await update($, view, v => ({ ...v, setup }))
      await openPane($, true)
      return { text: 'setup opened.' }
    }
    // A setup left open without Save is dropped: /dutchman shows the tips.
    await update($, view, v => ({ ...v, setup: null }))
    if (arg === 'refresh') void analyze($)
    await openPane($, true)
    return { text: arg === 'refresh' ? 'reading your logs again (about a minute).' : 'opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Code } = $.ui.resolve(e)
    const v = await read($, view)
    const res = v.result
    const set = (patch: Partial<View>) => () => void update($, view, x => ({ ...x, ...patch }))

    const open = res ? res.tips.filter(t => isOpenTip(v.state, v.config, t)) : []
    const hidden = res ? res.tips.filter(t => !v.state[t.id] && !worth(t, v.config)).length : 0
    const past = earlier(v)
    const saving = open.reduce((s, t) => s + (t.saving ?? 0), 0)
    const atStake = open.reduce((s, t) => s + (t.saving === null ? t.measured ?? 0 : 0), 0)
    const short = (t: Tip) =>
      t.saving !== null ? `${t.confidence === 'exact' ? '' : '~'}${money(t.saving)}/mo`
        : t.measured !== null ? `${money(t.measured)}/mo` : ''

    // ---- one summary line; the pane title already says what this is ----
    const summary = res && !res.note
      ? [`${money(res.spend)} in ${res.days} days`, saving > 0 && `~${money(saving)}/mo to save`,
          atStake > 0 && `${money(atStake)}/mo at stake`,
          hidden > 0 && `${hidden} under $${v.config.minSaving}/mo hidden`].filter(Boolean).join('  ·  ')
      : ''
    const header = (
      <Box flexDirection="row" justifyContent="space-between" marginBottom={1}>
        <Box flexDirection="column" flexShrink={1} marginRight={2}>
          <Text dimColor>{summary}{DRY ? '  ·  test mode' : ''}</Text>
          {summary && <Text dimColor>Amounts are at list price and count only logged calls; your bill can differ by a few percent.</Text>}
        </Box>
        <Button key="refresh" plain dimColor onPress={() => void analyze($)}>Refresh</Button>
      </Box>
    )

    const status = (
      <Box flexDirection="column">
        {v.busy && <Box marginBottom={1}><Text color="warning">{v.busy}</Text></Box>}
        {!v.busy && v.message && (
          <Box flexDirection="row" justifyContent="space-between" marginBottom={v.preview ? 0 : 1}>
            <Text color={v.isError ? 'error' : 'success'}>{v.message}</Text>
            <Button key="clear" plain dimColor onPress={set({ message: null, preview: null })}>✕</Button>
          </Box>
        )}
        {v.preview && (
          <Box marginBottom={1}><Code source={v.preview} format={v.preview.startsWith('---') ? 'diff' : 'source'} /></Box>
        )}
      </Box>
    )

    const tabs = (
      <Box flexDirection="row" gap={1} marginBottom={1}>
        <Button key="tab-open" variant={v.tab === 'open' ? 'primary' : 'secondary'} onPress={set({ tab: 'open', open: null })}>
          {`Open ${open.length}`}</Button>
        <Button key="tab-earlier" variant={v.tab === 'earlier' ? 'primary' : 'secondary'} onPress={set({ tab: 'earlier', open: null })}>
          {`Applied & dismissed ${past.length}`}</Button>
        <Button key="tab-settings" variant={v.tab === 'settings' ? 'primary' : 'secondary'} onPress={set({ tab: 'settings', open: null })}>
          Settings</Button>
      </Box>
    )

    // ---- a setting: the label with a short hint, the options as one row, the picked one highlighted ----
    const choice = <T extends string | number,>(key: string, label: string, hint: string, value: T,
      options: [T, string][], pick: (value: T) => void, recommended?: T) => (
      <Box key={key} flexDirection="column" marginBottom={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Box flexShrink={1} marginRight={2}><Text>{label}<Text dimColor>  {hint}</Text></Text></Box>
          {recommended !== undefined && (
            <Text dimColor>{value === recommended ? 'recommended' : `recommended: ${options.find(o => o[0] === recommended)?.[1]}`}</Text>
          )}
        </Box>
        <Box flexDirection="row" gap={1}>
          {options.map(([val, text]) => (
            <Button key={`${key}-${val}`} variant={val === value ? 'primary' : 'secondary'} onPress={() => pick(val)}>{text}</Button>
          ))}
        </Box>
      </Box>
    )
    const heading = (text: string) => <Text key={`h-${text}`} dimColor bold>{text}</Text>

    const MIN: [number, string][] = [[1, '$1'], [5, '$5'], [20, '$20'], [0, 'Any']]
    const NOTIFY: [Config['notify'], string][] = [['toast', 'Notice'], ['pane', 'Open pane'], ['command', 'Quiet']]
    const OFTEN_OPTS: [Config['often'], string][] = [['session', 'Every session'], ['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly']]
    const CONTEXT: [number, string][] = [[150_000, '150k'], [250_000, '250k'], [400_000, '400k'], [0, 'Never']]

    // ---- welcome: the first session, or /dutchman setup ----
    if (v.setup) {
      const d = v.setup
      const draft = (patch: Partial<Config>) => void update($, view, x => ({ ...x, setup: { ...d, ...patch } }))
      const start = async () => {
        await update($, view, x => ({ ...x, setup: null, tab: 'open', open: null }))
        await setConfig($, d)
      }
      return (
        <Box flexDirection="column">
          <Box marginBottom={1}><Text dimColor>Reads your Claude Code logs on this machine. Nothing changes until you press Apply.</Text></Box>
          {choice('min', 'Show tips from', 'per month', d.minSaving, MIN, x => draft({ minSaving: x }), 5)}
          {choice('notify', 'Open tips', 'at session start', d.notify, NOTIFY, x => draft({ notify: x }), 'pane')}
          {choice('often', 'Show them', 'at most', d.often, OFTEN_OPTS, x => draft({ often: x }), 'weekly')}
          {choice('context', 'Nudge past', 'tokens in one session', d.contextAt, CONTEXT, x => draft({ contextAt: x }), 250_000)}
          <Box flexDirection="row" alignItems="center" gap={2} marginTop={1}>
            <Box borderStyle="round" borderColor="success" paddingX={1}>
              <Button key="start" variant="primary" autoFocus onPress={() => void start()}>Save</Button>
            </Box>
            <Text dimColor>Change it later under Settings</Text>
          </Box>
        </Box>
      )
    }

    // ---- settings ----
    if (v.tab === 'settings') {
      const c = v.config
      return (
        <Box flexDirection="column">
          {header}
          {status}
          {tabs}
          {heading('TIPS')}
          {choice('min', 'Show tips from', 'per month', c.minSaving, MIN, x => void setConfig($, { minSaving: x }), 5)}
          {choice('notify', 'Open tips', 'at session start', c.notify, NOTIFY, x => void setConfig($, { notify: x }), 'pane')}
          {c.notify !== 'command' && choice('often', 'Show them', 'at most', c.often, OFTEN_OPTS, x => void setConfig($, { often: x }), 'weekly')}
          {heading('REMINDERS')}
          {choice('context', 'Nudge past', 'tokens in one session', c.contextAt, CONTEXT, x => void setConfig($, { contextAt: x }), 250_000)}
          {choice('stake', 'Cache reminder from', 'lost to expired caches per month', c.cacheStake,
            [[5, '$5'], [20, '$20'], [0, 'Never']], x => void setConfig($, { cacheStake: x }), 5)}
          {heading('ANALYSIS')}
          {choice('days', 'Read logs of', 'the last', c.days, [[14, '14 days'], [30, '30 days'], [90, '90 days']],
            x => void setConfig($, { days: x }), 30)}
          {choice('refresh', 'Analyse again', 'at session start', c.refresh,
            [['daily', 'Daily'], ['weekly', 'Weekly'], ['manual', 'Only on Refresh']], x => void setConfig($, { refresh: x }), 'daily')}
        </Box>
      )
    }

    if (!res || res.note)
      return <Box flexDirection="column">{header}{status}{tabs}<Text dimColor>{res?.note ?? 'No analysis yet. Press Refresh.'}</Text></Box>

    const KINDS = {
      fix: { label: 'Fixes', verb: 'Apply' },
      reminder: { label: 'Reminders', verb: 'Turn on' },
      check: { label: 'Checks', verb: 'Apply' },
    } as const
    const field = (label: string, text: string | null | undefined) =>
      text ? (
        <Box flexDirection="row" marginBottom={1}>
          <Box width={9} flexShrink={0}><Text dimColor>{label}</Text></Box>
          <Box flexGrow={1} flexShrink={1}><Text>{text}</Text></Box>
        </Box>
      ) : null

    const tip = (t: Tip) => {
      const st = v.state[t.id]?.status
      const isOpen = v.open === t.id
      return (
        <Box key={t.id} flexDirection="column" marginBottom={isOpen ? 1 : 0}>
          <Box flexDirection="row" justifyContent="space-between">
            <Box flexShrink={1}>
              <Button key={`row-${t.id}`} plain onPress={set({ open: isOpen ? null : t.id, preview: null, message: null, plan: null })}>
                <Text dimColor>{isOpen ? '▾ ' : '▸ '}</Text><Text bold={isOpen}>{t.title}</Text>
              </Button>
            </Box>
            <Box flexShrink={0} marginLeft={2}><Text dimColor>{st ?? short(t)}</Text></Box>
          </Box>
          {isOpen && (
            <Box flexDirection="column" marginTop={1} paddingLeft={2}>
              {field('Why', t.problem)}
              {field('How', t.how)}
              {t.saving !== null && field('Saving', `${t.confidence === 'exact' ? '' : 'about '}${money(t.saving)} per month at list price` +
                (t.confidence === 'exact' ? ', replayed on your own logs.' : '.'))}
              {field('Assumes', t.assumption)}
              {t.change && field(st === 'applied' ? 'Changed' : 'Changes', t.change +
                (t.actions.length ? ' Every file is backed up first; Undo puts it back.' : '') +
                (t.restart ? ' Takes effect in new sessions.' : ''))}
              {field('Do it', t.next)}
              {v.plan?.id === t.id && (
                <Box flexDirection="column" marginBottom={1}>
                  {v.plan.diff && <Code source={v.plan.diff} format="diff" />}
                  {v.plan.notes.map((n, i) => <Text key={`note-${i}`} dimColor>{n}</Text>)}
                </Box>
              )}
              <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                <Box flexDirection="row" gap={1}>
                  {!st && t.change && <Button key={`apply-${t.id}`} variant="primary" onPress={() => void apply($, t)}>{KINDS[t.kind].verb}</Button>}
                  {!st && t.change && <Button key={`plan-${t.id}`} onPress={() => void showPlan($, t)}>
                    {v.plan?.id === t.id ? 'Hide' : 'What will this do for me?'}</Button>}
                  {st === 'applied' && <Button key={`undo-${t.id}`} variant="primary" onPress={() => void undo($, t)}>Undo</Button>}
                  {!st && <Button key={`dismiss-${t.id}`} onPress={() => void setStatus($, t.id, 'dismissed').then(set({ open: null }))}>Dismiss</Button>}
                  {st === 'dismissed' && <Button key={`restore-${t.id}`} onPress={() => void setStatus($, t.id, undefined)}>Restore</Button>}
                </Box>
                <Text dimColor>Guide §{t.guide}</Text>
              </Box>
            </Box>
          )}
        </Box>
      )
    }

    const value = (t: Tip) => t.saving ?? t.measured ?? 0
    const section = (kind: Tip['kind'], tips: Tip[]) =>
      tips.length === 0 ? null : (
        <Box key={`sec-${kind}`} flexDirection="column" marginBottom={1}>
          <Text dimColor bold>{KINDS[kind].label.toUpperCase()}</Text>
          {[...tips].sort((a, b) => value(b) - value(a)).map(tip)}
        </Box>
      )

    const list = v.tab === 'open' ? open : past
    return (
      <Box flexDirection="column">
        {header}
        {status}
        {tabs}
        {list.length === 0
          ? <Text dimColor>{v.tab === 'open' ? 'No open tips: your setup already does what the guide suggests.' : 'Nothing applied or dismissed yet.'}</Text>
          : (['fix', 'reminder', 'check'] as const).map(kind => section(kind, list.filter(t => t.kind === kind)))}
      </Box>
    )
  })
}
