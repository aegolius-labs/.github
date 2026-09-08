# Verified distribution releases

`compute-release.yml` computes a stable Conventional Commit version on main with
read-only contents permission. It makes no bootstrap/tag/release writes, binds
the result to `github.sha`, and rejects tag drift around computation. The upstream
version action runs with dry_run=true and fetch_all_tags=true. No-bump has an
empty new-tag output. Untagged histories use that action's virtual v0.0.0 baseline.

`publish-release-assets.yml` is an opt-in interface for callers with distribution
assets. Existing `conventional-release.yml` callers are unchanged. Pin both new
workflows to the same full shared commit and pass that commit as automation-sha.

The caller must validate its candidate, build files, and upload one immutable
Actions artifact containing release-inventory.json and exactly its listed files.
Pass the artifact ID from that upload, the inventory's raw SHA-256, candidate SHA,
and stable vMAJOR.MINOR.PATCH tag. Download uses only the current workflow run;
no artifact-name search or external run ID is accepted.

Inventory schema 1 contains repository, candidate_sha, tag, version,
tag_state_sha256, notes, and assets (name, size, sha256; optional extra descriptive
fields are ignored). tag_state_sha256 is the compute job output. File names must
be simple basenames. The exact asset inventory is verified before writes, after
upload, and after publication. The inventory itself is not a release asset.

The publisher requires main at the preflighted commit and unchanged previous tag
state, creates a lightweight tag and a marked draft, verifies downloads, and
publishes last. It never deletes/replaces assets, tags, or releases. Matching
partial drafts resume; already published matching releases verify without writes.
Mismatches require reviewed remediation. Receipts retain completed steps and the
release ID, including a failed/uncertain publication outcome.

Callers must configure and independently verify release immutability before
activating this path. Reading that repository setting needs Administration read
permission, which GITHUB_TOKEN does not have; the workflow deliberately does not
request an admin token. It checks immutable=true on published readback and stops
without rollback if configuration was wrong. Preflight that setting during the
reviewed repository rollout, and do not change it while publishing.

Retain the caller's bundle for 30 days (the recovery window). Receipts are retained
for 30 days. Rerun only failed publisher jobs with the original inputs/bundle for
recovery. Rerunning the entire compute/build chain after tagging may yield a
no-bump result; use the receipt and original job for recovery. Expired bundles
require a newly reviewed recovery plan; rebuilding is not proof of byte identity.

Offline tests: `python -B -m unittest discover -s tests -v`.
Hosted syntax, no-bump, and a separately authorized disposable immutable-release
run remain required rollout evidence. Local fake-transport tests do not establish
GitHub permission enforcement or hosted execution.
