# Contributing to Aegolius Labs

This guide applies to every Aegolius Labs repository. A repository's own
`CONTRIBUTING.md`, `AGENTS.md` and `CLAUDE.md` add to it and win where they are
more specific. GitHub shows this file for any repository that has no
`CONTRIBUTING.md` of its own.

Everything here serves one end goal: `aio-agentic-sdlc`, a framework where a
person states intent, agents build and update the Intention and Reality DAGs,
and the scored diff between them is the backlog. Its
[`doc/VISION.md`](https://github.com/aegolius-labs/aio-agentic-sdlc/blob/main/doc/VISION.md)
is the vision for the whole organization. The other repositories are its
layers, and the kits also work on their own.

The products are:

| Repository | What it is |
| --- | --- |
| [aio-agentic-sdlc](https://github.com/aegolius-labs/aio-agentic-sdlc) | The framework and end product: Intention and Reality DAGs, the diff as the backlog, approval gates |
| [agentic-backlog-kit](https://github.com/aegolius-labs/agentic-backlog-kit) | The projection layer: the framework's work shown on GitHub Issues and Projects |
| [agentic-qa-kit](https://github.com/aegolius-labs/agentic-qa-kit) | The loop closer: an evidence ledger and skills for agent-assisted QA |
| agentic-product-playbook (private, experimental) | Stage and decision guidance for the framework's Intake side. It may become part of the framework instead of a separate product |

A UI layer over the suite is wanted and its form is not chosen yet; see the
vision.

Which repository owns which kind of truth is defined in
[`doc/authority-model.md`](https://github.com/aegolius-labs/aio-agentic-sdlc/blob/main/doc/authority-model.md).
Read it before a change that crosses repositories. The kits are also used
standalone, and that is a supported configuration, not a degraded one.

## Licensing and outside contributions

The products are dual licensed: the PolyForm Noncommercial License for
noncommercial use, and a paid commercial license for everything else (see each
repository's `COMMERCIAL.md`). Aegolius Labs must hold the rights to distribute
every contribution under both. Until a contributor agreement process is
published, outside code pull requests cannot be merged. Issues, design
discussion and documentation feedback are welcome.

Never commit secrets, credentials, production data or private backlog or QA
evidence. The product repositories are public, except agentic-product-playbook
while it is an experiment. Treat anything committed to any of them as public.

## Before you start

- **Read the ROADMAP.** Each repository's `ROADMAP.md` (and `doc/VISION.md` in
  aio-agentic-sdlc) sets the order of work. Pick up the next item there, or
  say in the pull request why a change is out of order.
- **Raise, don't resolve silently.** When a request or document conflicts with
  another document, rests on an assumption, or is ambiguous, raise it in the
  issue or pull request and get the maintainer's answer. Do not pick an
  interpretation quietly. This applies to coding agents as much as to people.
- **Keep layers honest.** Downstream state (a closed issue, a green run, a QA
  finding) is evidence, never intent. See the authority model.

## Product requirements that apply everywhere

- **Hosts.** Claude Code, Codex and Antigravity are all supported agent hosts.
  Behavior lives once in a repository's shared skill content, and each host
  gets only a thin manifest; never fork skill content per host. Each
  repository's README states which hosts it has been validated on so far.
  Support for another provider is welcome as a pull request that follows the
  same pattern.
- **Account types.** Anything that touches GitHub must work for repositories
  and Projects owned by a personal account as well as by an organization,
  unless a real platform limit prevents it. Record such a limit where users
  will see it.
- **Dependencies.** The kits keep their runtime dependency-free unless a
  dependency gives a concrete benefit the standard library cannot provide
  safely.

## Pull requests

1. Work on a branch and open a pull request against `main`. Nobody pushes to
   `main` directly.
2. **CI must be green before merge, for everyone.** Never skip, disable or
   weaken a test or check to get green.
3. A pull request needs one approving review from a code owner, and every
   review thread resolved. Repository rulesets enforce this; see
   [docs/repo-settings](docs/repo-settings/README.md).
4. Merge by squash only. The pull request title becomes the single commit on
   `main`, and that commit decides the release.

## Commit types and releases

Titles follow [Conventional Commits](https://www.conventionalcommits.org/).
Release automation on `main` reads the squash commit and cuts a version from it,
so choose the type deliberately:

| Type | Release |
| --- | --- |
| `feat:` | Minor |
| `fix:` | Patch |
| `docs:`, `test:`, `ci:`, `chore:`, `refactor:` | None |
| `!` or a `BREAKING CHANGE:` footer | Major |

- Use the type for what users get. A pull request that only changes
  documentation is `docs:` even when it documents a feature.
- **No breaking marker before 1.0.** The automation turns any breaking marker
  into a major bump, and a major bump of `0.x` is `1.0.0`. On a `0.x` line,
  name the break in the pull request body and the changelog instead. 1.0 is
  cut deliberately, against each product's published criteria.
- Releases are immutable. A tag or GitHub Release that went out is never
  rewritten; ship a new version instead.
- Write user-visible changes under `## [Unreleased]` in `CHANGELOG.md`. The
  release workflow commits nothing back, so the first change after a release
  promotes the released section by hand.
- The shared release workflows live in this repository. Callers pin
  `compute-release` and `publish-release-assets` to the same full commit and
  pass it as `automation-sha`; move all three together, including in
  Dependabot updates. See [docs/verified-releases.md](docs/verified-releases.md).

## Working with coding agents

Most work here is done with coding agents, under the same rules as people.
External writes (GitHub sync, releases, repository settings) follow the
products' plan, confirm and apply contracts, and a human confirms them. Some
operations do not work from hosted agent sandboxes; see
[docs/agent-environments.md](docs/agent-environments.md) before treating such a
failure as a bug.
