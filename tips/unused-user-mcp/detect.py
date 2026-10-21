"""MCP servers in your own ~/.claude.json, on in every project, never called in any session of the window."""
import os

from tiplib import dget, load_json, mcp_used, plural


def detect(sessions, settings, home, days, **_):
    cfg = os.path.join(os.path.dirname(os.path.normpath(home)), '.claude.json')  # ~/.claude.json sits next to ~/.claude
    servers = list(dget(load_json(cfg), 'mcpServers') or {})
    denied = {d.get('serverName') for d in dget(settings, 'deniedMcpServers') or [] if isinstance(d, dict)}
    used = mcp_used(sessions)
    unused = sorted(n for n in servers if n not in used and n not in denied)
    if not unused:
        return None
    names = ', '.join(unused)
    n = len(unused)
    return {
        'id': 'unused-user-mcp:' + ','.join(unused), 'kind': 'fix', 'confidence': 'measured',
        'title': f'Turn off {plural(n, "the MCP server", "MCP servers")} you never call: {names}',
        'saving': None, 'measured': None,
        'problem': f'{names} {plural(n, "is", "are")} set up for you in every project, so {plural(n, "its", "their")} '
                   f'tool descriptions load on every turn. None of your sessions in the last {days} days called '
                   f'{plural(n, "it", "them")}.',
        'how': 'Denying a server for yourself keeps its setup, so removing it from deniedMcpServers brings it back. Run '
               '/context in a fresh session to see how many tokens '
               f'{plural(n, "it takes", "they take")} now.',
        'assumption': None,
        'change': f'Adds {names} to deniedMcpServers in ~/.claude/settings.json. Your ~/.claude.json is not touched.',
        'actions': [{'op': 'json-list', 'file': '~/.claude/settings.json', 'key': 'deniedMcpServers',
                     'add': [{'serverName': n} for n in unused]}],
        'restart': True,
    }
