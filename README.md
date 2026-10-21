<h1>
  <img src="assets/icon.svg" alt="" width="48" align="center">
  The Dutchman
</h1>

**Not a cent more on Claude Code than needed.** The Dutchman reads your own Claude Code logs, finds the settings and
habits that cost you money, and tells you how much. One click applies the fix, and one click undoes it.

As we all know, the Dutch are notoriously stingy. And yet we could all use a Dutchman looking over our shoulder
while we use Claude.

[![CI](https://github.com/daanmeersseman/the-dutchman/actions/workflows/ci.yml/badge.svg)](https://github.com/daanmeersseman/the-dutchman/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-E8613C.svg)](LICENSE)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-1F1B1A.svg)

```
/plugin install dutchman --marketplace daanmeersseman/the-dutchman
```

## Why

Most of a Claude Code bill is not the work itself. It is the context sent again on every turn, a cache that expired
while you read, a helper agent on the most expensive model, a session that kept growing. Each of these is a setting or
a habit, and each one is easy to fix once you can see it.

The Dutchman shows which ones apply to *you*, priced on your own sessions.

## How it works

1. **At session start** The Dutchman reads the last 30 days of `~/.claude/projects` and your settings, in the background,
   at most once a day.
2. **A pane opens** with the tips that apply, each with what it costs or saves per month.
3. **Open a tip** to see what was found in your logs and what the amount assumes. **What will this do for me?** lists
   the exact settings and lines that change on your machine, before anything is written.
4. **Apply** makes the change without calling a model. Every file is backed up first. **Undo** puts it back, and
   refuses if you edited the file since.

An example pane:

```
$1,897 in 30 days  ·  ~$40/mo to save  ·  $253/mo at stake          Refresh
Amounts are at list price and count only logged calls; your bill can
differ by a few percent.

 Open 4    Applied & dismissed 0    Settings

FIXES
▸ Keep the cache warm for an hour instead of 5 minutes        ~$40/mo
▸ Turn off an MCP server you never use here: aspire
REMINDERS
▾ Get a nudge when a session passes 250k                $197/mo at stake
    Why    Every turn re-sends the whole conversation. 14 of your sessions
           grew past 250k tokens; their turns past that point cost $196.78.
    How    Once a session passes 250k tokens, a toast says so, once.
    [ Turn on ]  [ Dismiss ]                                      Guide §4
CHECKS
▸ 3 rules in this repo load on every turn                   $3/mo at stake
```

## The tips

A tip only shows when your own logs show the problem, and only after at least 7 days of logs.

| Tip | What it does | Amount |
|---|---|---|
| **1-hour cache** | Keeps the prompt cache warm for an hour instead of 5 minutes | exact: your sessions replayed |
| **Subagents on Sonnet** | Runs the built-in Explore, Plan and general-purpose agents on Sonnet | estimate |
| **Opus plans, Sonnet works** | Switches the main model to `opusplan` and starts sessions in plan mode | estimate |
| **Lower effort** | Sets Opus to medium effort when it runs at xhigh or max for everything | estimate |
| **Ignored effort setting** | Moves an effort setting to where Opus reads it | configuration |
| **Output style** | Fixes an output style that is not active because of its spelling | configuration |
| **Concise output** | Sets a concise output style when none is set | estimate |
| **Autocompact window** | Replaces a low autocompact percentage with a fixed window of 300k tokens | configuration |
| **Browser agent** | Adds a Sonnet subagent for Playwright, so screenshots and snapshots stay out of the main session | estimate |
| **CLAUDE.md imports** | Turns a big `@file` import in your user CLAUDE.md into a line Claude reads only when needed | measured |
| **Long sessions** | A reminder when a session passes 250k tokens, plus a `/handover` skill | measured |
| **Cache expiry** | A reminder before the cache of a big session runs out | measured |
| **Cold resume** | A reminder when you resume a big session whose cache has expired | measured |
| **Unused MCP servers** | Turns off MCP servers you never call in this project | count |
| **Unused user MCP servers** | Turns off MCP servers from your user config that you never call | count |
| **Unused plugins** | Disables plugins whose skills, commands and agents you never use | count |
| **Idle skills** | Makes skills Claude never picks load only when you type `/name` | count |
| **Always-on rules** | Points out project rules without a path scope | check |
| **Command output** | Suggests RTK when shell output fills your context | measured |

*Exact* replays your own calls with the change. *Estimate* rests on one assumption, shown with the tip. *Measured*
tells you what the problem cost, without promising what the fix saves.

## Settings

On first start the pane asks four things, with the recommended answer already picked:

- the minimum saving per month for a tip to show (**$5**);
- how open tips reach you: open the pane (**recommended**), a notice with the amount, or nothing until you type
  `/dutchman`;
- how often they may do so: every session, daily, **weekly** or monthly;
- from what context size a long session nudges you (**250k**).

The **Settings** tab holds these, plus how many days of logs to read (14, 30, 90), how often to read them again
(daily, weekly, only on Refresh), and from what monthly cost the cache reminder is offered.

| Command | |
|---|---|
| `/dutchman` | Open the pane |
| `/dutchman refresh` | Read the logs again, then open the pane |
| `/dutchman setup` | Open the first-start choices again |

## Privacy

The Dutchman runs on your machine. It reads local files only, sends nothing anywhere, and never calls a model.

Amounts are at Anthropic list price, so they hold for an API key. On a subscription, read them as how much of your
usage limit a habit takes. Backups of every file Apply changes live in `~/.claude/dutchman/backups/`.

## Requirements

- Claude Code 2.1.275 or later
- Python 3 on the `PATH` as `python` or `python3`

## The guide

Every tip links to a section of [the cost guide](docs/guide.md): how Claude Code is billed, what the cache does, which
model fits which work, and how to keep sessions small.

## Contributing

A new tip is one Python file. [CONTRIBUTING.md](CONTRIBUTING.md) has the layout, the tip format and how to test.
An idea without the code is welcome too: open a
[tip idea](https://github.com/daanmeersseman/the-dutchman/issues/new?template=tip-idea.md).

## Credits

Made by [@daanmeersseman](https://github.com/daanmeersseman). Works side by side with
[Frugalitas](https://github.com/siposzoltan03/frugalitas), which shows spend live when Claude Code runs through a
LiteLLM proxy. The Dutchman leaves the status line to Frugalitas, and its reminders defer to Frugalitas when both are
installed.

## License

[MIT](LICENSE)
