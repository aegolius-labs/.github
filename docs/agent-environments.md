# Agent environments

Most work on these repositories is done with coding agents. Some operations are
refused in hosted agent sandboxes, and the failure is easy to misread as a bug
in the kit. This page records what is known, so nobody re-investigates it.

## Claude Code on the web (cloud sessions)

Measured repeatedly between 2026-10-06 and 2026-11-02.

| Operation | Result in a cloud session | Where to run it instead |
| --- | --- | --- |
| GitHub GraphQL API | HTTP 403, "not available from Claude Code sessions" | A local machine with `gh` or `GH_TOKEN` |
| Agentic Backlog Kit `snapshot`, live `sync-plan`, `sync-apply`, `scaffold-apply`, `init-apply` | Fail, because Projects v2 is GraphQL only | Locally |
| Pushing a git tag (git or REST) | Refused by the egress proxy (403) | Locally, or let the release workflow mint it |
| Repository settings, rulesets, `gh repo create` | Refused | Locally, with an admin token |
| REST reads and writes on issues, PRs and contents | Work | Anywhere |
| `claude -p` evaluation lanes (QA kit `scripts/q*_claude_code.py`, abk installed-plugin eval) | Work | Anywhere; see the cost notes below |

Do not work around the GraphQL refusal by filing issues over REST. That skips
the kit's plan, digest, apply and receipt contract and leaves the Project board
out of date. Plan and apply live syncs on a local machine instead.

The GitHub MCP server available to agents has no Projects v2 support either,
which is why `agentic-backlog-kit` deliberately ships no `.mcp.json`.

## Local agents in auto or permission-gated modes

A local agent's permission classifier may refuse external writes (`sync-apply`,
`gh api` writes, `gh repo create`) even when the human has approved the plan in
chat. Either run the printed command yourself, which is the approval the kit
expects anyway, or add an explicit allow rule in the agent's settings.

## Evaluation cost

Evaluation lanes spend the account that runs them. Measured costs are recorded
next to each lane in `agentic-qa-kit/evals/README.md` and `ROADMAP.md`. Two
concurrent workers stay inside one account's session limit; six did not. While
a lane runs, do not edit the plugin working tree it installed from; work in a
separate `git worktree`.
