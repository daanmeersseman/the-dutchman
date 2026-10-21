"""Opus at xhigh or max effort for everyday work. Estimate from a measured output ratio."""
from tiplib import MIN_USD, cost, dget, main_turns, price_of

RATIO = 2.6  # in a measured test xhigh wrote 2.6x the output of medium


def detect(calls, settings, **_):
    lvl = dget(settings, 'modelSettings', 'claude-opus-5-5', 'effortLevel')
    if lvl not in ('xhigh', 'max'):
        return None
    out = sum(cost((0, c['t'][1], 0, 0, 0), price_of(c['model']))
              for lst in main_turns(calls).values() for c in lst if 'opus-5-5' in c['model'])
    save = out * (1 - 1 / RATIO)
    if save < MIN_USD:
        return None
    return {
        'id': 'effort-too-high', 'kind': 'fix', 'confidence': 'estimate',
        'title': 'Lower Opus effort to medium',
        'saving': save, 'measured': out,
        'problem': f'~/.claude/settings.json sets Opus 5.5 to "{lvl}" effort for every session. Thinking is billed as '
                   f'output: your Opus sessions wrote ${out:.2f} of output, not counting subagents.',
        'how': 'Medium is the default for daily work. For one hard problem, type /effort xhigh in that session only; '
               'the next session starts at medium again.',
        'assumption': f'Medium writes about {1 / RATIO:.0%} of the output of xhigh, in a measured test. Max writes more '
                      'than xhigh, so from max the saving is higher.',
        'change': 'Sets "effortLevel": "medium" for claude-opus-5-5 under modelSettings in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'modelSettings': {'claude-opus-5-5': {'effortLevel': 'medium'}}}}],
        'min_version': '2.1.251', 'restart': True,
    }
