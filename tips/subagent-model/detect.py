"""Built-in subagents (no own model) that ran on Opus. Same tokens priced at Sonnet."""
import datetime as dt

from tiplib import MIN_USD, SONNET, cost, dget, price_of, ts

MODEL = 'claude-sonnet-5-5'


def detect(calls, settings, days=30, **_):
    set_to = dget(settings, 'env', 'CLAUDE_CODE_SUBAGENT_MODEL')
    if set_to and 'opus' in str(set_to).lower():
        return None  # Opus on purpose
    sel = [c for c in calls if c['side'] and c['agent'] in ('general-purpose', 'Explore', 'Plan') and 'opus' in c['model']]
    if set_to:
        # set, yet they still ran on Opus: only the last week counts, older calls may predate the setting
        week = max((c['ts'] for c in calls), default='')
        week = (ts(week) - dt.timedelta(days=7)).isoformat()[:19] if week else ''
        sel = [c for c in sel if c['ts'] >= week]
    paid = sum(cost(c['t'], price_of(c['model'])) for c in sel)
    save = paid - sum(cost(c['t'], SONNET) for c in sel)
    if save < MIN_USD:
        return None
    if set_to:
        return {
            'id': 'subagent-model', 'kind': 'check', 'confidence': 'measured',
            'title': 'Your subagent model setting is not applied',
            'saving': None, 'measured': paid * days / 7,  # a week of logs, scaled to the window
            'problem': f'~/.claude/settings.json sets CLAUDE_CODE_SUBAGENT_MODEL to {set_to}, yet in the last 7 days '
                       f'{len(sel)} calls of built-in subagents (Explore, general-purpose, Plan) ran on Opus: ${paid:.2f}.',
            'how': 'Some ways of starting Claude Code (the desktop app, a launcher, a managed setup) pass their own '
                   'environment, so env values from settings.json do not reach every session.',
            'assumption': None,
            'change': None, 'actions': [], 'restart': False,
            'next': 'Check where the sessions that ran on Opus were started, and set CLAUDE_CODE_SUBAGENT_MODEL in '
                    'that environment, or pass model: "sonnet" when you start an agent.',
        }
    return {
        'id': 'subagent-model', 'kind': 'fix', 'confidence': 'estimate',
        'title': 'Run built-in subagents on Sonnet',
        'saving': save, 'measured': paid,
        'problem': f'Claude starts subagents (Explore, general-purpose, Plan) for searching and research. Yours ran on '
                   f'Opus, your main model: {len(sel)} calls, ${paid:.2f}.',
        'how': 'One setting gives these built-in subagents their own model. Sonnet costs half of Opus per token and does '
               'search and research work well. Agents you defined yourself with a model: line keep their model.',
        'assumption': 'Sonnet needs about the same number of tokens for these tasks.',
        'change': f'Adds "CLAUDE_CODE_SUBAGENT_MODEL": "{MODEL}" under env in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'env': {'CLAUDE_CODE_SUBAGENT_MODEL': MODEL}}}],
        'restart': True,
    }
