import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('release_assets', Path(__file__).parents[1] / 'scripts/release_assets.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
SHA = 'a' * 40
TAG = 'v0.1.1'
REPO = 'aegolius-labs/example'


class FakeGitHub:
    def __init__(self):
        self.current_sha = SHA
        self.tag_list = [{'name': 'v0.1.0', 'sha': 'b' * 40}]
        self.release = None
        self.uploaded = {}
        self.writes = []
        self.fail_upload_number = None
        self.fail_publish = False
        self.fail_after_publish = False
        self.immutable = True

    def tags(self): return copy.deepcopy(self.tag_list)
    def head(self): return self.current_sha
    def find_release(self, tag): return copy.deepcopy(self.release)
    def get_release(self, release_id): return copy.deepcopy(self.release)
    def assets(self, release_id):
        return [{'id': name, 'name': name, 'state': 'uploaded'} for name in self.uploaded]
    def download(self, asset): return self.uploaded[asset['id']]
    def create_tag(self, tag, sha):
        self.writes.append('tag')
        self.tag_list.append({'name': tag, 'sha': sha})
    def create_draft(self, tag, sha, body):
        self.writes.append('draft')
        self.release = {'id': 7, 'tag_name': tag, 'body': body, 'draft': True,
                        'prerelease': False, 'immutable': False}
        return copy.deepcopy(self.release)
    def upload(self, tag, path):
        if self.fail_upload_number == len(self.uploaded) + 1:
            raise r.ReleaseError('injected upload failure')
        self.writes.append(f'upload:{path.name}')
        self.uploaded[path.name] = path.read_bytes()
    def publish(self, release_id):
        if self.fail_publish:
            raise r.ReleaseError('injected publish failure')
        self.writes.append('publish')
        self.release.update(draft=False, immutable=self.immutable)
        if self.fail_after_publish:
            raise r.ReleaseError('injected lost publish response')


class ReleaseAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name)
        self.api = FakeGitHub()
        self.inventory = {'schema_version': 1, 'repository': REPO, 'candidate_sha': SHA,
                          'tag': TAG, 'version': TAG[1:], 'notes': 'Release notes',
                          'tag_state_sha256': r.tag_fingerprint(self.api.tags()), 'assets': []}
        for name, value in [('example.whl', b'wheel bytes'), ('example.tar.gz', b'sdist bytes')]:
            (self.bundle / name).write_bytes(value)
            self.inventory['assets'].append({'name': name, 'size': len(value), 'sha256': r.digest(value)})
        self.save_inventory()
        self.receipts = []

    def save_inventory(self):
        raw = r.canonical(self.inventory) + b'\n'
        (self.bundle / 'release-inventory.json').write_bytes(raw)
        self.expected_digest = r.digest(raw)

    def run_publish(self):
        return r.run_release(self.bundle, self.expected_digest, REPO, SHA, TAG, self.api,
                             lambda value: self.receipts.append(copy.deepcopy(value)))

    def test_draft_and_verified_assets_precede_immutable_publication(self):
        result = self.run_publish()
        self.assertEqual(['tag', 'draft', 'upload:example.tar.gz', 'upload:example.whl', 'publish'], self.api.writes)
        self.assertEqual('completed', result['status'])
        self.assertTrue(self.api.release['immutable'])
        completed = result['completed']
        self.assertLess(completed.index('draft_assets_verified'), completed.index('publication_requested'))
        self.assertEqual('published_assets_verified', completed[-1])

    def test_local_tamper_fails_before_any_write(self):
        (self.bundle / 'example.whl').write_bytes(b'changed')
        with self.assertRaisesRegex(r.ReleaseError, 'Local asset'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_inventory_digest_tamper_fails_before_any_write(self):
        self.expected_digest = 'f' * 64
        with self.assertRaisesRegex(r.ReleaseError, 'Inventory digest'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_identity_mismatch_fails_before_any_write(self):
        self.inventory['candidate_sha'] = 'c' * 40
        self.save_inventory()
        with self.assertRaisesRegex(r.ReleaseError, 'identity'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_extra_missing_and_duplicate_bundle_entries_fail(self):
        for mode in ('extra', 'missing', 'duplicate', 'traversal'):
            with self.subTest(mode=mode):
                original = copy.deepcopy(self.inventory)
                if mode == 'extra': (self.bundle / 'extra.txt').write_text('extra')
                if mode == 'missing': (self.bundle / 'example.whl').unlink()
                if mode == 'duplicate': self.inventory['assets'].append(self.inventory['assets'][0])
                if mode == 'traversal': self.inventory['assets'][0]['name'] = '../outside.whl'
                self.save_inventory()
                with self.assertRaises(r.ReleaseError): self.run_publish()
                self.assertEqual([], self.api.writes)
                (self.bundle / 'extra.txt').unlink(missing_ok=True)
                (self.bundle / 'example.whl').write_bytes(b'wheel bytes')
                self.inventory = original

    def test_head_and_tag_drift_fail_before_any_write(self):
        self.api.current_sha = 'c' * 40
        with self.assertRaisesRegex(r.ReleaseError, 'main moved'): self.run_publish()
        self.api.current_sha = SHA
        self.api.tag_list.append({'name': 'v0.2.0', 'sha': SHA})
        with self.assertRaisesRegex(r.ReleaseError, 'Tag state drifted'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_wrong_target_tag_fails_before_any_write(self):
        self.api.tag_list.append({'name': TAG, 'sha': 'c' * 40})
        with self.assertRaisesRegex(r.ReleaseError, 'different candidate'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_partial_upload_resumes_same_draft_without_replacing_asset(self):
        self.api.fail_upload_number = 2
        with self.assertRaisesRegex(r.ReleaseError, 'injected'): self.run_publish()
        self.assertTrue(self.api.release['draft'])
        self.assertEqual('failed', self.receipts[-1]['status'])
        self.assertEqual(7, self.receipts[-1]['release_id'])
        self.api.fail_upload_number = None
        self.run_publish()
        self.assertEqual(1, self.api.writes.count('draft'))
        self.assertEqual(1, self.api.writes.count('upload:example.tar.gz'))
        self.assertEqual(1, self.api.writes.count('publish'))

    def test_failure_immediately_after_draft_can_resume(self):
        self.api.fail_upload_number = 1
        with self.assertRaises(r.ReleaseError): self.run_publish()
        self.assertEqual(['tag', 'draft'], self.api.writes)
        self.api.fail_upload_number = None
        self.run_publish()
        self.assertEqual(1, self.api.writes.count('tag'))

    def test_conflicting_draft_asset_fails_before_further_writes(self):
        self.api.fail_publish = True
        with self.assertRaises(r.ReleaseError): self.run_publish()
        self.api.uploaded['example.whl'] = b'foreign payload'
        self.api.writes.clear()
        with self.assertRaisesRegex(r.ReleaseError, 'Remote asset hash'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_extra_remote_asset_fails_before_further_writes(self):
        self.api.fail_publish = True
        with self.assertRaises(r.ReleaseError): self.run_publish()
        self.api.uploaded['extra.txt'] = b'extra'
        self.api.writes.clear()
        with self.assertRaisesRegex(r.ReleaseError, 'Unexpected'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_foreign_release_marker_is_never_overwritten(self):
        self.api.release = {'id': 7, 'tag_name': TAG, 'body': 'unrelated', 'draft': True}
        with self.assertRaisesRegex(r.ReleaseError, 'marker'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_lost_publish_response_recovers_as_verified_noop(self):
        self.api.fail_after_publish = True
        with self.assertRaises(r.ReleaseError): self.run_publish()
        self.api.writes.clear()
        self.api.current_sha = 'd' * 40  # A later main commit must not prevent verification.
        result = self.run_publish()
        self.assertEqual([], self.api.writes)
        self.assertEqual(['verified_existing_publication'], result['completed'])

    def test_published_release_is_not_repaired_when_assets_drift(self):
        self.run_publish()
        self.api.uploaded.pop('example.whl')
        self.api.writes.clear()
        with self.assertRaisesRegex(r.ReleaseError, 'missing required'): self.run_publish()
        self.assertEqual([], self.api.writes)

    def test_disabled_immutability_is_reported_without_rollback(self):
        self.api.immutable = False
        with self.assertRaisesRegex(r.ReleaseError, 'immutability'): self.run_publish()
        self.assertFalse(self.api.release['draft'])
        self.assertEqual('failed', self.receipts[-1]['status'])
        self.assertEqual('publish', self.api.writes[-1])


if __name__ == '__main__':
    unittest.main()
