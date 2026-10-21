# Contributing to The Dutchman

Thanks for helping people spend less on Claude Code. The most useful contribution is a new tip: one Python file that
spots a costly setting or habit in the logs and prices it.

## Layout

| Path | What it is |
|---|---|
| `tips/<id>/detect.py` | One tip. `detect(**ctx)` returns a tip or `None`. |
| `scripts/analyze.py` | Runs every detector and prints the tips as JSON. The tip fields are documented at the top. |
| `scripts/tiplib.py` | Shared helpers: log reading, prices, `cost()`, `main_turns()`, `over_context()`. |
| `scripts/actions.py` | Applies and undoes a tip's `actions`, with a backup of every file it touches. |
| `hooks/register.tsx` | The pane, the notice, the `/dutchman` command and the reminders. |
| `hooks/logic.ts` | The pane's pure helpers, tested in `tests/logic.test.ts`. |
| `types/index.d.ts` | Types shared with the pane. |
| `docs/guide.md` | The cost guide: how Claude Code is billed, as background for the tips. |

## Adding a tip

1. Create `tips/<id>/detect.py`. Copy the closest existing tip:
   - a setting to change: `tips/subagent-model/detect.py`;
   - a reminder at the right moment: `tips/long-sessions/detect.py`;
   - a check that changes nothing itself: `tips/always-on-rules/detect.py`.
2. Take only the context you need and end with `**_`:
   ```python
   def detect(calls, settings, **_):
   ```
   The context holds `calls`, `sessions`, `settings`, `home`, `cwd`, `days`, `context_limit` and `cache_stake`.
   `days` is how many days the logs cover; `analyze.py` scales every amount to 30 of them. Settings files are edited
   by hand, so read nested keys with `dget(settings, 'env', 'X')` from `tiplib`.
   Each call is `{'t': (input, output, cache_read, write_5m, write_1h), 'model', 'agent', 'ts', 'sid', 'side', 'cwd'}`.
3. Return `None` unless the user's own logs show the problem. Below `MIN_USD` (from `tiplib`) a priced tip stays quiet.
4. Fill in the tip. Write `problem` about *their* numbers, `how` in plain words, and `change` file by file. A fix's
   `title` starts with a verb ("Lower Opus effort to medium"); a reminder's starts with "Get a nudge"; a check's states
   what was found. A check sets `next`: what the user can do about it.
5. Express the change as data in `actions`. The operations are listed at the top of `scripts/actions.py`:
   `json-merge` (a null value removes a key), `json-list`, `line-replace`, `copy-file`, `frontmatter-set`. Apply backs
   up every file first, and Undo restores it. `actions.py apply <id> --plan` prints what Apply would change.
   A new kind of change needs a new operation there, with a test in `scripts/test_actions.py`.
6. Add a test with **hand-computed** amounts to `scripts/test_analyze.py`. Build the logs in `setUp`, and assert the
   exact saving.

### Choosing `confidence`

| Value | Use it when |
|---|---|
| `exact` | The saving replays the user's own calls with the change applied. |
| `estimate` | The saving rests on one stated assumption; put it in `assumption`. |
| `measured` | You know what the problem cost, but not what the fix saves. Set `saving: None` and `measured`. |
| `config` | A setting is wrong or ignored; there is no amount. |

## Ground rules

- Nothing leaves the machine and no model is called. Detectors read local files only.
- Apply never changes a file without a backup, and never touches files shared with a team (project rules, `CLAUDE.md`).
  For those, make the tip a `check`.
- Prices come from `tiplib.price_of()`. Update them there, in one place.
- Write user-facing text in short, plain sentences, without dashes as punctuation, in US English.
- Use one word for one thing: "notice" for what pops up, "subagent" for a helper agent, "session" for a conversation.

## Run it locally

```bash
python -I scripts/test_analyze.py
```

```bash
python -I scripts/test_actions.py
```

```bash
claude plugin test .
```

```bash
python -I scripts/analyze.py --cwd <some project>
```

```bash
claude plugin validate .
```

To try the pane, add this folder as a local marketplace and install from it:

```
/plugin marketplace add <path to your clone>
/plugin install dutchman@the-dutchman
```

After an edit, `/reload-plugins` picks it up. Set `DRY = true` at the top of `hooks/register.tsx` to see the tips at
every session start, and to get a diff from Apply without writing anything. Set it back before you open a pull request.

## Pull requests

Keep one tip or one fix per pull request. CI runs both Python test suites and compiles the pane; run
`claude plugin test .` yourself, because CI has no Claude Code to run it with.
