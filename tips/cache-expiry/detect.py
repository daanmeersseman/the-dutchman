"""Turns that came after the cache expired and rewrote a large context. A reminder before it happens."""
from tiplib import cost, has_frugalitas, main_turns, price_of, ts

MIN_CONTEXT = 100_000


def detect(calls, settings, days=30, cache_stake=5.0, **_):
    if has_frugalitas(settings) or not cache_stake:
        return None  # Frugalitas shows a cache countdown with the rewrite's price; or the user turned it off
    ttl = 3600 if settings.get('promptCacheTtl') == '1h' else 300
    paid, n = 0.0, 0
    for lst in main_turns(calls).values():
        for prev, c in zip(lst, lst[1:]):
            inp, out, read, w5, w1 = c['t']
            if (ts(c['ts']) - ts(prev['ts'])).total_seconds() > ttl and w5 + w1 >= MIN_CONTEXT:
                p = price_of(c['model'])
                paid += cost((0, 0, 0, w5, w1), p) - cost((0, 0, w5 + w1, 0, 0), p)  # rewrite instead of a read
                n += 1
    if paid * 30 / days < cache_stake:
        return None
    mins = ttl // 60
    return {
        'id': 'cache-expiry', 'kind': 'reminder', 'category': 'Cache', 'confidence': 'measured',
        'title': f'Get a nudge before the cache of a big session expires',
        'saving': None, 'measured': paid,
        'problem': f'{n} times you came back to a session of 100k tokens or more after the cache had expired '
                   f'({mins} minutes idle). The first turn then wrote the whole context again: ${paid:.2f} more than '
                   'reading it from cache.',
        'how': f'When a session over 100k tokens has been idle for {mins - 1 if mins > 5 else 4} minutes, a toast says '
               'the cache is about to expire. Answer now, or write a handover and /clear before you walk away.',
        'assumption': 'Some of those turns were new work that needed the context; no amount is promised.',
        'reminder': {'id': 'cache-expiry', 'idle_ms': (ttl - 60) * 1000, 'min_tokens': MIN_CONTEXT,
                     'text': 'The cache of this {k}k session expires in a minute. The next turn after that writes '
                             'all of it again. Answer now, or /handover and /clear before a break.'},
        'change': 'Turns on the reminder in this plugin. Nothing else changes.',
        'actions': [], 'restart': False, 'guide': '5',
    }
