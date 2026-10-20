export type TipKind = 'fix' | 'reminder' | 'check'

export type Reminder = {
  id: string
  text: string // {k}: the context size in thousands
  at?: number // context-size reminder: first at this many tokens
  every?: number // and again at each this many more
  idle_ms?: number // idle reminder: after this long without a turn
  min_tokens?: number // only for a context at least this big
}

export type Tip = {
  id: string
  kind: TipKind
  category: string
  confidence: 'exact' | 'estimate' | 'measured' | 'config'
  title: string
  saving: number | null
  measured: number | null
  problem: string
  how: string
  assumption: string | null
  change: string | null // null: nothing for the plugin to change; `next` says what the user can do
  next?: string
  actions: unknown[]
  reminder?: Reminder
  choose?: { question: string; items: string[] }
  min_version?: string
  restart: boolean
  guide: string
}

export type Result = { days: number; spend: number; calls: number; tips: Tip[]; note?: string; errors?: string[]; at: number }
export type Status = { status: 'dismissed' | 'applied'; at: number; tip?: Tip }
export type State = Record<string, Status>

export type Config = {
  minSaving: number // hide tips worth less per month; tips without an amount always show
  notify: 'toast' | 'pane' | 'command' // how new tips announce themselves at session start
  contextAt: number // long-session reminder threshold in tokens; 0: never
  days: number // how far back the analysis reads
  refresh: 'daily' | 'weekly' | 'manual'
  cacheStake: number // cache-expiry reminder only when at least this much per month is at stake; 0: never
}

export type View = {
  result: Result | null
  state: State
  open: string | null // the expanded tip
  busy: string | null // what runs now, shown at the top
  message: string | null // the last outcome
  isError?: boolean // whether that outcome is a failure
  preview: string | null // a dry-run diff
  tab: 'open' | 'earlier' | 'settings'
  config: Config
  setup: Config | null // the welcome screen's picks while it shows
}

declare module 'claude-code' {
  interface PluginState {
    'burndown': { view: View }
  }
}
