"""Screenshots and page snapshots taken in the main session stay in its context for every later turn."""
import glob, os

from tiplib import MIN_USD, main_turns, read_price

AGENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser-checker.md')
TOKENS = 2_000  # an image is 1k to 4k tokens, a snapshot or request list about 7k characters


def has_browser_agent(home):
    for path in glob.glob(os.path.join(home, 'agents', '*.md')):
        try:
            head = open(path, encoding='utf-8', errors='replace').read(2000)
        except OSError:
            continue
        if 'playwright' in head.split('---', 2)[1 if head.startswith('---') else 0]:
            return True
    return False


def detect(calls, sessions, home, days, **_):
    if has_browser_agent(home):
        return None
    turns = main_turns(calls)
    carried, n = 0.0, 0
    for sid, s in sessions.items():
        later = turns.get(sid) or []
        for stamp in s['pw_main']:
            n += 1
            carried += sum(TOKENS * read_price(c) for c in later if c['ts'] > stamp)
    if carried < 2 * MIN_USD:
        return None
    return {
        'id': 'playwright-agent', 'kind': 'fix', 'confidence': 'estimate',
        'title': 'Let a Sonnet subagent work the browser',
        'saving': carried, 'measured': carried,
        'problem': f'Your sessions took {n} screenshots, page snapshots or request lists with Playwright themselves. Each stays '
                   f'in the context and is read again on every later turn: about ${carried:.2f} in {days} days.',
        'how': 'A browser-checker agent on Sonnet does the clicking and measuring and returns only values and file paths, '
               'never an image. Claude picks it when a task needs a browser; its context ends with the task.',
        'assumption': f'About {TOKENS:,} tokens per result, carried until the session ends. The agent\'s own run costs a '
                      'little, at Sonnet price.',
        'change': 'Adds the agent ~/.claude/agents/browser-checker.md (model: sonnet, tools: Playwright only).',
        'actions': [{'op': 'copy-file', 'src': AGENT, 'dest': '~/.claude/agents/browser-checker.md'}],
        'restart': True,
    }
