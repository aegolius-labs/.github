# Repository settings

The public product repositories (`agentic-backlog-kit`, `agentic-qa-kit`) share
one set of repository settings. They were applied to `agentic-qa-kit` on
2026-10-29 to match `agentic-backlog-kit`. This page records them so a new
repository, or a maintainer checking for drift, does not have to reverse
engineer them from the GitHub UI.

## General

- Merge method: squash only, with auto-merge allowed. The PR title becomes the
  single Conventional Commit the release calculator reads.
- Delete head branches after merge.
- Secret scanning with push protection.
- Private vulnerability reporting.
- CodeQL default setup for `actions` and `python`.
- `.github/CODEOWNERS` assigns every path to the owner.

## Rulesets

Rulesets, not classic branch protection, guard `main` and release tags.

- [`main-ruleset.json`](main-ruleset.json): on the default branch, no deletion
  or force push, linear history, a pull request with one approving Code Owner
  review (stale approvals dismissed, threads resolved, squash only), the `test`
  status check (strict), and CodeQL with no high or higher security alert.
  Repository admins may bypass only through a pull request.
- [`release-tags-ruleset.json`](release-tags-ruleset.json): `v*` tags can be
  neither updated nor deleted, with no bypass. Creation stays open because the
  release workflow mints tags with the Actions token, and GitHub does not
  accept the GitHub Actions app as a bypass actor.

The `integration_id` 15368 on the `test` check is GitHub Actions.

## Applying them

Repository settings and rulesets need an admin token. Apply a ruleset with:

```bash
gh api -X POST repos/aegolius-labs/<repo>/rulesets --input docs/repo-settings/main-ruleset.json
gh api -X POST repos/aegolius-labs/<repo>/rulesets --input docs/repo-settings/release-tags-ruleset.json
```

Check for drift with `gh api repos/aegolius-labs/<repo>/rulesets` and compare
each ruleset's `rules` and `bypass_actors` with these files. Claude Code cloud
sessions cannot make these writes; see
[agent environments](../agent-environments.md).

## Visibility

All four repositories are public. Private repositories on the Free plan ran out
of GitHub Actions minutes, which stopped CI and releases for `agentic-qa-kit`
until it went public on 2026-10-29. Anything committed here is published.
