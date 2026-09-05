"""Publish only a verified release bundle, with publication as the final write.

No dependency beyond Python and the authenticated GitHub CLI. Importing this
module performs no I/O. The transport is injected for offline failure tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class ReleaseError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def tag_fingerprint(tags):
    return digest(canonical(sorted(tags, key=lambda entry: entry['name'])))


class GitHub:
    def __init__(self, repository):
        self.repository = repository
        self.prefix = f'repos/{repository}'

    def request(self, endpoint, method='GET', data=None, pages=False, binary=False):
        args = ['gh', 'api', '--method', method, f'{self.prefix}/{endpoint}']
        args += ['-H', 'X-GitHub-Api-Version: 2022-11-28']
        if pages:
            args += ['--paginate', '--slurp']
        if binary:
            args += ['-H', 'Accept: application/octet-stream']
        if data is not None:
            args += ['--input', '-']
        result = subprocess.run(args, input=canonical(data) if data is not None else None,
                                capture_output=True, check=False)
        if result.returncode:
            # Keep credentials and arbitrary server responses out of receipts.
            raise ReleaseError(f'GitHub {method} {endpoint} failed (exit {result.returncode})')
        if binary:
            return result.stdout
        value = json.loads(result.stdout)
        return [entry for page in value for entry in page] if pages else value

    def tags(self):
        return [{'name': tag['name'], 'sha': tag['commit']['sha']}
                for tag in self.request('tags?per_page=100', pages=True)]

    def head(self):
        return self.request('git/ref/heads/main')['object']['sha']

    def find_release(self, tag):
        matches = [entry for entry in self.request('releases?per_page=100', pages=True)
                   if entry['tag_name'] == tag]
        if len(matches) > 1:
            raise ReleaseError('Multiple releases claim the expected tag')
        return matches[0] if matches else None

    def get_release(self, release_id):
        return self.request(f'releases/{release_id}')

    def assets(self, release_id):
        return self.request(f'releases/{release_id}/assets?per_page=100', pages=True)

    def download(self, asset):
        return self.request(f"releases/assets/{asset['id']}", binary=True)

    def create_tag(self, tag, sha):
        return self.request('git/refs', 'POST', {'ref': f'refs/tags/{tag}', 'sha': sha})

    def create_draft(self, tag, sha, body):
        return self.request('releases', 'POST', {'tag_name': tag, 'target_commitish': sha,
                            'name': tag, 'body': body, 'draft': True, 'prerelease': False})

    def upload(self, tag, path):
        result = subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo',
                                 self.repository], capture_output=True)
        if result.returncode:
            raise ReleaseError('Asset upload failed; refresh the matching draft before retry')

    def publish(self, release_id):
        return self.request(f'releases/{release_id}', 'PATCH',
                            {'draft': False, 'make_latest': 'true'})


def load_bundle(bundle, expected_digest, repository, sha, tag):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ReleaseError('Invalid repository identity')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ReleaseError('Expected a full candidate commit SHA')
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ReleaseError('Expected a stable vMAJOR.MINOR.PATCH tag')
    inventory = bundle / 'release-inventory.json'
    if inventory.is_symlink() or not inventory.is_file():
        raise ReleaseError('Missing regular inventory file')
    raw = inventory.read_bytes()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_digest) or digest(raw) != expected_digest:
        raise ReleaseError('Inventory digest mismatch')
    data = json.loads(raw)
    if (data.get('schema_version'), data.get('repository'), data.get('candidate_sha'),
        data.get('tag'), data.get('version')) != (1, repository, sha, tag, tag[1:]):
        raise ReleaseError('Inventory identity mismatch')
    if not re.fullmatch(r'[0-9a-f]{64}', data.get('tag_state_sha256', '')):
        raise ReleaseError('Invalid tag-state fingerprint')
    assets = data.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 100:
        raise ReleaseError('Invalid asset inventory')
    if not isinstance(data.get('notes', ''), str):
        raise ReleaseError('Invalid release notes')
    names = {'release-inventory.json'}
    for asset in assets:
        name = asset.get('name', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in names:
            raise ReleaseError('Unsafe or duplicate asset name')
        names.add(name)
        path = bundle / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseError('Missing regular asset file')
        raw = path.read_bytes()
        if type(asset.get('size')) is not int or len(raw) != asset['size'] or digest(raw) != asset.get('sha256'):
            raise ReleaseError('Local asset inventory mismatch')
    if {path.name for path in bundle.iterdir()} != names:
        raise ReleaseError('Unexpected files in release bundle')
    return data


def run_release(bundle, expected_digest, repository, sha, tag, api, journal,
                require_immutable=True):
    data = load_bundle(bundle, expected_digest, repository, sha, tag)
    marker = f'<!-- aegolius-release-inventory:{expected_digest} -->'
    expected = {entry['name']: entry for entry in data['assets']}
    state = {'schema_version': 1, 'repository': repository, 'candidate_sha': sha,
             'tag': tag, 'inventory_sha256': expected_digest, 'status': 'running',
             'completed': [], 'release_id': None}

    def record(step):
        state['completed'].append(step)
        journal(state)

    def verify_identity(release):
        if release['tag_name'] != tag or marker not in (release.get('body') or '') or release.get('prerelease'):
            raise ReleaseError('Release identity or inventory marker mismatch')

    def check_tags(require_head=True):
        tags = api.tags()
        matching = [entry for entry in tags if entry['name'] == tag]
        if len(matching) > 1 or (matching and matching[0]['sha'] != sha):
            raise ReleaseError('Existing tag points to a different candidate')
        if require_head:
            if api.head() != sha:
                raise ReleaseError('Protected main moved after preflight')
            remaining = [entry for entry in tags if entry['name'] != tag]
            if tag_fingerprint(remaining) != data['tag_state_sha256']:
                raise ReleaseError('Tag state drifted after version computation')
        return bool(matching)

    def verify_assets(release_id, complete):
        found = {}
        for asset in api.assets(release_id):
            name = asset['name']
            if name not in expected or name in found or asset.get('state') != 'uploaded':
                raise ReleaseError('Unexpected, duplicate, or incomplete remote asset')
            payload = api.download(asset)
            wanted = expected[name]
            if len(payload) != wanted['size'] or digest(payload) != wanted['sha256']:
                raise ReleaseError('Remote asset hash mismatch')
            found[name] = asset
        if complete and set(found) != set(expected):
            raise ReleaseError('Published/draft release is missing required assets')
        return found

    journal(state)
    try:
        release = api.find_release(tag)
        if release:
            verify_identity(release)
            state['release_id'] = release['id']
            if not release['draft']:
                if not check_tags(require_head=False):
                    raise ReleaseError('Published release has no expected tag')
                verify_assets(release['id'], complete=True)
                if require_immutable and release.get('immutable') is not True:
                    raise ReleaseError('Published release is not immutable')
                state['status'] = 'completed'
                record('verified_existing_publication')
                return state
        tag_exists = check_tags()
        # Verify all pre-existing draft assets BEFORE any new write.
        found = verify_assets(release['id'], complete=False) if release else {}
        if not tag_exists:
            api.create_tag(tag, sha)
            record('tag_created')
        if not release:
            check_tags()
            release = api.create_draft(tag, sha, data.get('notes', '') + '\n\n' + marker)
            state['release_id'] = release['id']
            record('draft_created')
        for name in sorted(expected):
            if name not in found:
                check_tags()
                current = api.get_release(release['id'])
                verify_identity(current)
                if not current['draft']:
                    raise ReleaseError('Draft was published before asset completion')
                api.upload(tag, bundle / name)
                record(f'asset_uploaded:{name}')
        check_tags()
        current = api.get_release(release['id'])
        verify_identity(current)
        if not current['draft']:
            raise ReleaseError('Draft state changed before publication')
        verify_assets(release['id'], complete=True)
        record('draft_assets_verified')
        api.publish(release['id'])
        record('publication_requested')
        current = api.get_release(release['id'])
        verify_identity(current)
        if current['draft'] or (require_immutable and current.get('immutable') is not True):
            raise ReleaseError('Publication/immutability verification failed')
        if not check_tags(require_head=False):
            raise ReleaseError('Published tag missing')
        verify_assets(release['id'], complete=True)
        state['status'] = 'completed'
        record('published_assets_verified')
        return state
    except Exception as exc:
        state['status'] = 'failed'
        state['error'] = str(exc) if isinstance(exc, ReleaseError) else type(exc).__name__
        journal(state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if (os.environ.get('GITHUB_REPOSITORY') != args.repository
        or os.environ.get('GITHUB_SHA') != args.sha
        or os.environ.get('GITHUB_REF') != 'refs/heads/main'):
        parser.error('Publication requires the exact main workflow candidate')
    def journal(value):
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.receipt.with_suffix('.tmp')
        temporary.write_bytes(canonical(value) + b'\n')
        temporary.replace(args.receipt)
    try:
        result = run_release(args.bundle, args.inventory_sha256, args.repository,
                             args.sha, args.tag, GitHub(args.repository), journal)
    except Exception as exc:
        print(str(exc) if isinstance(exc, ReleaseError) else type(exc).__name__, file=sys.stderr)
        return 1
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            out.write(f"released=true\nrelease-id={result['release_id']}\n")
    print(f"Verified release {args.tag} ({result['release_id']})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
