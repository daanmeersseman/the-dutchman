"""Enabled project MCP servers with no tool call in this project's sessions. No amount: tool sizes are not in the logs."""
import os

from tiplib import project_mcp_state


def detect(sessions, cwd, days, **_):
    used = set().union(*(s['mcp_used'] for s in sessions.values())) if sessions else set()
    unused = sorted(n for n in project_mcp_state(cwd) if n not in used)
    if not unused:
        return None
    names = ', '.join(unused)
    local = os.path.normpath(os.path.join(cwd, '.claude', 'settings.local.json'))
    return {
        'id': 'unused-mcp:' + ','.join(unused), 'kind': 'fix', 'category': 'Fixed cost', 'confidence': 'measured',
        'title': f'Turn off MCP server{"s" if len(unused) > 1 else ""} you never use here: {names}',
        'saving': None, 'measured': None,
        'problem': f'An MCP server adds all its tool descriptions to every turn, used or not. {names} is switched on in '
                   f'this project, but none of your sessions in the last {days} days called it.',
        'how': 'Switching it off for this project removes its tools from your context. You can switch it back on any '
               'time with /mcp, for the session that needs it. Run /context in a fresh session to see how many tokens '
               'it takes now.',
        'assumption': None,
        'change': f'Moves {names} from enabledMcpjsonServers to disabledMcpjsonServers in {local} '
                  '(your own, untracked file). The shared .mcp.json is not touched.',
        'actions': [
            {'op': 'json-list', 'file': local, 'key': 'enabledMcpjsonServers', 'remove': unused},
            {'op': 'json-list', 'file': local, 'key': 'disabledMcpjsonServers', 'add': unused},
        ],
        'restart': True, 'guide': '3.1',
    }
