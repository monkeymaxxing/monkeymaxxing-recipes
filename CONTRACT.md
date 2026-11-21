# The Recipe Contract

Every recipe in this repository follows this contract.
`scripts/lint_recipes.py` checks the frontmatter and the required sections
on every pull request. A maintainer checks the core rules by hand.

## Where a recipe lives

A recipe is one Markdown file, `<category>/<id>.md`, such as
`services/redis-cache-pool.md`. Files that belong to the recipe, such as an
example app, a check file, or a test, go in a folder with the same name
beside it: `services/redis-cache-pool/`. A `README.md` in a category folder
introduces the category; it is not a recipe.

## Frontmatter

Every recipe starts with this YAML frontmatter:

```yaml
---
id: redis-cache-pool
title: Add a Redis cache
category: services
applies_to: [stack]
summary: Adds private Redis cache servers that your app reaches over WireGuard, with MMWatchdog checks.
author: your-github-name
vetted_on: 2026-11-25
vetted_against:
  stack: v0.3.0
vetted_method: live-checkpoint
---
```

| Field | Rule |
| --- | --- |
| `id` | Lowercase letters, digits, and hyphens (`^[a-z0-9][a-z0-9-]*$`). The same as the file name without `.md`. Unique in the repository. |
| `title` | A short title that says what the recipe does, such as "Add a Redis cache". |
| `category` | `services`, `watchdog-checks`, `providers`, `frameworks`, or `migrations`. The same as the recipe's folder. |
| `applies_to` | `[stack]`, `[solo]`, or `[stack, solo]`. |
| `summary` | One or two short sentences for the catalog table: what the recipe does, in plain words. |
| `author` | The author's GitHub name. First-party recipes use `monkeymaxxing`. |
| `vetted_on` | The date a maintainer checked the recipe, as `YYYY-MM-DD`. |
| `vetted_against` | The release each checked product was tested against, one line per checked product (a non-empty subset of `applies_to`), such as `stack: v0.3.0`. |
| `vetted_method` | How it was checked: `live-checkpoint` (applied, verified, and removed on a real test system), `script-tests` (the recipe's own script tests passed), or `review-only` (read and reviewed, with nothing to run). |

**Contributors leave out `vetted_on`, `vetted_against`, and
`vetted_method`.** Only a maintainer adds them, when the recipe is accepted.
The pull request checks refuse a pull request that adds or changes any of
the three. The reason: these fields are what tell a reader how far to trust
a recipe, so only the person who did the check may write them.

## The trust banner

Right after the title, every recipe has this banner, word for word:

```markdown
> [!IMPORTANT]
> Vetted once on submission (`vetted_on`) against `vetted_against`. Not routinely re-tested and outside core Stack/Solo support.
```

## Required sections

Every `services/` and `watchdog-checks/` recipe has these sections, with
these exact headings, in this order:

1. **The trust banner** (above).
2. **`## When to use this (and when you don't need it)`**: the problem it
   solves, the sign that a team needs it, and when the core already covers
   the need. For example: "Postgres can cache this for you until X."
3. **`## What it adds and what it costs`**: new servers, packages,
   containers, settings, and checks; the monthly cost; and the ongoing work,
   such as upgrades.
4. **`## Data, security, and backups`**: whether the service keeps data
   that matters (stateful) or can be rebuilt from nothing (stateless). For
   stateful data, how it is backed up to locked storage and how a restore is
   proven. Also every WireGuard connection, firewall rule, and MMWatchdog
   check it adds.
5. **`## Apply steps`**: the exact files to create or change, the
   `custom_` check file names, what goes in the `# --- Custom extensions ---`
   slots and under `custom:`, and which values the coding agent adapts to
   the team's system.
6. **`## Verification check`**: a command to run and the output that proves
   the recipe works.
7. **`## Clean removal`**: how to take everything out again, including
   data, settings, checks, firewall rules, and the `custom_extensions:`
   entry, so the system is the same as before.

### Guides in `providers/`, `frameworks/`, and `migrations/`

These guides are reference documents, and they keep the shape of their
family, which the category's `README.md` describes. They need the
frontmatter and the trust banner. They do not need the seven headings, but
they answer the same questions:

| Question | `providers/` | `frameworks/` | `migrations/` |
| --- | --- | --- | --- |
| When to use it | Why to choose this provider, and its plans and regions | The framework and versions it covers | The platform it moves from, and what does not carry over |
| What it adds and costs | Server prices and account steps | What changes in the app | The steps and the downtime of the move |
| Data, security, and backups | Where the token lives and what it can do | Database, uploads, and secrets in the app | How data is exported, restored, and checked |
| Apply steps | The five provider scripts | Copy and build steps | Export, restore, and cutover steps |
| Verification check | The guide's script tests (`providers/<id>/*_provider_scripts_test.py`) | The guide's checks on a running example app | The checks after restore and after cutover |
| Clean removal | Deleting the servers and the token | Not needed: the app keeps its changes | Rollback and cleanup of the old platform |

## Core rules every recipe keeps

1. **It only adds.** A recipe never replaces or weakens Postgres,
   Cloudflare Tunnel, WireGuard, MMX, MMWatchdog, or the backups.
2. **No open public ports.** Web traffic comes through Cloudflare Tunnel.
   SSH goes through doubleshell over WireGuard. Traffic between servers goes
   over WireGuard. A recipe opens no public web port and no public SSH port.
3. **No secrets in Git.** Secrets go into the encrypted vault, typed by the
   person at a hidden prompt.
4. **Stored data is backed up.** A stateful service backs up its data to
   locked, offsite storage, and the recipe shows how to prove a restore.
5. **Pinned software.** Install Debian packages, or download a program at a
   fixed version and check its SHA-256 before use. Never `curl | sh`.
6. **No weaker defenses.** A recipe never weakens the firewall, AppArmor,
   monitoring, or backups. If it must touch vault keys, `sudoers`, `ssh/`,
   or a file that the Stack's desk review (`ssh desk01-review`) watches, it
   says so at the top of `## Apply steps`, and the coding agent stops to ask.
7. **Check file names.** Each MMWatchdog check file a recipe adds is named
   `custom_<name>.yml` and matches `^[a-z0-9][a-z0-9_-]*\.yml$`, so it never
   collides with a core check file.
8. **Check group names.** Each check group name in that file matches
   `^[a-z0-9_]+$`: underscores, never hyphens. That is the only shape the
   Stack's triage agent may run with `mmwatchdog check-now`. Start group
   names with `custom_` too, so they never collide with a core group.
9. **Use the extension slots.** Fleet stages go between the
   `# --- Custom extensions ---` boundary lines (`playbooks/every_server.yml`
   in the Stack, `playbooks/solo_server.yml` in Solo). Settings go under
   `custom:` in `mmx_project_settings.yml`. The Stack's and Solo's upgrade
   steps keep both.
10. **New providers need one line in the Stack.** A provider whose API takes
    a token in a header only works after its API address is added to
    `providerGuideAPIAddresses` in the Stack's
    `set_up_outside_services/personal_token.go`. That list keeps a coding
    agent from sending the person's provider token to any other host. A new
    provider recipe says this plainly, and its pull request links the
    matching one-line change to
    [monkeymaxxing-stack](https://github.com/monkeymaxxing/monkeymaxxing-stack).
