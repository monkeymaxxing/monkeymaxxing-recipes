---
id: background-job-queue
title: Watch Postgres background job queues
category: watchdog-checks
applies_to: [stack, solo]
summary: Adds MMWatchdog checks that warn when jobs pile up in a Postgres-backed job queue, such as Solid Queue, GoodJob, Oban, or pg-boss, or wait too long to start.
author: monkeymaxxing
vetted_on: 2026-11-23
vetted_against:
  stack: v0.3.1
  solo: v0.1.0
vetted_method: live-checkpoint
---

# Watch Postgres background job queues

> [!IMPORTANT]
> Reviewed once when added. Recipes are not re-tested on every Stack or Solo release and are outside core support.

This recipe adds one MMWatchdog check file with one check for each job queue
you list. Each check counts the jobs that are due and waiting for a worker,
and measures how long the oldest one has waited. It warns when either number
passes its limit.

## When to use this (and when you don't need it)

Many apps send email, build reports, and call other services from background
jobs. The jobs wait in a queue until a worker runs them. When the workers
stop, crash in a loop, or fall behind, nothing breaks on the web pages at
first. Users just stop getting their emails, and nobody notices for hours.

The core does not watch the queue itself. It starts each app's job container
from `jobs_command`, and MMWatchdog records the container's CPU use, but no
core check alerts when jobs stop moving. Use this recipe when your app keeps
its job queue in Postgres with one of these libraries:

| `adapter` | Library | Table it reads |
| --- | --- | --- |
| `solid_queue` | Rails Solid Queue | `solid_queue_ready_executions` and `solid_queue_scheduled_executions` |
| `good_job` | Rails GoodJob | `good_jobs` |
| `oban` | Elixir Oban | `oban_jobs` |
| `pg_boss` | Node.js pg-boss, version 10 or later | `pgboss.job` |

You don't need it when your app has no background jobs (`jobs_command: ""`),
or when its queue lives outside Postgres, such as in Redis with Sidekiq or
BullMQ. This recipe does not read those. You may also skip it while your jobs
are few and nothing depends on them being on time.

What the check counts as a **pending job**: a job that is due now and has not
started. A job scheduled for tomorrow does not count until tomorrow. A job
that is running, finished, or failed for good does not count. For each
adapter:

- `solid_queue`: every row of `solid_queue_ready_executions`, plus each row of
  `solid_queue_scheduled_executions` whose `scheduled_at` has passed. A due
  scheduled job counts too, because it shows a stopped dispatcher. Failed
  jobs are in `solid_queue_failed_executions` and do not count. Solid Queue
  keeps a failed job's `finished_at` empty, so a count of unfinished rows of
  `solid_queue_jobs` would count every failed job forever.
- `good_job`: rows of `good_jobs` with no `finished_at` and no `performed_at`,
  whose `scheduled_at` (or `created_at`, when `scheduled_at` is empty) has
  passed. This is GoodJob's own "queued" state.
- `oban`: rows of `oban_jobs` in the state `available`, `scheduled`, or
  `retryable` whose `scheduled_at` has passed. Oban moves a due `scheduled` or
  `retryable` job to `available` within a second, so a pile of them means
  Oban is not running.
- `pg_boss`: rows of `pgboss.job` in the state `created` or `retry` whose
  `start_after` has passed. pg-boss 9 and earlier named the column
  `startafter`. On those versions the check fails with `column "start_after"
  does not exist`; upgrade pg-boss, or change `start_after` to `startafter`
  in your copy of the check file.

## What it adds and what it costs

It costs $0. It adds no server, no package, no container, and no change to
Postgres.

It adds:

- One file, `mmwatchdog_checks/custom_background_job_queue.yml`, with one
  check group, `custom_background_job_queue`. Each queue you list gets one
  check, named after it, such as `shop_jobs_is_not_backing_up`.
- One entry, `custom_background_job_queue.yml`, in `mmwatchdog_check_files`:
  in the `database_servers` group of `inventories/servers.yml` on the Stack,
  and in `mmx_project_settings.yml` on Solo (the checks run on `solo01`).
- Settings under `custom.background_job_queue:` in `mmx_project_settings.yml`.

Each check runs one small count query a minute. The queries use the indexes
that each library creates for its own workers. The ongoing work is small:
add a queue when you add an app with jobs, and raise `max_pending_jobs` when
your normal busy hour grows.

## Data, security, and backups

The recipe is stateless. It stores no data of its own, so it needs no backup
and no restore proof. The job tables belong to the app and are in the core's
normal Postgres backups.

- **What it reads.** Each check reads a count and the oldest due time. It
  never reads a job's arguments, so no customer data reaches MMWatchdog's
  output or an alert. The output is one line, such as
  `shop_jobs: 3 pending jobs, oldest 0.2 minutes`.
- **Login.** The checks run as the operating system account `postgres` and
  connect to the queue's database through the local socket
  `/var/run/postgresql`. They need no password and add no account. They only
  read. `PGOPTIONS` sets a `statement_timeout` of 10 seconds, so a check never
  runs for long, and the time zone `UTC`, so the libraries' UTC timestamps
  compare correctly.
- **Replicas on the Stack.** The check runs on every database server. On a
  standby replica it passes at once with "standby replica; skipped". On the
  primary it counts. After a failover, the new primary's check takes over by
  itself.
- **Network:** none. The recipe opens no port and adds no firewall rule and no
  WireGuard connection.
- **Check group name:** `custom_background_job_queue`. It uses underscores
  only and matches `^[a-z0-9_]+$`, so on the Stack the triage agent can run
  `sudo mmwatchdog check-now custom_background_job_queue`.
- **Alerts:** every check has `alert_severity: warn`. A warn tells a person
  during the day and wakes nobody. Late jobs hurt, but rarely enough to wake
  someone. A team whose jobs take card payments may raise one check to `sos`.
  While the core check `postgres/postgres_answers` fails, these checks send no
  alert of their own.

## Apply steps

The recipe touches no vault key, `sudoers`, `ssh/`, or file that the Stack's
desk review watches, and changes no core file. The coding agent does not need
to stop for any of them.

The coding agent adapts these values to the team's system:

- One entry in `queues` for each app whose jobs live in Postgres, with the
  app's `database_name` from `apps:` and the right `adapter`. Look in the
  app's code: `config.active_job.queue_adapter` in a Rails app, an `Oban`
  entry in an Elixir app's supervision tree, or `new PgBoss(...)` in a
  Node.js app.
- `schema`, only when the library uses a schema other than its default, such
  as Oban's `prefix` option or pg-boss's `schema` option.
- The two limits, if the team wants others.

**1. Add the settings** under `custom:` in `mmx_project_settings.yml`. On both
the Stack and Solo, `custom:` is inside the `# --- Custom extensions ---`
lines. When `custom:` is still `custom: {}`, replace that line with the block
below. When it already has other keys, add only the `background_job_queue:`
key and keep the rest:

```yaml
  custom:
    background_job_queue:
      queues:
        - name: shop_jobs
          database_name: shop
          adapter: solid_queue
          # Reason for 500: a burst after a busy hour clears in minutes; 500
          # due jobs that stay for 10 minutes mean the workers cannot keep
          # up. Set it well above your own busy hour's number, which the
          # check's output shows.
          max_pending_jobs: 500
          # Reason for 15: a sign-up email or a receipt that waits 15 minutes
          # is already late for the user.
          max_oldest_job_age_minutes: 15
          # Optional. Without it: public, or pgboss for pg_boss.
          # schema: public
```

Each queue has these fields:

| Field | Meaning |
| --- | --- |
| `name` | Lowercase letters, digits, and underscores only. It names the check, such as `shop_jobs_is_not_backing_up`, and starts each output line. Unique in the list. Keep it short: an alert title holds at most 120 characters. |
| `database_name` | The database that holds the queue's tables, usually the app's `database_name`. |
| `adapter` | `solid_queue`, `good_job`, `oban`, or `pg_boss`. |
| `max_pending_jobs` | A whole number. The check fails when more jobs than this are due and waiting. |
| `max_oldest_job_age_minutes` | A number, such as `15` or `2.5`. The check fails when the oldest due job has waited longer. |
| `schema` | Optional. The schema of the queue's tables. |

**2. Create `mmwatchdog_checks/custom_background_job_queue.yml`.** MMX renders
this template on each server into
`/etc/mmwatchdog/check_groups/custom_background_job_queue.yml`. The template
refuses a wrong name, adapter, or limit before anything reaches a server. The
script gets every value through `env`, and the SQL is in quoted heredocs, so
no value is pasted into the SQL or the shell.

```yaml
{{- /*
  MMWatchdog's check group for the background job queues in
  custom.background_job_queue, from the recipe background-job-queue
  (custom_recipes/background-job-queue.md). This file is an MMX template.
  It reads the role input custom.
*/ -}}
{{- if not (hasKey .inputs.custom "background_job_queue") }}{{ fail "custom.background_job_queue is missing from mmx_project_settings.yml. Add it, or remove custom_background_job_queue.yml from mmwatchdog_check_files." }}{{ end }}
{{- $settings := .inputs.custom.background_job_queue }}
{{- if not $settings.queues }}{{ fail "custom.background_job_queue.queues in mmx_project_settings.yml is empty. List at least one queue, or remove custom_background_job_queue.yml from mmwatchdog_check_files." }}{{ end }}
# Managed by MMX from mmwatchdog_checks/custom_background_job_queue.yml in the systems repository.
# This check file comes from the recipe background-job-queue.
# To be woken for a check, set that check's alert_severity to sos.
check_groups:
  # check_every 1m: a queue can back up within minutes.
  # time_limit_per_run 20s: each run is one count query, and PGOPTIONS
  # stops it after 10 seconds.
  # alert_after_failing_for 10m: a deploy restarts the workers, and a burst
  # of jobs clears in minutes. Ten minutes past a limit means the workers
  # are down or too slow.
  # recovered_after_healthy_for 2m: the queue must stay below its limits
  # for two runs before the alert closes.
  # Reason for warn: the site still serves pages; the jobs are late.
  custom_background_job_queue:
    check_every: 1m
    time_limit_per_run: 20s
    alert_after_failing_for: 10m
    recovered_after_healthy_for: 2m
    checks:
{{- range $queue := $settings.queues }}
{{- if not (regexMatch `^[a-z0-9_]+$` (toString $queue.name)) }}{{ fail (printf "custom.background_job_queue.queues has the name %q. Use lowercase letters, digits, and underscores only, such as shop_jobs." (toString $queue.name)) }}{{ end }}
{{- if not (has (toString $queue.adapter) (list "solid_queue" "good_job" "oban" "pg_boss")) }}{{ fail (printf "custom.background_job_queue.queues %s has the adapter %q. Use solid_queue, good_job, oban, or pg_boss." $queue.name (toString $queue.adapter)) }}{{ end }}
{{- if not (regexMatch `^[0-9]+$` (toString $queue.max_pending_jobs)) }}{{ fail (printf "custom.background_job_queue.queues %s has max_pending_jobs %q. Use a whole number, such as 500." $queue.name (toString $queue.max_pending_jobs)) }}{{ end }}
{{- if not (regexMatch `^[0-9]+(\.[0-9]+)?$` (toString $queue.max_oldest_job_age_minutes)) }}{{ fail (printf "custom.background_job_queue.queues %s has max_oldest_job_age_minutes %q. Use a number of minutes, such as 15." $queue.name (toString $queue.max_oldest_job_age_minutes)) }}{{ end }}
{{- /* index gives nothing for an optional field that the queue leaves out; $queue.schema would fail. */}}
{{- $schema := index $queue "schema" }}
{{- if not $schema }}{{ $schema = ternary "pgboss" "public" (eq $queue.adapter "pg_boss") }}{{ end }}
      # What to do: check that the app's job container runs
      # (systemctl status <app>-jobs.service) and read its log. A container
      # that runs but falls behind needs more workers or faster jobs.
      {{ $queue.name }}_is_not_backing_up:
        shell:
          script: |
            set -u
            in_recovery=$(psql -X -At -d "$DATABASE_NAME" -c 'SELECT pg_is_in_recovery()' 2>&1) || {
              echo "$QUEUE_NAME: cannot connect to the database $DATABASE_NAME: $in_recovery"
              exit 1
            }
            if [ "$in_recovery" = t ]; then
              echo "standby replica; skipped: the primary runs this check"
              exit 0
            fi
            # The table that shows that the adapter's migrations ran.
            case "$ADAPTER" in
              solid_queue) table=solid_queue_ready_executions ;;
              good_job) table=good_jobs ;;
              oban) table=oban_jobs ;;
              pg_boss) table=job ;;
            esac
            found=$(psql -X -At -v ON_ERROR_STOP=1 -d "$DATABASE_NAME" -v schema="$SCHEMA" -v table="$table" 2>&1 <<'SQL'
            SELECT to_regclass(format('%I.%I', :'schema', :'table')) IS NOT NULL;
            SQL
            ) || {
              echo "$QUEUE_NAME: cannot look for the table $SCHEMA.$table: $found"
              exit 1
            }
            if [ "$found" != t ]; then
              echo "$QUEUE_NAME: the table $SCHEMA.$table does not exist in the database $DATABASE_NAME."
              echo "Check adapter ($ADAPTER), database_name, and schema in custom.background_job_queue, and that the app's queue migrations ran."
              exit 1
            fi
            # Each query prints the number of due jobs that have not started
            # and the minutes the oldest of them has waited.
            queue_sql() {
              case "$ADAPTER" in
                solid_queue) cat <<'SQL'
            SELECT count(*), coalesce(round(greatest(0, extract(epoch FROM now() - min(due_at)))::numeric / 60, 1), 0)
            FROM (
              SELECT created_at AS due_at FROM :"schema".solid_queue_ready_executions
              UNION ALL
              SELECT scheduled_at FROM :"schema".solid_queue_scheduled_executions WHERE scheduled_at <= now()
            ) AS due_jobs;
            SQL
                  ;;
                good_job) cat <<'SQL'
            SELECT count(*), coalesce(round(greatest(0, extract(epoch FROM now() - min(coalesce(scheduled_at, created_at))))::numeric / 60, 1), 0)
            FROM :"schema".good_jobs
            WHERE finished_at IS NULL AND performed_at IS NULL
              AND coalesce(scheduled_at, created_at) <= now();
            SQL
                  ;;
                oban) cat <<'SQL'
            SELECT count(*), coalesce(round(greatest(0, extract(epoch FROM now() - min(scheduled_at)))::numeric / 60, 1), 0)
            FROM :"schema".oban_jobs
            WHERE state IN ('available', 'scheduled', 'retryable') AND scheduled_at <= now();
            SQL
                  ;;
                pg_boss) cat <<'SQL'
            SELECT count(*), coalesce(round(greatest(0, extract(epoch FROM now() - min(start_after)))::numeric / 60, 1), 0)
            FROM :"schema".job
            WHERE state IN ('created', 'retry') AND start_after <= now();
            SQL
                  ;;
              esac
            }
            result=$(queue_sql | psql -X -At -F ' ' -v ON_ERROR_STOP=1 -d "$DATABASE_NAME" -v schema="$SCHEMA" 2>&1) || {
              echo "$QUEUE_NAME: cannot count the jobs: $result"
              exit 1
            }
            read -r pending oldest_minutes <<< "$result"
            above() { awk -v value="$1" -v limit="$2" 'BEGIN { exit !(value + 0 > limit + 0) }'; }
            if above "$pending" "$MAX_PENDING_JOBS" || above "$oldest_minutes" "$MAX_OLDEST_JOB_AGE_MINUTES"; then
              echo "$QUEUE_NAME: $pending pending jobs (limit $MAX_PENDING_JOBS), oldest $oldest_minutes minutes (limit $MAX_OLDEST_JOB_AGE_MINUTES)"
              exit 1
            fi
            echo "$QUEUE_NAME: $pending pending jobs, oldest $oldest_minutes minutes"
          run_as_user_account: postgres
          env:
            PGHOST: /var/run/postgresql
            PGPORT: "5432"
            PGCONNECT_TIMEOUT: "5"
            PGOPTIONS: "-c statement_timeout=10s -c TimeZone=UTC"
            QUEUE_NAME: {{ $queue.name | toJson }}
            DATABASE_NAME: {{ toString $queue.database_name | toJson }}
            ADAPTER: {{ toString $queue.adapter | toJson }}
            SCHEMA: {{ toString $schema | toJson }}
            MAX_PENDING_JOBS: {{ toString $queue.max_pending_jobs | toJson }}
            MAX_OLDEST_JOB_AGE_MINUTES: {{ toString $queue.max_oldest_job_age_minutes | toJson }}
        alert_severity: warn
        no_alerts_or_recovery_actions_while_these_checks_fail: [postgres/postgres_answers]
{{- end }}
```

**3. Register the check file.**

On the **Stack**, in `inventories/servers.yml`, add the file at the end of
the `database_servers` group's list. The checks then run on every database
server, and count on the primary:

```yaml
  database_servers:
    nodes: [db01]
    vars:
      is_database_server: true
      mmwatchdog_check_files: [every_server.yml, database_servers.yml, custom_background_job_queue.yml]
```

On **Solo**, in `mmx_project_settings.yml`, add the file at the end of
`mmwatchdog_check_files`. The checks then run on `solo01`:

```yaml
  mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_background_job_queue.yml]
```

**4. Record the recipe.** Save this recipe as
`custom_recipes/background-job-queue.md`, with `source_url`,
`source_commit`, and `applied_on` at the top. Then add this entry to
`custom_extensions:` in `monkeymaxxing_stack_checklist.yml` (Stack) or
`monkeymaxxing_solo_checklist.yml` (Solo), with the result of the
verification check below:

```yaml
custom_extensions:
  - id: background-job-queue
    title: Watch Postgres background job queues
    recipe: watchdog-checks/background-job-queue.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/watchdog-checks/background-job-queue.md
    source_commit: "<SHA>"
    applied_on: "2026-11-23"
    state: done
    verification: "mmwatchdog check-now custom_background_job_queue exited 0 on db01: shop_jobs: 3 pending jobs, oldest 0.2 minutes"
```

Replace `<SHA>` with the full commit you read, use the UTC date of the
applying commit, and write `solo01` instead of `db01` on Solo.

**5. Validate and apply.** Run `mmx validate every_server` on the Stack, or
`mmx validate solo_server` on Solo. Then follow the system's normal change
steps in `AGENTS.md`: commit, publish, preview with `dryrun`, and run
`every_server` (Stack) or `solo_server` (Solo). MMX renders the file into a
candidate directory, has `mmwatchdog validate` check it, and only then
installs it into `/etc/mmwatchdog/check_groups/`.

## Verification check

Run these on the primary database server (Stack) or on `solo01` (Solo):

```sh
sudo mmwatchdog check-now custom_background_job_queue --count-as-scheduled-run --json
echo $?
sudo mmwatchdog status custom_background_job_queue --json
```

`check-now` must exit with status 0, and each queue's check must be `ok`. Its
`stdout` shows the queue's numbers, such as:

```text
shop_jobs: 3 pending jobs, oldest 0.2 minutes
```

On a Stack replica, the same command passes with
`standby replica; skipped: the primary runs this check`. `status` must show
every check of the group healthy.

A wrong `adapter`, `schema`, or `database_name`, or a queue whose migrations
have not run, fails at once with a line such as:

```text
shop_jobs: the table public.good_jobs does not exist in the database shop.
Check adapter (good_job), database_name, and schema in custom.background_job_queue, and that the app's queue migrations ran.
```

To see the warning work, on a test system only: stop the app's job
container (`sudo systemctl stop shop-jobs.service`), have the app queue a job,
such as by signing up a test user, and run `check-now` again. With
`max_pending_jobs: 0`, it fails with a line such as
`shop_jobs: 1 pending jobs (limit 0), oldest 0.4 minutes (limit 15)`. Start
the container again (`sudo systemctl start shop-jobs.service`), put the limit
back, and apply.

## Clean removal

Take these steps in one commit, so the system is the same as before:

1. Remove `custom_background_job_queue.yml` from `mmwatchdog_check_files`, and
   keep the other entries: in the `database_servers` group of
   `inventories/servers.yml` (Stack), or in `mmx_project_settings.yml` (Solo).
2. Delete `mmwatchdog_checks/custom_background_job_queue.yml` and
   `custom_recipes/background-job-queue.md`.
3. Remove only the `background_job_queue:` key from `custom:` in
   `mmx_project_settings.yml`. Leave every other custom setting in place.
   Leave `custom: {}` only when no other custom settings remain.
4. Remove the `background-job-queue` entry from `custom_extensions:` in the
   checklist file.
5. Run `mmx validate`, then apply the commit with `every_server` (Stack) or
   `solo_server` (Solo).

The run deletes `custom_background_job_queue.yml` from both the candidate
directory and the live `/etc/mmwatchdog/check_groups/`, because the file is no
longer in `mmwatchdog_check_files`. MMWatchdog then stops the checks. The
recipe changed no table, kept no data, opened no port, and added no secret, so
nothing else needs undoing.
