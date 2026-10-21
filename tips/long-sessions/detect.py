"""What turns above the chosen context size cost. A reminder at the moment it happens, not a promised saving."""
import os

from tiplib import MIN_USD, has_frugalitas, over_context

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'handover-skill.md')


def detect(calls, sessions, home, settings, context_limit, **_):
    if not context_limit:
        return None  # the user turned this reminder off
    k = f'{context_limit // 1000}k'
    frugal = has_frugalitas(settings)
    over, n_sess, turns = over_context(calls, context_limit)
    if over < 5 * MIN_USD:
        return None
    autos = sum(1 for s in sessions.values() for _, trig in s['compactions'] if trig == 'auto')
    has_skill = os.path.exists(os.path.join(home, 'skills', 'handover', 'SKILL.md'))
    if frugal:
        do = '/frugal restart (Haiku writes a handover, then the session clears and continues small)'
    else:
        do = '/handover, then /clear, then /handover resume'
    tip = {
        'id': 'long-sessions', 'kind': 'reminder', 'confidence': 'measured',
        'title': f'Get a nudge when a session passes {k} tokens',
        'saving': None, 'measured': over,
        'problem': f'Every turn sends the whole conversation again. {n_sess} of your sessions grew past {k} tokens. On '
                   f'their {turns} turns after that, the part above {k} cost ${over:.2f}. Claude also compacted on its own '
                   f'{autos} times, which summarizes at a moment you did not choose and can drop details.',
        'how': f'Once a session passes {k} tokens, a notice says so, and again at every 150k more. Then finish the '
               f'task, or carry it into a small session: {do}. Do it before the cache expires (5 minutes idle, 1 hour '
               'with the 1-hour cache), when reading the context is cheapest.',
        'assumption': 'How much it saves depends on how long those sessions would have run on, so no amount is promised.',
        'reminder': {'id': 'context-size', 'at': context_limit, 'every': 150_000,
                     'text': f'Context is {{k}}k tokens, and every turn sends all of it again. Finish this task, or: {do}.'},
        'change': 'Turns on the reminder in this plugin. Nothing else changes.',
        'actions': [], 'restart': False,
    }
    if not frugal and not has_skill:
        tip['change'] = ('Turns on the reminder, and installs a /handover skill in ~/.claude/skills/handover/SKILL.md, '
                         'because Claude Code has none built in. It runs only when you type '
                         '/handover, so it adds nothing to your context otherwise. Handovers go to ~/.claude/handovers/, '
                         'outside your repos, in the same format as /frugal restart from the Frugalitas plugin.')
        tip['actions'] = [{'op': 'copy-file', 'src': SKILL, 'dest': '~/.claude/skills/handover/SKILL.md'}]
    return tip
