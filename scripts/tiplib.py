"""Shared helpers for the tip detectors in tips/*/detect.py: log reading and list prices."""
import collections, datetime as dt, glob, json, os

# USD per 1M tokens: input, output, cache read, cache write 5m, cache write 1h. The first matching key wins.
PRICES = {
    'opus-5-5': (4, 20, .2, 5, 8), 'opus-latest': (4, 20, .2, 5, 8), 'opus-5': (5, 25, .5, 6.25, 10),
    'sonnet-5': (2, 10, .2, 2.5, 4), 'sonnet-latest': (2, 10, .2, 2.5, 4),
    'haiku-5-5': (.1, .5, .01, .125, .2), 'haiku-latest': (.1, .5, .01, .125, .2), 'haiku-4-5': (1, 5, .1, 1.25, 2),
}
SONNET = PRICES['sonnet-5']
MIN_DAYS = 7          # a tip needs at least this much history
MIN_USD = 1.0         # tips worth less than this over the window are not shown
CONTEXT_LIMIT = 250_000


def price_of(model):
    return next((p for k, p in PRICES.items() if k in (model or '')), None)


def cost(t, p):
    return sum(a * b for a, b in zip(t, p)) / 1e6


def ts(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_calls(home, since):
    """One record per API call (deduped on message.id), plus per-session facts the detectors need."""
    calls = {}
    sessions = collections.defaultdict(lambda: {'compactions': [], 'mcp_used': set(), 'skills_used': set(),
                                                'bash_calls': 0, 'bash_chars': 0})
    for path in glob.glob(os.path.join(home, 'projects', '**', '*.jsonl'), recursive=True):
        sub = os.sep + 'subagents' + os.sep in path or '/subagents/' in path
        agent = 'main'
        if sub:
            agent = (load_json(path[:-6] + '.meta.json') or {}).get('agentType', '?')
        try:
            f = open(path, encoding='utf-8', errors='replace')
        except OSError:
            continue
        with f:
            for line in f:
                if '"timestamp"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                stamp = e.get('timestamp', '')
                if stamp < since:
                    continue
                sid = e.get('sessionId')
                if e.get('type') == 'system' and e.get('subtype') == 'compact_boundary':
                    sessions[sid]['compactions'].append((stamp, (e.get('compactMetadata') or {}).get('trigger')))
                    continue
                m = e.get('message')
                if e.get('type') == 'user' and not sub and isinstance(m, dict) and isinstance(m.get('content'), list):
                    tur = e.get('toolUseResult')
                    if isinstance(tur, dict) and 'stdout' in tur:  # a Bash result; others have no stdout
                        sessions[sid]['bash_calls'] += 1
                        sessions[sid]['bash_chars'] += len(tur.get('stdout') or '') + len(tur.get('stderr') or '')
                    continue
                if e.get('type') != 'assistant' or not isinstance(m, dict):
                    continue
                for b in m.get('content') or []:
                    if isinstance(b, dict) and b.get('type') == 'tool_use':
                        name = b.get('name') or ''
                        if name.startswith('mcp__'):
                            sessions[sid]['mcp_used'].add(name.split('__')[1])
                        elif name == 'Skill':
                            sessions[sid]['skills_used'].add(str((b.get('input') or {}).get('skill', '')).split(':')[-1])
                u, mid = m.get('usage'), m.get('id')
                if not u or not mid:
                    continue
                cc = u.get('cache_creation') or {}
                w5, w1 = cc.get('ephemeral_5m_input_tokens') or 0, cc.get('ephemeral_1h_input_tokens') or 0
                if not (w5 or w1):  # older log lines have no 5m/1h split
                    w5 = u.get('cache_creation_input_tokens') or 0
                t = (u.get('input_tokens') or 0, u.get('output_tokens') or 0, u.get('cache_read_input_tokens') or 0, w5, w1)
                old = calls.get(mid)
                # streaming writes one message as several lines: keep the one with the most output
                if old is None or t[1] > old['t'][1]:
                    calls[mid] = {'t': t, 'model': m.get('model') or '', 'agent': agent, 'ts': stamp, 'sid': sid,
                                  'side': sub or bool(e.get('isSidechain')),
                                  'cwd': os.path.normcase(os.path.normpath(e['cwd'])) if e.get('cwd') else None}
    return [c for c in calls.values() if price_of(c['model'])], sessions


def main_turns(calls):
    by = collections.defaultdict(list)
    for c in calls:
        if not c['side'] and c['sid']:
            by[c['sid']].append(c)
    for lst in by.values():
        lst.sort(key=lambda c: c['ts'])
    return by


def project_mcp_state(cwd):
    """Which servers of the project's .mcp.json are on, from the settings that switch them."""
    servers = list(((load_json(os.path.join(cwd, '.mcp.json')) or {}).get('mcpServers') or {}).keys())
    enable_all, enabled, disabled = False, set(), set()
    for f in ('settings.json', 'settings.local.json'):
        s = load_json(os.path.join(cwd, '.claude', f)) or {}
        enable_all = s.get('enableAllProjectMcpServers', enable_all)
        enabled |= set(s.get('enabledMcpjsonServers') or [])
        disabled |= set(s.get('disabledMcpjsonServers') or [])
    return [n for n in servers if n not in disabled and (enable_all or n in enabled)]


def has_hook(settings, needle):
    """Whether any configured hook command mentions needle."""
    return needle in json.dumps(settings.get('hooks') or {})


def has_frugalitas(settings):
    return any(k.startswith('frugalitas@') and v for k, v in (settings.get('enabledPlugins') or {}).items())


def over_context(calls, limit=CONTEXT_LIMIT):
    """Main-session turns above limit: their cost, the sessions they are in, how many."""
    over, sess, turns = 0.0, set(), 0
    for sid, lst in main_turns(calls).items():
        for c in lst:
            inp, _, read, w5, w1 = c['t']
            if inp + read + w5 + w1 > limit:
                over += cost(c['t'], price_of(c['model']))
                sess.add(sid)
                turns += 1
    return over, len(sess), turns
