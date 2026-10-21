"""Shared helpers for the tip detectors in tips/*/detect.py: log reading and list prices."""
import collections, datetime as dt, glob, json, os, re

COMMAND = re.compile(r'<command-name>/([^<\s]+)</command-name>')
PW_HEAVY = ('browser_take_screenshot', 'browser_snapshot', 'browser_network_requests')  # tools with large results

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
ITEM = re.compile(r'^(?!\.\.?$)[\w.-]+$')  # a name that can be a path part: no separators, not . or ..


def price_of(model):
    return next((p for k, p in PRICES.items() if k in (model or '')), None)


def cost(t, p):
    return sum(a * b for a, b in zip(t, p)) / 1e6


def norm(path):
    """A path in one form, to compare a log's cwd with a folder."""
    return os.path.normcase(os.path.normpath(path))


def dget(d, *keys):
    """d[k1][k2]..., or None when a level is missing or not an object: settings files are edited by hand."""
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def ts(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def load_json(path):
    try:
        with open(path, encoding='utf-8-sig') as f:  # -sig: a file saved with a BOM still reads
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_calls(home, since):
    """One record per API call (deduped on message.id), plus per-session facts the detectors need."""
    calls = {}
    sessions = collections.defaultdict(lambda: {'compactions': [], 'mcp_used': set(), 'skills_used': set(),
                                                'bash_calls': 0, 'bash_chars': 0, 'names': set(), 'pw_main': [],
                                                'cwd': None})
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
                if not isinstance(e, dict):
                    continue
                stamp = e.get('timestamp', '')
                if stamp < since:
                    continue
                sid = e.get('sessionId')
                if e.get('cwd') and not sessions[sid]['cwd']:
                    sessions[sid]['cwd'] = norm(e['cwd'])
                if sub:
                    sessions[sid]['names'].add(agent)  # what a plugin's agent was used under
                if '<command-name>' in line:
                    sessions[sid]['names'].update(COMMAND.findall(line))
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
                            if name.split('__')[-1] in PW_HEAVY and not sub and not e.get('isSidechain'):
                                sessions[sid]['pw_main'].append(stamp)
                        elif name == 'Skill':
                            skill = str((b.get('input') or {}).get('skill', ''))
                            sessions[sid]['skills_used'].add(skill.split(':')[-1])
                            sessions[sid]['names'].add(skill)
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
                                  'cwd': norm(e['cwd']) if e.get('cwd') else None}
    return [c for c in calls.values() if price_of(c['model'])], sessions


def main_turns(calls):
    by = collections.defaultdict(list)
    for c in calls:
        if not c['side'] and c['sid']:
            by[c['sid']].append(c)
    for lst in by.values():
        lst.sort(key=lambda c: c['ts'])
    return by


def project_mcp_state(cwd, home):
    """Which servers of the project's .mcp.json are on, from the settings that switch them and the approvals
    Claude Code keeps per project in ~/.claude.json."""
    servers = list(dget(load_json(os.path.join(cwd, '.mcp.json')), 'mcpServers') or {})
    projects = dget(load_json(os.path.join(os.path.dirname(os.path.normpath(home)), '.claude.json')), 'projects') or {}
    approved = next((p for k, p in projects.items() if norm(k) == norm(cwd)), None)
    enable_all, enabled, disabled = False, set(), set()
    for s in (approved, load_json(os.path.join(cwd, '.claude', 'settings.json')),
              load_json(os.path.join(cwd, '.claude', 'settings.local.json'))):
        if not isinstance(s, dict):
            continue
        enable_all = s.get('enableAllProjectMcpServers', enable_all)
        enabled |= {n for n in s.get('enabledMcpjsonServers') or [] if isinstance(n, str)}
        disabled |= {n for n in s.get('disabledMcpjsonServers') or [] if isinstance(n, str)}
    return [n for n in servers if n not in disabled and (enable_all or n in enabled)]


def mcp_used(sessions, cwd=None):
    """MCP servers called in any session, or only in the sessions of the folder cwd."""
    return set().union(set(), *(s['mcp_used'] for s in sessions.values() if cwd is None or s.get('cwd') == norm(cwd)))


def has_hook(settings, needle):
    """Whether any configured hook command mentions needle."""
    return needle in json.dumps(dget(settings, 'hooks') or {})


def used_names(sessions):
    """Skills, commands, agent types and MCP servers used in any session, as their names appear in the logs."""
    return set().union(set(), *(s['names'] | s['mcp_used'] for s in sessions.values()))


def read_price(c):
    """What one token costs to carry into this call: the cache read price of its model."""
    return price_of(c['model'])[2] / 1e6


def has_frugalitas(settings):
    plugins = dget(settings, 'enabledPlugins')
    return isinstance(plugins, dict) and any(k.startswith('frugalitas@') and v for k, v in plugins.items())


def handover(home):
    """How to carry the work into a fresh session: with the /handover skill when it is installed."""
    if os.path.exists(os.path.join(home, 'skills', 'handover', 'SKILL.md')):
        return '/handover, then /clear, then /handover resume'
    return 'ask Claude for a short handover note, then /clear and paste it in'


def plural(n, one, many):
    return one if n == 1 else many


def over_context(calls, limit=CONTEXT_LIMIT):
    """Main-session turns above limit: what the part above limit cost, the sessions they are in, how many."""
    over, sess, turns = 0.0, set(), 0
    for sid, lst in main_turns(calls).items():
        for c in lst:
            inp, _, read, w5, w1 = c['t']
            ctx = inp + read + w5 + w1
            if ctx > limit:
                over += cost(c['t'], price_of(c['model'])) * (ctx - limit) / ctx
                sess.add(sid)
                turns += 1
    return over, len(sess), turns
