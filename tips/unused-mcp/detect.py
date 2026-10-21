"""Enabled project MCP servers with no tool call in this project's sessions. No amount: tool sizes are not in the logs."""
import os

from tiplib import mcp_used, plural, project_mcp_state


def detect(sessions, cwd, home, days, **_):
    used = mcp_used(sessions, cwd)
    unused = sorted(n for n in project_mcp_state(cwd, home) if n not in used)
    if not unused:
        return None
    names = ', '.join(unused)
    n = len(unused)
    local = os.path.normpath(os.path.join(cwd, '.claude', 'settings.local.json'))
    return {
        'id': 'unused-mcp:' + ','.join(unused), 'kind': 'fix', 'confidence': 'measured',
        'title': f'Turn off {plural(n, "the MCP server", "MCP servers")} you never use here: {names}',
        'saving': None, 'measured': None,
        'problem': f'An MCP server adds all its tool descriptions to every turn, used or not. {names} '
                   f'{plural(n, "is", "are")} switched on in this project, but none of your sessions here in the last '
                   f'{days} days called {plural(n, "it", "them")}.',
        'how': f'Switching {plural(n, "it", "them")} off for this project removes the tools from your context. /mcp '
               'switches a server back on for the session that needs it. Run /context in a fresh session to see how '
               f'many tokens {plural(n, "it takes", "they take")} now.',
        'assumption': None,
        'change': f'Adds {names} to disabledMcpjsonServers in {local}, your own untracked file, and takes '
                  f'{plural(n, "it", "them")} out of enabledMcpjsonServers there. The shared .mcp.json is not touched.',
        'actions': [
            {'op': 'json-list', 'file': local, 'key': 'enabledMcpjsonServers', 'remove': unused},
            {'op': 'json-list', 'file': local, 'key': 'disabledMcpjsonServers', 'add': unused},
        ],
        'restart': True,
    }
