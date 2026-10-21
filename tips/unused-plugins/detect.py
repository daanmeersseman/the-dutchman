"""Enabled plugins of which no skill, command, agent or MCP tool was used in the window."""
import os

from tiplib import dget, load_json, plural, used_names


def parts(path):
    """What a plugin adds that leaves a trace in the logs: its skills, commands and agents."""
    names = set()
    for kind in ('skills', 'commands', 'agents'):
        d = os.path.join(path, kind)
        if os.path.isdir(d):
            names |= {os.path.splitext(n)[0] for n in os.listdir(d)}
    return names


def detect(sessions, settings, home, days, **_):
    installed = dget(load_json(os.path.join(home, 'plugins', 'installed_plugins.json')), 'plugins') or {}
    used = used_names(sessions)
    idle = []
    for key, on in (dget(settings, 'enabledPlugins') or {}).items():
        name = key.split('@')[0]
        if not on or name == 'dutchman':
            continue
        paths = [i.get('installPath') for i in installed.get(key) or [] if i.get('installPath')]
        if not paths or os.path.isdir(os.path.join(paths[-1], 'hooks')):
            continue  # a plugin with hooks works without being called, so no use is not no value
        mine = parts(paths[-1])
        if not mine:
            continue
        if any(u == name or u.startswith(name + ':') or u.startswith('plugin_' + name) or u in mine for u in used):
            continue
        idle.append((key, sorted(mine)))
    if not idle:
        return None
    keys = [k for k, _ in idle]
    names = ', '.join(k.split('@')[0] for k in keys)
    return {
        'id': 'unused-plugins:' + ','.join(keys), 'kind': 'fix', 'confidence': 'measured',
        'title': f'Turn off {plural(len(keys), "the plugin", "plugins")} you never use: {names}',
        'saving': None, 'measured': None,
        'problem': f'A plugin adds the descriptions of its skills, commands and agents to every turn. In the last {days} '
                   f'days you used none of {names}: ' +
                   '; '.join(f'{k.split("@")[0]} has {", ".join(m[:4])}{"…" if len(m) > 4 else ""}' for k, m in idle) + '.',
        'how': 'A disabled plugin stays installed. Switch it back on with /plugin when you need it.',
        'assumption': None,
        'change': 'Sets ' + ', '.join(f'"{k}"' for k in keys) + ' to false under enabledPlugins in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'enabledPlugins': {k: False for k in keys}}}],
        'restart': True,
    }
