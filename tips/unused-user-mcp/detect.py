"""MCP servers in your own ~/.claude.json, on in every project, never called in any session of the window."""
import os

from tiplib import load_json


def detect(sessions, home, days, **_):
    cfg = os.path.join(os.path.dirname(os.path.normpath(home)), ".claude.json")  # ~/.claude.json sits next to ~/.claude
    servers = list(((load_json(cfg) or {}).get('mcpServers') or {}).keys())
    used = set().union(*(s['mcp_used'] for s in sessions.values())) if sessions else set()
    unused = sorted(n for n in servers if n not in used)
    if not unused:
        return None
    names = ', '.join(unused)

    return {
        'id': 'unused-user-mcp:' + ','.join(unused), 'kind': 'fix', 'category': 'Fixed cost', 'confidence': 'measured',
        'title': f'Turn off MCP server{"s" if len(unused) > 1 else ""} you never call: {names}',
        'saving': None, 'measured': None,
        'problem': f'{names} {"is" if len(unused) == 1 else "are"} set up for you in every project, so {"its" if len(unused) == 1 else "their"} '
                   f'tool descriptions load on every turn. None of your sessions in the last {days} days called it.',
        'how': 'Denying a server for yourself keeps its setup, so /mcp or removing the line brings it back. Run /context in a '
               'fresh session to see how many tokens it takes now.',
        'assumption': None,
        'change': f'Adds {names} to deniedMcpServers in ~/.claude/settings.json. Your ~/.claude.json is not touched.',
        'actions': [{'op': 'json-list', 'file': '~/.claude/settings.json', 'key': 'deniedMcpServers',
                     'add': [{'serverName': n} for n in unused]}],
        'restart': True, 'guide': '3.1',
    }
