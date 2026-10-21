"""Turns that came after the cache expired and rewrote a large context. A reminder before it happens."""
from tiplib import cost, handover, has_frugalitas, main_turns, price_of, ts

MIN_CONTEXT = 100_000


def detect(calls, settings, home='', days=30, cache_stake=5.0, **_):
    if has_frugalitas(settings) or not cache_stake:
        return None  # Frugalitas shows a cache countdown with the rewrite's price; or the user turned it off
    ttl = 3600 if settings.get('promptCacheTtl') == '1h' else 300
    paid, n = 0.0, 0
    for lst in main_turns(calls).values():
        for prev, c in zip(lst, lst[1:]):
            inp, out, read, w5, w1 = c['t']
            gap = (ts(c['ts']) - ts(prev['ts'])).total_seconds()
            if ttl < gap < 3600 and w5 + w1 >= MIN_CONTEXT:  # an hour or more is a resume: cold-resume
                p = price_of(c['model'])
                paid += cost((0, 0, 0, w5, w1), p) - cost((0, 0, w5 + w1, 0, 0), p)  # rewrite instead of a read
                n += 1
    if paid * 30 / days < cache_stake:
        return None
    mins = ttl // 60
    do = handover(home)
    return {
        'id': 'cache-expiry', 'kind': 'reminder', 'confidence': 'measured',
        'title': 'Get a nudge before the cache of a big session expires',
        'saving': None, 'measured': paid,
        'problem': f'{n} times you came back to a session of 100k tokens or more after the cache had expired '
                   f'({mins} minutes idle). The first turn then wrote the whole context again: ${paid:.2f} more than '
                   'reading it from cache.',
        'how': 'When a session over 100k tokens has been idle until a minute before its cache expires, a notice says '
               f'so. Answer now, or before a break: {do}.',
        'assumption': 'Some of those turns were new work that needed the context; no amount is promised.',
        'reminder': {'id': 'cache-expiry', 'before_expiry_ms': 60_000, 'min_tokens': MIN_CONTEXT,
                     'text': 'The cache of this {k}k session expires in a minute. The next turn after that writes '
                             f'all of it again. Answer now, or before a break: {do}.'},
        'change': 'Turns on the reminder in this plugin. Nothing else changes.',
        'actions': [], 'restart': False,
    }
