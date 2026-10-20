"""Find cost-saving tips for this Claude Code setup, priced on the user's own session logs.

Usage: python analyze.py [--days N] [--home DIR] [--cwd DIR] [--context-limit TOKENS] [--cache-stake USD]
Prints JSON: {"days", "spend", "calls", "tips": [...]}. Every amount is at Anthropic list price over the window.

Each tip is a folder tips/<id>/ with detect.py, whose detect(**ctx) returns a tip or None. ctx holds
calls, sessions, settings, home, cwd, days and the user's
choices context_limit (0: off) and cache_stake (USD per 30 days, 0: off); take only what you need and end with **_. A tip has:
  id, category, title
  confidence  exact | estimate | measured | config
  saving      USD over the window, or None; measured: what the problem cost, or None
  problem     what was found in *your* logs or settings, with numbers
  how         how the fix works, in plain words
  assumption  what the amount assumes, or None
  change      exactly what Apply changes, file by file; None when there is nothing to apply
  actions     what scripts/actions.py runs on Apply ([] when change is None)
  choose      optional {question, items}: the user picks items first, "{item}" in actions becomes each
  min_version optional Claude Code version the change needs
  restart     whether Claude Code must restart for it; guide: section of docs/guide.md
"""
import argparse, datetime as dt, glob, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tiplib import CONTEXT_LIMIT, MIN_DAYS, cost, load_json, price_of, read_calls, ts  # noqa: E402

TIPS = os.path.join(os.path.dirname(HERE), 'tips')


def detectors():
    for path in sorted(glob.glob(os.path.join(TIPS, '*', 'detect.py'))):
        name = os.path.basename(os.path.dirname(path))
        spec = importlib.util.spec_from_file_location(f'tip_{name.replace("-", "_")}', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield name, mod.detect


def analyze(home, cwd, days, now=None, context_limit=CONTEXT_LIMIT, cache_stake=5.0):
    now = now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    settings = load_json(os.path.join(home, 'settings.json')) or {}
    calls, sessions = read_calls(home, since)
    first = min((c['ts'] for c in calls), default=None)
    history = (now - ts(first)).days if first else 0
    out = {'days': days, 'history_days': history, 'calls': len(calls),
           'spend': round(sum(cost(c['t'], price_of(c['model'])) for c in calls), 2), 'tips': [], 'errors': []}
    if history < MIN_DAYS:
        out['note'] = f'Only {history} days of logs; tips need {MIN_DAYS}.'
        return out
    ctx = dict(calls=calls, sessions=sessions, settings=settings, home=home, cwd=cwd, days=days,
               context_limit=context_limit, cache_stake=cache_stake)
    for name, detect in detectors():
        try:
            tip = detect(**ctx)
        except Exception as e:  # one broken tip must not hide the others
            out['errors'].append(f'{name}: {e!r}')
            continue
        if tip:
            for k in ('saving', 'measured'):
                if tip[k] is not None:
                    tip[k] = round(tip[k] * 30 / days, 2)  # per 30 days
            out['tips'].append(tip)
    out['tips'].sort(key=lambda t: -(t['saving'] or 0))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=30)
    ap.add_argument('--home', default=os.path.expanduser('~/.claude'))
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--context-limit', type=int, default=CONTEXT_LIMIT)
    ap.add_argument('--cache-stake', type=float, default=5.0)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(analyze(a.home, a.cwd, a.days, context_limit=a.context_limit, cache_stake=a.cache_stake),
                     ensure_ascii=False))
