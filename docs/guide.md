# Fewer tokens, same work: a Claude Code cost guide

This guide comes with Burndown, a Claude Code plugin that measures each of these tips on your own session logs.

By Daan Meersseman (@daanmeersseman), with measurements from Mark, a colleague. Every tip comes with what it did for one of us, measured at Anthropic list price. Your numbers will differ. The ratios are what matter.

> **In one sentence:** most of the money goes on re-sending the whole context every turn. The model's answers are a small part. Keep the context small, keep the cache warm, and pick the cheapest model that can do the work.

---

## Start in 5 minutes

1. **Measure your baseline.** Start a fresh session, type nothing, and run `/context`. That number is what you pay on every turn.
2. **Price your last month.** Run [`price_logs.py`](#a3-price_logspy-price-your-session-logs) (Appendix A3). It shows where your money goes: cache writes, output, which model, which agent.
3. **Pick a profile** and paste it into `~/.claude/settings.json`:

**Profile A: light work** (search, analysis, questions, small fixes)

```json
{
  "model": "claude-haiku-5-5[1m]",
  "outputStyle": "Concise",
  "env": { "CLAUDE_CODE_SUBAGENT_MODEL": "claude-haiku-5-5[1m]" }
}
```

**Profile B: implementation work** (features, bugs across several files)

```json
{
  "model": "opusplan",
  "permissions": { "defaultMode": "plan" },
  "outputStyle": "Concise",
  "env": { "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-5-5" },
  "modelSettings": {
    "claude-opus-5-5":   { "effortLevel": "medium" },
    "claude-sonnet-5-5": { "effortLevel": "high" }
  }
}
```

Restart Claude Code after changing settings.

### The top 10

| # | Tip | Effort | Measured effect |
|---|---|---|---|
| 1 | Disable unused MCP servers and plugins (§3.1) | 2 min | baseline 133k → 61k, on every turn (one author) |
| 2 | One task per session, handover instead of `/resume` (§4) | habit | two runaway sessions were 40% of two weeks' spend (one author) |
| 3 | Don't let the cache go cold (§5) | habit | a cold turn costs up to 25× a warm one |
| 4 | `opusplan`: Opus plans, Sonnet executes (§6.2) | 1 line | main sessions −11% (one author) |
| 5 | Subagents on a cheaper model (§6.3) | 1 line | those calls −34% (one author) |
| 6 | Effort `medium` on Opus (§6.4) | 1 line | xhigh writes 2.6× the output of medium (one author) |
| 7 | RTK: condensed command output (§7) | 5 min | command output −73% (one author) |
| 8 | Path-scoped rules (§3.3) | per rule | 58k tokens of rules load only when needed (one author) |
| 9 | Ponytail: smallest change that works (§8) | 2 min | −26% cost in the author's benchmark |
| 10 | A cost meter and budgets (§9) | 5 min | you see what a turn costs while you work |

---

## 1. How Claude Code is billed

Every message re-sends **the whole context**:

```
cost of one turn ≈ (system prompt + tools + memory + skills + whole conversation)  ← input, mostly from cache
                 + the model's answer                                              ← output
```

**Example:** a 40-turn session with ~1k output per turn.

| Average context | Input over 40 turns | Output |
|---|---|---|
| 50k | 2,000,000 tokens | ~40,000 tokens |
| 200k | 8,000,000 tokens | ~40,000 tokens |

Same work, four times the input. **Context size × number of turns decides the bill.** Every tip below cuts one of those two, or makes the tokens cheaper.

---

## 2. Measure first

| Tool | Shows |
|---|---|
| `/context` | what is in the context now; in a fresh session, your **baseline** |
| `/mcp` | which MCP servers are on |
| `/cost`, `/usage` | session cost and cache hit rate |
| `price_logs.py` (A3) | cost per type, model and agent type over all your sessions |

**In `/context`, look at:** System tools (includes MCP tools, usually the biggest surprise), Memory files, Skills, Messages. Everything except Messages is paid on every turn.

**Comparing two setups:** same model, same task. Compare `/context` in a fresh session and `/cost` at the end. Take several snapshots, because `/context` shows only the current moment.

---

## 3. Cut the fixed cost (baseline)

### 3.1 MCP servers and plugins

- Every MCP server adds **all its tool descriptions** to the context, used or not. One author's largest one was 83k tokens.
- **Rule:** whatever the current work doesn't need stays off. Enable a server only for the session that needs it.
- **Watch out:** toggling a server mid-session can invalidate the cache. Do it at the start.

**One author's result:** baseline 133k → 61k (−54%), on every turn.

### 3.2 CLAUDE.md and memory

- **Delete what the model does well without it.** If removing a rule doesn't change the behavior, it wasn't needed.
- **One rule, one line.** "Use pnpm, not npm." beats a paragraph.
- **`@import` saves nothing:** the file loads in full. Write the path instead ("Deploy: `docs/deploy.md`") and the model reads it when needed.
- **Look for duplicates** between global and project level.
- **Don't cut** security, data-loss and project-specific rules for length.

**For scale:** 10k always-on tokens cost one author about $85 in four weeks.

### 3.3 Path-scoped rules

A rule in `.claude/rules/*.md` with a `paths:` header loads only when Claude reads or edits a matching file:

```markdown
---
description: "React components: data fetching and state"
paths:
  - "web/src/components/**"
  - "web/src/hooks/**"
---
- **MUST** fetch data through `useQuery`; never call `fetch` inside a component.
```

- Without `paths:`, the rule loads at startup, like CLAUDE.md. User level works too: `~/.claude/rules/`.
- **Watch out:** a glob that matches almost everything makes the rule always-on again.

**One author's result:** 29 of the 33 rules in their main repo are path-scoped, about 58k tokens that load only when needed.

### 3.4 Skills

Only a skill's `description` is always in the context. The body loads when the skill runs.

- **Short description that answers "when".** It is a trigger. Keep documentation in the body.
- **`disable-model-invocation: true`** for skills you only start yourself (`/handover`, `/deploy`): their description leaves the context.
- **Details in separate files** in the skill folder.
- **Router skill** for large knowledge bases: the skill picks only the files that match the topic and states the cost before loading:

```markdown
Domain knowledge lives in 21 files (~50k tokens). Never read them all.
Map the user's topic to a row in the table below and read only those files.
Say what you load and the estimated cost in one line: "Load: 04-grid, 15-ui-specs (~7k tokens)."
```

**One author's result:** a router skill loads 2k to 13k tokens instead of 50k.

---

## 4. Session hygiene

- **One task, one session.** A new, unrelated task: `/clear`.
- **Don't `/resume` a long session.** It reloads everything, often onto a cold cache. Use a handover: `/handover` → `/clear` → `/handover resume`. The skill is in Appendix A1.
- **`/compact`** when the same task continues; you can say what to keep: `/compact keep the debugging findings`.
- **Start sessions that don't read code outside the repo.** A repo's CLAUDE.md and rules load on every turn. One author's PR follow-up session went from 100k to 68k tokens at the first turn by starting in the home folder.

**Thresholds:**

| Context | Action |
|---|---|
| ~250k | `/compact` for the same task, otherwise handover |
| ~300k | handover, then `/clear` |
| auto-compact limit | the last line; don't let it decide |

A hook that warns you at these thresholds is in Appendix A2.

**Watch out:** don't set `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` low; it compacts every few minutes. Change the window size (`autoCompactWindow`) instead.

**One author's result:** two sessions that grew to 579k and 886k were 40% of two weeks' spend.

---

## 5. The cache

The context is read from the cache at about a tenth of the input price, **as long as the cache is alive**.

| Operation | Price vs normal input |
|---|---|
| Cache read | 0.1× (0.05× on Opus 5.5) |
| Cache write, 5-minute lifetime | 1.25× |
| Cache write, 1-hour lifetime | 2× |

**Opus 5.5, 200k context:** warm turn ≈ $0.04, cold turn ≈ $1.00.

**What makes it go cold:**
- a pause longer than the cache lifetime (default 5 minutes),
- switching models (including approving a plan under `opusplan`),
- changing the tool list (MCP on or off) or the effort level on some models.

**Rules:**
- Before a longer break with a large context: handover and `/clear`.
- Switch models only at phase boundaries.
- Pick effort and model at the start of a session.

### 5.1 5 minutes or 1 hour?

The 1-hour cache doubles the write price, so it only pays off if you often pause between 5 and 60 minutes. **Measure, then choose.** The Burndown plugin's 1-hour cache tip back-tests the 1-hour cache on your own logs.

```json
{ "promptCacheTtl": "1h" }
```

- Count the pauses that aren't breaks: Claude waiting for your plan approval, a subagent or a build. For one author that was a third of the pause rewrites.
- Applies to the main session only. Subagents have their own setting (`subagentPromptCacheTtl`).
- **Check:** after the switch, `ephemeral_1h_input_tokens` in your session logs is above 0.

**One author's result:** 1h would have saved 11% of main-session cost over 30 days, so they switched.

---

## 6. The right model for the job

### 6.1 Prices

| Model | Input / output per 1M tokens | Input ratio |
|---|---|---|
| Haiku 5.5 | $0.10 / $0.50 | 1× |
| Sonnet 5.5 | $2 / $10 | 20× |
| Opus 5.5 | $4 / $20 | 40× |

Cache reads cost $0.20 on both Sonnet and Opus 5.5.

**Model IDs:** `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`. `[1m]` requests the 1M window. Treat it as headroom and keep your context small.

**Trap:** `/model` saves the new model as your default for future sessions.

### 6.2 Choose by type of work

| Work | Setup |
|---|---|
| Search, analysis, questions, simple fixes | **Profile A:** Haiku. Step up to Sonnet or Opus when the cause isn't found after two attempts, or a wrong decision would be expensive. |
| Implementation across several files | **Profile B:** `opusplan`. Opus writes the plan in plan mode; after you approve it, Sonnet does the work. |
| Large tasks (8+ files, independent parts) | An Opus orchestrator that delegates parts to Sonnet or Haiku subagents (below). |

**`opusplan` tips:**
- With `defaultMode: "plan"`, every session starts with a plan.
- Approving a plan is a model switch, so the context is written to the cache again. Plan the whole task and approve once.

**One author's result:** Sonnet turns cost 35% less than the same turns on Opus; net −11% on main sessions after the switch cost.

### 6.3 Subagents

A subagent works in its own context and returns a short summary, so your main context stays small.

```markdown
---
name: research-scout
description: Code search in the repo, docs and web research. Returns a short summary.
model: haiku
tools: Read, Grep, Glob, WebFetch, WebSearch
maxTurns: 20
---
Search, read, compare. Answer in under 200 words: the finding, file paths with line numbers, what remains uncertain.
```

| Task | Model |
|---|---|
| Repo search, docs, research, logs, JSON, commit messages | Haiku |
| Mechanical edits from an exact plan, one well-bounded part with a test | Sonnet |
| Decisions: architecture, security, root cause, review | Opus |

- **Set a default** for built-in subagents (`general-purpose`, `Explore`): `CLAUDE_CODE_SUBAGENT_MODEL`. A `model` in an agent file wins over it; `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` overrides everything.
- **Give paths and function names.** Don't paste code. The brief must stand on its own.
- **Don't delegate trivia.** For one or two files, doing it yourself is cheaper.
- `maxTurns` stops an agent that goes in circles.
- **Check** which model ran: `/tasks`, or the "By agent" lines of `price_logs.py`. Agent files go in `~/.claude/agents/` or `.claude/agents/`; a misspelled field is silently ignored (`claude --debug` shows it).

**One author's result:** built-in subagents ran on Opus by default; on Sonnet those calls cost 34% less.

### 6.4 Effort

Effort sets how long the model thinks. Thinking is billed as output, and it is most of the output (about 75% of Opus output for one author).

```json
"modelSettings": {
  "claude-opus-5-5":   { "effortLevel": "medium" },
  "claude-sonnet-5-5": { "effortLevel": "high" }
}
```

- **Rule:** medium or high for daily work. `/effort xhigh` or `max` for one hard problem, in that session only.
- **Watch out:** a top-level `effortLevel` does nothing for Opus 5.5. Use `modelSettings` or `/effort`.

**One author's result:** on Opus, medium and high gave the same amount of output; xhigh gave 2.6×.

---

## 7. Less noise in the context

Anything that enters the conversation is re-read on every later turn (about 30 turns on average for one author).

- **Targeted reads.** `grep` first, then read only that part.
- **Don't re-read** a file that is already in the context.
- **Filter logs** (`grep`, `tail -50`) before they enter the context.
- **Specific requests.** "Fix `applyDiscount` in `checkout.ts`" needs less searching than "fix the checkout bug".
- **Ask in one go.** Three questions are three turns.
- **Let a script do the bookkeeping.** If the model keeps calling `gh` or reading state files to know where it is, write a script that prints one finished summary. One author's `/pr-review` skill had 6 to 8 such calls per run, each re-reading a 100 to 160k context: a third of the run's cost.

### 7.1 RTK: condensed command output

A hook that condenses Bash output (build, test, git, grep) before it enters the context.

- Install: `rtk init -g`. **Check:** `rtk gain`.
- Trust the condensed result; ask for raw output only when it is clearly unusable.
- **Watch out:** in git worktree sessions, the worktree guard refuses `rtk git ...`. Appendix A4 has a hook wrapper that skips git there.

**One author's result:** command output −73% (1.3M tokens in six days).

### 7.2 Screenshots and Playwright

- An image is 1,000 to 4,000 tokens and stays until the session ends. Only when justified.
- Playwright's `browser_snapshot` and `browser_network_requests` return about 7k characters each. `browser_evaluate` returns under 1k.
- **Rule:** measure with `browser_evaluate` (sizes, colors, text). Save screenshots to a file. Let a Sonnet subagent do it and return only values and file paths:

```markdown
- Never return an image. Save every screenshot with browser_take_screenshot (filename) and return the path.
- Do not paste accessibility snapshots, DOM dumps or logs into your report.
- Measure with browser_evaluate: getBoundingClientRect, getComputedStyle, textContent.
```

---

## 8. Less output

- **Concise output style:** `"outputStyle": "Concise"` (case-sensitive; `"concise"` falls back to Default). Answer first, no recap. The cost effect is small, because most output is thinking. You mainly save reading time.
- **Ponytail** makes the model work like a "lazy senior developer": the smallest change that fully works, no abstractions for later. Author's benchmark: −53% code, −26% cost, −45% tokens, and 98% of risky logic gets a test (68% without). It adds about 580 tokens to the baseline. Not measured by us yet.

---

## 9. See what you spend

- **Status line:** Claude Code passes `cost.total_cost_usd` to a status line script. Show it while you work.
- **Frugalitas:** session, day and month spend in the status line, budgets with a warning or `block` mode, and a cache countdown (`⏳ cache 3:42`) that shows what the rewrite will cost. It reads spend from a LiteLLM proxy, so it fits teams that route Claude Code through one.

```
/plugin install frugalitas --marketplace siposzoltan03/frugalitas
```

Budgets via `/config` → frugalitas. Defaults: $20 per session, $60 per day, $800 per month.

---

## 10. Common mistakes

| Mistake | Why it's expensive | Instead |
|---|---|---|
| A session running for days | every turn carries the whole history | one task, one session; handover |
| An MCP server that is always on | its tool descriptions on every turn | enable it for that work only |
| Opus for everything | 40× Haiku's input price | a profile per type of work (§6.2) |
| Switching models back and forth | every switch rewrites the cache | switch at phase boundaries |
| `/resume` on a long session | everything reloaded, often cold | `/handover` → `/clear` → `/handover resume` |
| Continuing after a long break | cold cache, full rewrite | handover before the break |
| `/effort max` as default | thinking is billed as output | medium or high; max for one problem |
| Built-in subagents on your main model | Opus price for search work | `CLAUDE_CODE_SUBAGENT_MODEL` |
| 1-hour cache without measuring | double write price | measure your pauses first (§5.1) |
| Very low auto-compact percentage | constant re-compaction | change the window size |

---

## Works only if

- **Frugalitas:** needs Claude Code routed through a LiteLLM gateway (`ANTHROPIC_BASE_URL`).
- **Desktop app:** `/plugin install` doesn't work there. Use a terminal.
- **Claude Code version:** `promptCacheTtl` needs v2.1.242+, `modelSettings` v2.1.251+. Update if a setting has no effect.
- After changing settings or environment variables, **fully restart** Claude Code.

---

# Appendix

## A1. `/handover` skill

`~/.claude/skills/handover/SKILL.md`:

```markdown
---
name: handover
description: Write a handover doc so the session can be cleared, or resume from one. Use when the user runs /handover or /handover resume.
argument-hint: "[resume]"
disable-model-invocation: true
---

If `$ARGUMENTS` is `resume`:
1. Find the newest `docs/*-handover.md` in the repo (`ls -t docs/*-handover.md`). If there is none, say so and stop. If several are recent and it's unclear which task is meant, ask.
2. Read it. Read only the files it names that the next step needs.
3. Summarize in 3 to 5 lines: goal, state, next step. Then do the next step, unless the handover says to wait for the user.

Otherwise, write a handover:
1. File: `docs/<task-slug>-handover.md`. Overwrite the same task's earlier handover.
2. Sections: **Goal**, **State** (done / in progress, with file paths), **Decisions** (with the why), **Open points and risks**, **Next step** (one concrete action), **How to verify** (commands).
3. At most ~60 lines. Paths and function names, not pasted code. No narration of the conversation.
4. Do not commit it.
5. End with: `Handover: <path>. Next: /clear, then /handover resume.`
```

## A2. Context warning hook

`~/.claude/hooks/context-guard.mjs`:

```js
#!/usr/bin/env node
import { readFileSync } from 'node:fs'

const COMPACT_AT = 250_000
const HANDOVER_AT = 300_000

try {
  const { transcript_path } = JSON.parse(readFileSync(0, 'utf8'))
  const lines = readFileSync(transcript_path, 'utf8').trimEnd().split('\n').reverse()

  let tokens = 0
  for (const line of lines) {
    let e
    try { e = JSON.parse(line) } catch { continue }
    const u = e.message?.usage
    if (e.type !== 'assistant' || e.isSidechain || !u) continue // subagent messages don't count
    tokens = (u.input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0)
    break
  }

  const k = `${Math.round(tokens / 1000)}k`
  const msg = tokens >= HANDOVER_AT ? `🛑 Context: ${k}. /handover, then /clear.`
            : tokens >= COMPACT_AT ? `⚠️ Context: ${k}. Consider /compact or a handover.`
            : null
  if (msg) process.stdout.write(JSON.stringify({ systemMessage: msg }))
} catch {} // a hook failure must never block the prompt
```

Register it in `settings.json`:

```json
"hooks": {
  "UserPromptSubmit": [
    { "hooks": [ { "type": "command", "command": "node /ABSOLUTE/PATH/context-guard.mjs" } ] }
  ]
}
```

Test: `echo '{"transcript_path":"/path/to/session.jsonl"}' | node context-guard.mjs`

## A3. `price_logs.py`: price your session logs

Python 3, no packages. Logs live in `~/.claude/projects/` and are deleted after 30 days (`cleanupPeriodDays`).

```bash
python price_logs.py               # all logs
python price_logs.py 2026-10-14    # since a date
```

```python
"""Price your Claude Code session logs at Anthropic list price (USD). Usage: python price_logs.py [YYYY-MM-DD]"""
import collections, glob, json, os, sys

# USD per 1M tokens: input, output, cache read, cache write 5m, cache write 1h. The first matching key wins.
# shortcut: Haiku 5.5 costs 5x above 100k-token prompts, not priced here; fine unless Haiku runs your main session.
PRICES = {
    'opus-5-5': (4, 20, .2, 5, 8), 'opus-5': (5, 25, .5, 6.25, 10),
    'sonnet-5': (2, 10, .2, 2.5, 4),
    'haiku-5-5': (.1, .5, .01, .125, .2), 'haiku-4-5': (1, 5, .1, 1.25, 2),
}
since = sys.argv[1] if len(sys.argv) > 1 else ''
calls = {}
for path in glob.glob(os.path.expanduser('~/.claude/projects/**/*.jsonl'), recursive=True):
    agent = 'main'
    if os.sep + 'subagents' + os.sep in path:
        try:
            agent = json.load(open(path[:-6] + '.meta.json', encoding='utf-8')).get('agentType', '?')
        except OSError:
            agent = '?'
    for line in open(path, encoding='utf-8', errors='replace'):
        try:
            e = json.loads(line)
            mid, model, u = e['message']['id'], e['message']['model'], e['message']['usage']
        except (ValueError, KeyError, TypeError):
            continue
        if e.get('type') != 'assistant' or e.get('timestamp', '') < since:
            continue
        old = calls.get(mid)
        # streaming writes one message as several lines: keep the one with the most output
        if old is None or (u.get('output_tokens') or 0) > (old[2].get('output_tokens') or 0):
            calls[mid] = (model, agent, u)

by_type, by_model, by_agent, unpriced = (collections.Counter() for _ in range(4))
for model, agent, u in calls.values():
    price = next((p for k, p in PRICES.items() if k in model), None)
    if price is None:
        unpriced[model] += 1
        continue
    cc = u.get('cache_creation') or {}
    w5, w1 = cc.get('ephemeral_5m_input_tokens') or 0, cc.get('ephemeral_1h_input_tokens') or 0
    if not (w5 or w1):  # older log lines have no 5m/1h split
        w5 = u.get('cache_creation_input_tokens') or 0
    tokens = (u.get('input_tokens') or 0, u.get('output_tokens') or 0, u.get('cache_read_input_tokens') or 0, w5, w1)
    for name, t, p in zip(('input', 'output', 'cache read', 'cache write 5m', 'cache write 1h'), tokens, price):
        by_type[name] += t * p / 1e6
    cost = sum(t * p for t, p in zip(tokens, price)) / 1e6
    by_model[f"{model} ({'main' if agent == 'main' else 'subagent'})"] += cost
    by_agent[agent] += cost

total = sum(by_type.values())
print(f'{sum(1 for c in calls.values() if c[0] not in unpriced)} calls, ${total:,.2f}. Not priced: {dict(unpriced)}')
for title, c in (('cost type', by_type), ('model', by_model), ('agent', by_agent)):
    print(f'\nBy {title}:')
    for k, v in c.most_common(10):
        print(f'  {k:40} ${v:9,.2f} {v / total:6.1%}')
```

## A4. RTK hook wrapper for worktree sessions

Register this instead of `rtk hook claude` as the `PreToolUse` hook for Bash:

```js
// Runs `rtk hook claude`, except for git commands in worktree sessions: their isolation guard refuses `rtk git ...`.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const input = readFileSync(0, "utf8");
let cwd = "", cmd = "";
try { const j = JSON.parse(input); cwd = j.cwd ?? ""; cmd = j.tool_input?.command ?? ""; } catch {}
if (/[\\/]\.claude[\\/]worktrees[\\/]/.test(cwd) && /\bgit\b/.test(cmd)) process.exit(0);

const r = spawnSync("rtk", ["hook", "claude"], { input, encoding: "utf8", shell: true });
process.stdout.write(r.stdout ?? "");
process.stderr.write(r.stderr ?? "");
process.exit(r.status ?? 0);
```
