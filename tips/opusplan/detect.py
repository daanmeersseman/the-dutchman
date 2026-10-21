"""Sessions on Opus for planning and doing alike. Estimate from a measured net effect."""
from tiplib import MIN_USD, cost, dget, main_turns, price_of

NET = 0.11  # in a measured test opusplan cut session cost by 11%, net of the cost of each switch


def detect(calls, settings, **_):
    model = str(settings.get('model') or '')
    plan = dget(settings, 'permissions', 'defaultMode') is not None  # leave a chosen mode alone
    if 'opusplan' in model:  # the logs decide the rest: a default of sonnet says nothing if /model picks Opus
        return None
    main = [c for lst in main_turns(calls).values() for c in lst]
    total = sum(cost(c['t'], price_of(c['model'])) for c in main)
    opus = sum(cost(c['t'], price_of(c['model'])) for c in main if 'opus' in c['model'])
    if total == 0 or opus / total < 0.5:
        return None
    save = opus * NET
    if save < MIN_USD:
        return None
    return {
        'id': 'opusplan', 'kind': 'fix', 'confidence': 'estimate',
        'title': 'Let Opus plan and Sonnet do the work',
        'saving': save, 'measured': opus,
        'problem': f'Your sessions ran on Opus for planning and doing alike: ${opus:.2f} of ${total:.2f}, not counting subagents.',
        'how': 'With the model "opusplan", Opus writes the plan in plan mode (Shift+Tab); after you approve it, Sonnet '
               'carries it out at about half the price per token. Approving a plan switches models, which writes the '
               'context to the cache once more, so plan the whole task and approve once.',
        'assumption': f'About {NET:.0%} less, from a measured test. The work after the plan cost 35% less on Sonnet, '
                      'not half, because Sonnet used more tokens; each switch then cost a little. It depends on how much '
                      'of your work happens after a plan.',
        'change': 'Sets "model": "opusplan" in ~/.claude/settings.json' + (f' (now "{model}")' if model else '') + (
            '.' if plan else ', and starts new sessions in plan mode ("defaultMode": "plan"), so Opus plans first.') +
            ' /model switches back for one session.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'model': 'opusplan', **({} if plan else {'permissions': {'defaultMode': 'plan'}})}}],
        'restart': True,
    }
