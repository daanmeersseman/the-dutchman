"""Checks for actions.py on a temporary folder. Run: python test_actions.py"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actions


class ActionsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.backups = os.path.join(self.dir, 'backups')
        self.settings = os.path.join(self.dir, 'settings.json')
        with open(self.settings, 'w', encoding='utf-8') as f:
            json.dump({'env': {'A': '1'}, 'model': 'opus'}, f)

    def read(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_merge_then_undo_restores_bytes(self):
        before = self.read(self.settings)
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'env': {'B': '2'}}}], backups=self.backups)
        self.assertTrue(r['ok'], r)
        self.assertEqual(json.loads(self.read(self.settings)), {'env': {'A': '1', 'B': '2'}, 'model': 'opus'})
        self.assertTrue(actions.undo('t', backups=self.backups)['ok'])
        self.assertEqual(self.read(self.settings), before)

    def test_dry_writes_nothing_and_shows_diff(self):
        before = self.read(self.settings)
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}}], backups=self.backups, dry=True)
        self.assertTrue(r['ok'])
        self.assertIn('+  "x": 1', r['message'])
        self.assertEqual(self.read(self.settings), before)
        self.assertFalse(os.path.exists(self.backups))

    def test_copy_into_new_folder_undo_removes_it(self):
        src = os.path.join(self.dir, 'src.md')
        open(src, 'w').write('hi')
        dest = os.path.join(self.dir, 'skills', 'handover', 'SKILL.md')
        self.assertTrue(actions.apply('c', [{'op': 'copy-file', 'src': src, 'dest': dest}], backups=self.backups)['ok'])
        self.assertEqual(self.read(dest), 'hi')
        actions.undo('c', backups=self.backups)
        self.assertFalse(os.path.exists(os.path.dirname(dest)))

    def test_json_list_moves_server(self):
        local = os.path.join(self.dir, 'local.json')
        json.dump({'enabledMcpjsonServers': ['aspire', 'x'], 'disabledMcpjsonServers': ['pw']}, open(local, 'w'))
        actions.apply('m', [{'op': 'json-list', 'file': local, 'key': 'enabledMcpjsonServers', 'remove': ['aspire']},
                            {'op': 'json-list', 'file': local, 'key': 'disabledMcpjsonServers', 'add': ['aspire']}],
                      backups=self.backups)
        self.assertEqual(json.loads(self.read(local)), {'enabledMcpjsonServers': ['x'], 'disabledMcpjsonServers': ['pw', 'aspire']})

    def test_frontmatter_per_item(self):
        for n in ('a', 'b'):
            os.makedirs(os.path.join(self.dir, n))
            open(os.path.join(self.dir, n, 'SKILL.md'), 'w').write('---\nname: x\ndescription: y\n---\nbody\n')
        act = [{'op': 'frontmatter-set', 'file': os.path.join(self.dir, '{item}', 'SKILL.md'),
                'key': 'disable-model-invocation', 'value': 'true'}]
        self.assertTrue(actions.apply('s', act, ['a'], backups=self.backups)['ok'])
        self.assertIn('disable-model-invocation: true\n---\nbody', self.read(os.path.join(self.dir, 'a', 'SKILL.md')))
        self.assertNotIn('disable', self.read(os.path.join(self.dir, 'b', 'SKILL.md')))

    def test_bad_item_is_refused(self):
        r = actions.apply('s', [{'op': 'copy-file', 'src': 'x', 'dest': '{item}'}], ['../evil'], backups=self.backups)
        self.assertFalse(r['ok'])

    def test_failure_leaves_nothing_changed(self):
        before = self.read(self.settings)
        r = actions.apply('f', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}},
                                {'op': 'copy-file', 'src': os.path.join(self.dir, 'missing'), 'dest': self.settings}],
                          backups=self.backups)
        self.assertFalse(r['ok'])
        self.assertEqual(self.read(self.settings), before)

    def test_undo_refuses_after_later_edit(self):
        actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}}], backups=self.backups)
        open(self.settings, 'a').write(' ')
        self.assertFalse(actions.undo('t', backups=self.backups)['ok'])

    def test_invalid_json_is_not_overwritten(self):
        open(self.settings, 'w').write('{broken')
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}}], backups=self.backups)
        self.assertFalse(r['ok'])
        self.assertEqual(self.read(self.settings), '{broken')


if __name__ == '__main__':
    unittest.main()
