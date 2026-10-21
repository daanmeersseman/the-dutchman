// The pane's pure helpers, apart from register.tsx so tests/logic.test.ts can run them without a session.

export const money = (n: number) => `$${n < 10 ? n.toFixed(2) : Math.round(n)}`

export const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

// Whether version have is older than need, compared as major.minor.patch.
export function older(have: string, need: string): boolean {
  const [a, b] = [have, need].map(v => v.split('.').map(Number))
  for (let i = 0; i < 3; i++) if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) < (b[i] ?? 0)
  return false
}

// The context-size threshold a session has passed: at, then each `every` more. 0 while below at.
export function reached(tokens: number, at: number, every?: number): number {
  if (tokens < at) return 0
  return every ? at + Math.floor((tokens - at) / every) * every : at
}

// How long a session may sit idle before the reminder, `before` ms ahead of the cache expiring.
// setting: promptCacheTtl as it is now, so a 1-hour cache applied after the analysis counts.
export const idleBeforeExpiry = (setting: unknown, before: number) => (setting === '1h' ? 3_600_000 : 300_000) - before

// The notice at session start. The app shows the plugin's name above it, so it starts with the money.
// A promised saving and a measured cost ("at stake") stay apart.
export function noticeText(save: number, stake: number, n: number): string {
  const head = save > 0 && stake > 0 ? `~${money(save)}/mo to save, ${money(stake)}/mo at stake`
    : save > 0 ? `~${money(save)}/mo to save on Claude Code`
    : stake > 0 ? `${money(stake)}/mo of your Claude Code bill at stake`
    : 'Claude Code settings that cost more than needed'
  return `${head}. ${n} ${plural(n, 'tip', 'tips')}: type /dutchman.`
}
