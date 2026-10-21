"""Big sessions picked up again after an hour or more: the first turn wrote the whole context again."""
from tiplib import cost, handover, has_frugalitas, main_turns, price_of, ts

MIN_CONTEXT = 100_000
AWAY = 3600  # an hour or more away: a resumed session, not a break (cache-expiry covers the shorter gaps)


def detect(calls, settings, days, home='', cache_stake=5.0, **_):
    if has_frugalitas(settings) or not cache_stake:
        return None  # Frugalitas has /frugal restart for this; or the user turned cache reminders off
    paid, n = 0.0, 0
    for lst in main_turns(calls).values():
        for prev, c in zip(lst, lst[1:]):
            inp, out, read, w5, w1 = c['t']
            if (ts(c['ts']) - ts(prev['ts'])).total_seconds() >= AWAY and w5 + w1 >= MIN_CONTEXT:
                p = price_of(c['model'])
                paid += cost((0, 0, 0, w5, w1), p) - cost((0, 0, w5 + w1, 0, 0), p)
                n += 1
    if paid * 30 / days < cache_stake:
        return None
    return {
        'id': 'cold-resume', 'kind': 'reminder', 'confidence': 'measured',
        'title': 'Get a nudge when you resume a big session',
        'saving': None, 'measured': paid,
        'problem': f'{n} times you picked up a session of 100k tokens or more after an hour or longer. The cache was gone, '
                   f'so the first turn wrote the whole context again: ${paid:.2f} more than reading it from cache.',
        'how': 'When a session opens that already carries 100k tokens or more, a notice says so. If the new work does not '
               f'need all of it, start fresh: {handover(home)}.',
        'assumption': 'Some of those sessions needed their whole history; no amount is promised.',
        'reminder': {'id': 'cold-resume', 'on_resume': True, 'min_tokens': MIN_CONTEXT,
                     'text': 'This session carries {k}k tokens. If the cache has expired, the first turn writes all of it '
                             'again. A handover to a new session is cheaper when the next task does not need it all.'},
        'change': 'Turns on the reminder in this plugin. Nothing else changes.',
        'actions': [], 'restart': False,
    }
