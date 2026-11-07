# Usage evidence contract

Status: proposed. Nothing implements it yet. Each kit adds it through its own
ROADMAP item.

This contract lets a project opt in to recording how the Aegolius Labs kits
are used there, and lets the project's owner share that record on purpose.
It exists so that use of the kits produces evidence about the kits. It is the
same in every kit, so one report can read them all.

## Principles

- **Off unless a person turns it on, per project.** No kit records anything
  in a project that has not opted in. No skill turns it on by itself.
- **Local first.** The record is a file in the project, written by the kit's
  own engine. The engine makes no network call to record usage.
- **Sharing is a separate, explicit act.** Data leaves the machine only when a
  person posts it, or when the project's config records that its owner
  authorized posting to a repository they control.
- **Counts, not content.** The record holds command names, outcomes and
  versions. It never holds anything from the project itself.
- **Evidence about the kits, never intent.** Usage records and feedback never
  create backlog items, Intention nodes or issues on their own. A pattern in
  them becomes work only when a maintainer decides so through a ROADMAP. See
  the [authority model](https://github.com/aegolius-labs/aio-agentic-sdlc/blob/main/doc/authority-model.md).
- **Same on every host and account type.** Recording happens in the engine,
  so it does not depend on host hooks, and nothing touches GitHub until
  something is posted.

## Layout

```text
.aegolius-usage/
  config.json      # presence + enabled: true is the opt-in
  events.jsonl     # one line per engine command
  feedback.jsonl   # one line per feedback note
```

`usage enable` creates the folder and adds `.aegolius-usage/` to the project's
`.gitignore`. The folder is shared by every kit installed in the project, so
one opt-in covers all of them. Each kit writes only its own lines.

### `config.json`

```json
{
  "schema": "aegolius-usage-config/v1",
  "enabled": true,
  "enabled_at": "2026-11-08T14:00:00Z",
  "project_id": "u-7f3c9a2e5b14",
  "publish": null
}
```

- `project_id` is random, made once by `usage enable`. It is never derived
  from the folder, repository or owner name.
- `publish` is `null` unless the owner authorized posting:

```json
"publish": {
  "repository": "OWNER/REPO",
  "authorized_by": "the person, in their own words or handle",
  "authorized_at": "2026-11-08T14:00:00Z"
}
```

An agent must never fill in `publish` for a person. `usage publish` refuses
when it is absent.

### `events.jsonl`

One JSON object per line, written by the engine after each command:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | `aegolius-usage-event/v1` |
| `ts` | string | UTC, ISO 8601 with `Z` |
| `kit` | string | `aio-agentic-sdlc`, `agentic-backlog-kit`, `agentic-qa-kit` or `agentic-product-playbook` |
| `kit_version` | string | The installed version, or `unknown` |
| `command` | string | The command name only, such as `session-close`. Never its arguments. |
| `outcome` | string | `ok`, `refused` or `error` |
| `error_class` | string or null | A fixed code from the kit, never message text |
| `host` | string | `claude-code`, `codex`, `antigravity` or `unknown`. Taken only from a signal the host sets; never guessed. |
| `initiated_by` | string | `person`, `agent` or `unknown`, as passed by the caller. Self-reported, so it is a hint, not proof. |
| `run_id` | string | Random, groups the commands of one workflow. Carries no identity. |

### `feedback.jsonl`

Written only through `usage feedback`, which validates it:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | `aegolius-usage-feedback/v1` |
| `ts` | string | UTC |
| `kit` | string | As above |
| `run_id` | string or null | Links to the workflow it is about |
| `source` | string | `agent-judgment` or `person` |
| `verdict` | string | `helped`, `neutral` or `got_in_the_way` |
| `friction` | list of strings | At most 5 phrases of at most 80 characters each |

Feedback with `source: agent-judgment` is a model's opinion of a tool it was
told to use. Reports must label it as such and never present it as user
evidence.

### Never recorded

File paths, repository, folder or branch names, issue or finding text, code,
command arguments, error messages, user names, email addresses, tokens,
machine names and IP addresses. The engine rejects a `friction` phrase that
looks like a path, URL, email address or secret.

## Commands

Each kit's engine exposes the same subcommands under its own CLI:

| Command | Effect |
| --- | --- |
| `usage enable` | Creates the folder, config and `.gitignore` entry |
| `usage disable` | Sets `enabled: false`; nothing more is written |
| `usage purge` | Deletes the folder |
| `usage feedback` | Validates and appends one feedback line |
| `usage report --root PATH ...` | Read-only summary over one or more projects |
| `usage report --share` | The same summary as Markdown, for a person to post |
| `usage publish` | Posts the summary to the configured repository |

`usage report` follows the QA kit's `metrics` guardrails: every rate shows its
numerator and denominator, counts under 5 are withheld, and there is no view by
person or agent.

## Publishing

- **Owner-authorized.** When `publish` is set, `usage publish` posts the
  summary as a comment on one issue per project in the named repository. The
  issue title is the `project_id`. The repository should be private when the
  projects are. Posting goes through the same GitHub transports as the backlog
  kit (`gh` or a token) and works for personal accounts and organizations.
- **Everyone else.** `usage report --share` prints the summary and the skill
  offers to draft an issue on the kit's public feedback channel. The person
  reviews it and posts it. Nothing is sent without that.
- **What a summary holds.** Counts by kit, command, outcome, host and
  initiator over a stated period, feedback verdict tallies, and friction
  phrases. Nothing else from the ledger.

## Bugs

A defect in a kit is not a usage record. It goes through the QA kit's bug
handoff as its own issue, and is filed only after a person confirms it.

## Skills

Skills may ask, once per project, whether to turn recording on. At the end of
a workflow in a project that has opted in, they ask the agent for one feedback
note through `usage feedback`. A kit without an engine writes the same files
through its skills and states that its records are agent-written.

## Fixture

Each implementing kit carries the same fixture of a config, events and
feedback, byte-identical across repositories, and tests that its engine
accepts it and rejects the forbidden fields above.
