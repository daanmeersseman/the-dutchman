"""Opus at xhigh or max effort for everyday work. Estimate from the guide's measured output ratio."""
from tiplib import MIN_USD, cost, main_turns, price_of

RATIO = 2.6  # xhigh wrote 2.6x the output of medium as measured in guide 6.4


def detect(calls, settings, **_):
    lvl = ((settings.get('modelSettings') or {}).get('claude-opus-5-5') or {}).get('effortLevel')
    if lvl not in ('xhigh', 'max'):
        return None
    out = sum(cost((0, c['t'][1], 0, 0, 0), price_of(c['model']))
              for lst in main_turns(calls).values() for c in lst if 'opus-5-5' in c['model'])
    save = out * (1 - 1 / RATIO)
    if save < MIN_USD:
        return None
    return {
        'id': 'effort-too-high', 'kind': 'fix', 'category': 'Models', 'confidence': 'estimate',
        'title': f'Opus runs at "{lvl}" effort for every task',
        'saving': save, 'measured': out,
        'problem': f'~/.claude/settings.json sets Opus 5.5 to "{lvl}" effort for every session. Thinking is billed as '
                   f'output: your Opus main sessions wrote ${out:.2f} of output.',
        'how': 'Medium is the default for daily work. For one hard problem, type /effort xhigh in that session only; '
               'the next session starts at medium again.',
        'assumption': f'Medium writes 1/{RATIO} of the output of xhigh, as measured for the guide. Max writes more '
                      'than xhigh, so for max this is a lower bound.',
        'change': 'Sets "effortLevel": "medium" for claude-opus-5-5 under modelSettings in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'modelSettings': {'claude-opus-5-5': {'effortLevel': 'medium'}}}}],
        'min_version': '2.1.251', 'restart': True, 'guide': '6.4',
    }
