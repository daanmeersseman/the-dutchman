"""Built-in subagents (no own model) that ran on Opus. Same tokens priced at Sonnet."""
from tiplib import MIN_USD, SONNET, cost, price_of

MODEL = 'claude-sonnet-5-5'


def detect(calls, settings, **_):
    if (settings.get('env') or {}).get('CLAUDE_CODE_SUBAGENT_MODEL'):
        return None
    sel = [c for c in calls if c['side'] and c['agent'] in ('general-purpose', 'Explore', 'Plan', '?') and 'opus' in c['model']]
    now = sum(cost(c['t'], price_of(c['model'])) for c in sel)
    save = now - sum(cost(c['t'], SONNET) for c in sel)
    if save < MIN_USD:
        return None
    return {
        'id': 'subagent-model', 'kind': 'fix', 'category': 'Models', 'confidence': 'estimate',
        'title': 'Run built-in subagents on Sonnet',
        'saving': save, 'measured': now,
        'problem': f'Claude starts helper agents (Explore, general-purpose, Plan) for searching and research. Yours ran on '
                   f'Opus, your main model: {len(sel)} calls, ${now:.2f}.',
        'how': 'One setting gives these built-in helpers their own model. Sonnet costs half of Opus per token and does '
               'search and research work well. Agents you defined yourself with a model: line keep their model.',
        'assumption': 'Sonnet needs about the same number of tokens for these tasks.',
        'change': f'Adds "CLAUDE_CODE_SUBAGENT_MODEL": "{MODEL}" under env in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'env': {'CLAUDE_CODE_SUBAGENT_MODEL': MODEL}}}],
        'restart': True, 'guide': '6.3',
    }
