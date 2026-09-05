import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]


def snippets():
    workflow = (ROOT / '.github/workflows/compute-release.yml').read_text(encoding='utf-8-sig')
    return [textwrap.dedent(block) for block in re.findall(
        r'        shell: python\n        run: \|\n((?:          [^\n]*\n?)+)', workflow)]


class ComputeWorkflowTests(unittest.TestCase):
    def run_snippet(self, code, pages, expected=''):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'outputs'
            env = {'GITHUB_OUTPUT': str(output), 'GITHUB_REPOSITORY': 'aegolius-labs/example',
                   'EXPECTED_TAG_STATE': expected}
            with patch.dict(os.environ, env), patch('subprocess.check_output', return_value=json.dumps(pages).encode()) as api:
                exec(compile(code, 'compute-release.yml', 'exec'), {})
                self.assertEqual(['gh', 'api', '--paginate', '--slurp',
                                  'repos/aegolius-labs/example/tags?per_page=100'], api.call_args.args[0])
            return output.read_text() if output.exists() else ''

    def test_untagged_computation_fingerprints_without_bootstrap(self):
        before, after = snippets()
        expected = hashlib.sha256(b'[]').hexdigest()
        self.assertEqual(f'digest={expected}\n', self.run_snippet(before, [[]]))
        self.run_snippet(after, [[]], expected)

    def test_pages_and_order_produce_canonical_fingerprint(self):
        before, after = snippets()
        pages = [[{'name': 'v1.0.0', 'commit': {'sha': 'a' * 40}}],
                 [{'name': 'v0.1.0', 'commit': {'sha': 'b' * 40}}]]
        expected = self.run_snippet(before, pages).strip().split('=')[1]
        self.run_snippet(after, pages[::-1], expected)

    def test_drift_fails_before_any_mutation(self):
        before, after = snippets()
        expected = self.run_snippet(before, [[]]).strip().split('=')[1]
        pages = [[{'name': 'v0.1.0', 'commit': {'sha': 'b' * 40}}]]
        with self.assertRaisesRegex(SystemExit, 'drifted'):
            self.run_snippet(after, pages, expected)


if __name__ == '__main__':
    unittest.main()
