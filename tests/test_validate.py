import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate', ROOT / 'scripts/validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class CatalogValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ['marketplace.json', 'README.md', 'README.zh-CN.md', 'LICENSE']:
            shutil.copy2(ROOT / name, self.root / name)
        shutil.copytree(ROOT / '.agents', self.root / '.agents')
        shutil.copytree(ROOT / '.claude-plugin', self.root / '.claude-plugin')
        shutil.copytree(ROOT / 'plugins', self.root / 'plugins')

    def test_current_catalog(self):
        self.assertEqual(validator.validate(self.root), (5, 23, 1))

    def test_marketplace_sync_and_boundaries(self):
        original = json.loads((self.root / 'marketplace.json').read_text())
        cases = {
            'duplicate identity': lambda m: m['plugins'].append(copy.deepcopy(m['plugins'][0])),
            'path traversal': lambda m: m['plugins'][0]['source'].update(path='../escape'),
            'absolute path': lambda m: m['plugins'][0]['source'].update(path='/tmp/escape'),
            'remote entry': lambda m: m['plugins'][0]['source'].update(source='git'),
            'entry mismatch': lambda m: m['plugins'][0].update(name='different'),
            'missing plugin': lambda m: m['plugins'][0]['source'].update(path='./plugins/missing'),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(original)
                mutate(manifest)
                (self.root / 'marketplace.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
        (self.root / 'marketplace.json').write_text(json.dumps(original))

        # Desync between .claude-plugin/marketplace.json and marketplace.json fails.
        claude_path = self.root / '.claude-plugin/marketplace.json'
        claude_original = json.loads(claude_path.read_text())
        claude_mutated = copy.deepcopy(claude_original)
        claude_mutated['plugins'].pop()
        claude_path.write_text(json.dumps(claude_mutated))
        with self.assertRaises(ValueError):
            validator.validate(self.root)

    def test_bundle_and_mcp_boundaries(self):
        plugin = self.root / 'plugins/docs-lookup'
        manifest_path = plugin / 'plugin.json'
        original = json.loads(manifest_path.read_text())
        for field, value in [('name', 'different'), ('version', 'latest'), ('license', 'unknown'),
                             ('skills', '../skills'), ('mcpServers', './.mcp.json'),
                             ('apps', './bindings.json')]:
            with self.subTest(field=field):
                manifest = {**original, field: value}
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
        manifest_path.write_text(json.dumps(original))

        # Forbidden host-specific directories/files are rejected.
        for forbidden in ('hooks', 'commands', '.app.json'):
            with self.subTest(forbidden=forbidden):
                target = plugin / forbidden
                if forbidden.endswith('.json'):
                    target.write_text('{}')
                else:
                    target.mkdir()
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
                if target.is_dir():
                    target.rmdir()
                else:
                    target.unlink()

        # Raw secret in .mcp.json is rejected.
        mcp_path = self.root / 'plugins/starter-template/.mcp.json'
        original_mcp = json.loads(mcp_path.read_text())
        bad_mcp = copy.deepcopy(original_mcp)
        bad_mcp['mcpServers']['example-http']['headers']['Authorization'] = 'Bearer sk-live-raw-secret'
        mcp_path.write_text(json.dumps(bad_mcp))
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        mcp_path.write_text(json.dumps(original_mcp))

        # Symlink inside bundle is rejected.
        (plugin / 'escaped').symlink_to(self.root.parent)
        with self.assertRaises(ValueError):
            validator.validate(self.root)

    def test_skill_and_documentation_contract(self):
        skill = self.root / 'plugins/docs-lookup/skills/library-docs/SKILL.md'
        original = skill.read_text()
        skill.write_text(original.replace('name: library-docs', 'name: wrong'))
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        skill.write_text(original)
        skill.write_text(original.replace('description:', 'description: ' + 'x' * 301))
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        skill.write_text(original)
        readme = self.root / 'README.zh-CN.md'
        readme.write_text(readme.read_text().replace('(plugins/docs-lookup)', '(plugins/missing)'))
        with self.assertRaises(ValueError):
            validator.validate(self.root)


if __name__ == '__main__':
    unittest.main()
