"""Back-test the 1-hour cache on main-session turns. Exact under the log's own timing."""
from tiplib import MIN_USD, cost, main_turns, price_of, ts


def detect(calls, settings, **_):
    if settings.get('promptCacheTtl') == '1h':
        return None
    now = then = 0.0
    rewrites = 0
    for lst in main_turns(calls).values():
        prev = None
        for c in lst:
            p = price_of(c['model'])
            inp, out, read, w5, w1 = c['t']
            now += cost(c['t'], p)
            ctx = inp + read + w5 + w1
            gap = (ts(c['ts']) - ts(prev['ts'])).total_seconds() if prev else None
            same_model = prev is not None and prev['model'] == c['model']
            if same_model and gap is not None and 300 < gap <= 3600 and (w5 + w1) >= 0.5 * ctx and ctx >= 20_000:
                # under 1h this rewrite would have been a cache read of the cached prefix
                cached = prev['t'][0] + prev['t'][2] + prev['t'][3] + prev['t'][4]
                hit = min(cached, w5 + w1)
                then += cost((inp, out, read + hit, 0, w5 + w1 - hit), p)
                rewrites += 1
            else:
                then += cost((inp, out, read, 0, w5 + w1), p)  # every write at the 1h price
            prev = c
    save = now - then
    if save < MIN_USD:
        return None
    return {
        'id': 'cache-ttl-1h', 'kind': 'fix', 'category': 'Cache', 'confidence': 'exact',
        'title': 'Keep the cache warm for an hour instead of 5 minutes',
        'saving': save, 'measured': now,
        'problem': f'Claude caches your conversation so the next turn reads it cheaply. The cache lasts 5 minutes. '
                   f'{rewrites} times you (or Claude, waiting on a build or your approval) paused 5 to 60 minutes, and '
                   f'the whole conversation was written to the cache again at full price.',
        'how': 'With a 1-hour cache those pauses stay cheap. Each cache write costs more (2x instead of 1.25x the input '
               f'price). Replaying your own last sessions with a 1-hour cache: ${then:.2f} instead of ${now:.2f}.',
        'assumption': None,
        'change': 'Adds "promptCacheTtl": "1h" to ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json', 'value': {'promptCacheTtl': '1h'}}],
        'min_version': '2.1.242', 'restart': True, 'guide': '5.1',
    }
