---
id: postgres-bloat-and-slow-queries
title: Watch Postgres for table bloat and slow queries
category: watchdog-checks
applies_to: [stack, solo]
summary: Adds MMWatchdog checks that warn when the apps' tables collect too many dead rows and when an app query is slow on average.
author: monkeymaxxing
vetted_on: 2026-11-23
vetted_against:
  stack: v0.3.1
  solo: v0.1.0
vetted_method: live-checkpoint
---

# Watch Postgres for table bloat and slow queries

> [!IMPORTANT]
> Reviewed once when added. Recipes are not re-tested on every Stack or Solo release and are outside core support.

This recipe adds one MMWatchdog check file with two checks on the database
server. The first check warns when a table in an app's database holds too
many dead rows, which is how table bloat starts. The second check warns when
an app query that runs often takes too long on average.

## When to use this (and when you don't need it)

The core already watches Postgres: it checks that Postgres answers, that
connections and transaction IDs stay below their limits, and that backups and
archiving work. It does not look inside the apps' tables or at the apps'
queries. Two slow problems can grow there without any core alert:

- **Dead rows.** When a row is updated or deleted, Postgres keeps the old
  version as a "dead row" until vacuum clears it. Autovacuum, Postgres's own
  background cleaner, normally keeps up. When it is blocked, such as by a
  transaction that stays open for hours, dead rows pile up. The table then
  grows on disk, scans get slower, and the space is not given back to the
  operating system later.
- **Slow queries.** A query that took 20 ms when the table was small can take
  2 seconds a year later, because an index is missing. Users feel it before
  anyone sees it in a graph.

Use this recipe when your apps have tables that grow and change every day,
and you want a daytime warning before those problems reach users.

You don't need it while your database is small and young: tables under
10 MB, a handful of users, and queries you just wrote. You also don't need it
if you already watch dead rows and query times in an outside tool.

What it does not do:

- The dead-row check counts dead rows that wait for vacuum, from Postgres's
  own statistics (`pg_stat_user_tables`). It does not measure the free space
  that stays inside a table file after vacuum. That needs an extra extension,
  such as `pgstattuple`, and a full scan of each table.
- The slow-query check reads the average time of each query since its
  statistics were last reset. A query that was slow last month and is fast
  now keeps a high average until enough fast calls pull it down, or until you
  reset its statistics. The verification and removal sections show how.

## What it adds and what it costs

It costs $0. It adds no server, no package, and no container.

It adds:

- One file, `mmwatchdog_checks/custom_postgres_bloat_and_slow_queries.yml`,
  with one check group, `custom_postgres_bloat_and_slow_queries`, and two
  checks: `tables_have_acceptable_dead_tuples` and
  `no_slow_queries_above_limit`.
- One entry, `custom_postgres_bloat_and_slow_queries.yml`, in
  `mmwatchdog_check_files`: in the `database_servers` group of
  `inventories/servers.yml` on the Stack, and in `mmx_project_settings.yml` on
  Solo (the checks run on `solo01`).
- Settings under `custom.postgres_bloat_and_slow_queries:` in
  `mmx_project_settings.yml`.
- The Postgres extension `pg_stat_statements`, which records the time of each
  query. On the Stack it is already there: pg_auto_failover loads it on every
  database server and creates it when it creates the cluster. On Solo the
  recipe adds one fleet stage that loads it, restarts Postgres once, and
  creates the extension.

Costs to know:

- **One Postgres restart on Solo.** Loading `pg_stat_statements` takes a
  restart. The apps lose their database connections for a few seconds and
  reconnect by themselves. Apply it in a quiet hour. The Stack needs no
  restart.
- **A little memory and CPU.** `pg_stat_statements` keeps up to 5,000 query
  shapes in shared memory, a few megabytes, and adds a small cost to each
  query. Most teams cannot measure the difference. The checks themselves read
  Postgres's statistics views and run in well under a second.
- **Ongoing work.** A warning asks for a person: find what blocks vacuum, or
  add an index to a slow query. Tune the limits after the first weeks, so the
  check warns about real problems only.

## Data, security, and backups

The recipe is stateless. It stores no data of its own. MMWatchdog keeps its
normal check readings.

- **Query statistics.** `pg_stat_statements` keeps its numbers in Postgres's
  memory and saves them to a file inside the data directory at a clean
  shutdown. They are performance numbers, not app data, so they need no
  backup. After a restore they start empty. The extension object in the
  `postgres` database is part of the normal backups.
- **What leaves the server.** The slow-query check prints up to 5 query texts,
  cut to 120 characters, into its output. MMWatchdog keeps that output as
  evidence and sends it with a warning. `pg_stat_statements` replaces the
  values in a normal query with placeholders such as `$1`, so the output shows
  table and column names, not customer data. The check only prints queries
  that ran at least `slow_query_min_calls` times in an app's database.
- **Statements that keep their values.** By default `pg_stat_statements`
  also records commands such as `ALTER ROLE`, with their text as written. On
  Solo, the recipe turns that off with `pg_stat_statements.track_utility =
  off`, so a password in such a command is never stored. On the Stack,
  pg_auto_failover's own setting stays; only Postgres superusers can read
  those texts there.
- **Login.** Both checks run as the operating system account `postgres` and
  connect through the local socket `/var/run/postgresql`. They need no
  password and add no account. They only read: `PGOPTIONS` sets a
  `statement_timeout` of 20 seconds, so a check never runs for long.
- **Network:** none. The recipe opens no port and adds no firewall rule and no
  WireGuard connection.
- **Replicas on the Stack.** The dead-row check skips a standby replica,
  because only the primary counts dead rows, and passes there with "standby
  replica; skipped". After a failover, the new primary's check takes over by
  itself. The slow-query check runs on every database server, and each
  server reports the queries that ran on it. A replica that serves reads
  (`operating_procedures/send_reads_to_replicas.md`) reports its slow reads.
- **Check group name:** `custom_postgres_bloat_and_slow_queries`. It uses
  underscores only and matches `^[a-z0-9_]+$`, so on the Stack the triage
  agent can run `sudo mmwatchdog check-now custom_postgres_bloat_and_slow_queries`.
- **Alerts:** both checks have `alert_severity: warn`. A warn tells a person
  during the day and wakes nobody. Dead rows and slow queries get worse over
  days. Neither is a reason to wake someone. While the core check
  `postgres/postgres_answers` fails, these checks send no alert of their own.

## Apply steps

**On the Stack**, this recipe changes no core file in the normal case:
`pg_stat_statements` is already loaded. Step 2 checks that. If step 2 finds
it missing, the fix changes `roles/database_server/main.yml`, a core file,
and restarts Postgres. The coding agent then stops and asks the person
before going on.

**On Solo**, the recipe adds one custom fleet stage, which writes
`/etc/postgresql/17/main/conf.d/20-custom-pg-stat-statements.conf` and
restarts `postgresql@17-main` once. It edits no core file. The coding agent
tells the person about the short restart before running it.

The recipe touches no vault key, `sudoers`, `ssh/`, or file that the Stack's
desk review watches.

The coding agent adapts these values to the team's system:

- The four limits under `custom.postgres_bloat_and_slow_queries`, if the team
  wants others.
- `check_slow_queries: false`, for a team that does not want the slow-query
  check. Solo then needs no fleet stage and no restart: skip the Solo part of
  step 2.

**1. Add the settings** under `custom:` in `mmx_project_settings.yml`. On both
the Stack and Solo, `custom:` is inside the `# --- Custom extensions ---`
lines. When `custom:` is still `custom: {}`, replace that line with the block
below. When it already has other keys, add only the
`postgres_bloat_and_slow_queries:` key and keep the rest:

```yaml
  custom:
    postgres_bloat_and_slow_queries:
      # Tables smaller than this are skipped. Reason for 10: in a small
      # table a few dead rows are a large share, and vacuum clears them in
      # seconds anyway.
      min_table_size_megabytes: 10
      # The share of dead rows among a table's live and dead rows above
      # which the check fails. Reason for 20: autovacuum starts on a table
      # once its dead rows pass about a fifth of its live rows
      # (autovacuum_vacuum_scale_factor 0.2). A table at 20% dead rows is
      # already past that point. If it stays there for 2 hours, vacuum is
      # blocked or cannot keep up.
      max_dead_tuple_percent: 20
      # false leaves out the slow-query check.
      check_slow_queries: true
      # Queries that ran fewer times are skipped. Reason for 50: a one-off
      # report or a migration is slow on purpose and does not repeat.
      slow_query_min_calls: 50
      # The average time above which a query fails the check. Reason for
      # 500: a query that takes half a second on average makes every page
      # that uses it feel slow.
      slow_query_max_mean_milliseconds: 500
```

The dead-row check looks at every app in `apps:` and reads the database named
by its `database_name`. A new app is watched from the next run, with no change
here.

**2. Load `pg_stat_statements`.**

On the **Stack**, check each database server. As the account `postgres`, run:

```sh
psql -X -At -h /var/run/postgresql -d postgres -c 'SHOW shared_preload_libraries'
psql -X -At -h /var/run/postgresql -d postgres -c "SELECT extversion FROM pg_extension WHERE extname = 'pg_stat_statements'"
```

The first command must print a list that holds `pg_stat_statements`. The
second must print a version, such as `1.11`.

- When the version line is empty, run this once on the primary. The replicas
  receive the extension by replication:

  ```sh
  psql -X -h /var/run/postgresql -d postgres -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements'
  ```

- When `pg_stat_statements` is missing from `shared_preload_libraries`, stop
  and ask the person. The fix adds `shared_preload_libraries:
  pg_stat_statements` to `postgresql_settings:` in
  `roles/database_server/main.yml`, records that core edit under
  `## Custom extensions` in `AGENTS.md`, and restarts each server with
  `operating_procedures/update_and_restart_the_database_servers.md`. Do not
  add `pgautofailover` to the list. That library belongs to the failover
  monitor on `util01`, not to the database servers.

On **Solo**, add this stage between the `# --- Custom extensions ---` lines of
`playbooks/solo_server.yml`, above the block's last "Keep these three boundary
comment lines" line:

```yaml
  # From the recipe postgres-bloat-and-slow-queries
  # (custom_recipes/postgres-bloat-and-slow-queries.md). Loads
  # pg_stat_statements, which records the time of each query, for the check
  # custom_postgres_bloat_and_slow_queries. The file is the only change to
  # Postgres's settings; a change to it restarts Postgres once.
  - id: custom_pg_stat_statements
    nodes: solo_server
    on_node_failure: stop_run
    node_tasks:
      - task_block:
          id: custom_load_pg_stat_statements
          changes:
            - id: write_the_pg_stat_statements_settings
              file:
                path: "/etc/postgresql/{{ .vars.postgresql_major_version }}/main/conf.d/20-custom-pg-stat-statements.conf"
                content: |
                  # Managed by MMX from playbooks/solo_server.yml (recipe postgres-bloat-and-slow-queries).
                  shared_preload_libraries = 'pg_stat_statements'
                  # Commands such as ALTER ROLE keep their text as written,
                  # password included, so pg_stat_statements does not record them.
                  pg_stat_statements.track_utility = off
                owner: postgres
                group: postgres
                permissions_mode: "0644"
          activate:
            - id: restart_postgres_to_load_pg_stat_statements
              systemd_service:
                name: "postgresql@{{ .vars.postgresql_major_version }}-main"
                state: running
                refresh: restart
          verify:
            - id: wait_until_postgres_accepts_connections_again
              wait_for:
                command_succeeds: '"/usr/lib/postgresql/$POSTGRESQL_MAJOR_VERSION/bin/pg_isready" --quiet --port 5432'
                env:
                  POSTGRESQL_MAJOR_VERSION: "{{ .vars.postgresql_major_version }}"
                wait_at_most: 60s
      # One extension in the database postgres covers every database:
      # pg_stat_statements records the queries of all of them.
      - id: create_the_pg_stat_statements_extension
        shell:
          script: psql -X -v ON_ERROR_STOP=1 -d postgres -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements'
          run_as_user_account: postgres
          skip_if_this_command_succeeds: psql -X -At -d postgres -c "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'" | grep -x 1 > /dev/null
```

The core's own file, `10-monkeymaxxing-solo.conf`, does not set
`shared_preload_libraries`, so the two files do not conflict.

**3. Create `mmwatchdog_checks/custom_postgres_bloat_and_slow_queries.yml`.**
MMX renders this template on each server into
`/etc/mmwatchdog/check_groups/custom_postgres_bloat_and_slow_queries.yml`.
The scripts get every value through `env`, and the SQL is in quoted
heredocs, so no value is pasted into the SQL or the shell.

```yaml
{{- /*
  MMWatchdog's check group for dead rows in the apps' tables and for slow
  queries, from the recipe postgres-bloat-and-slow-queries
  (custom_recipes/postgres-bloat-and-slow-queries.md). This file is an MMX
  template. It reads the role inputs apps and custom.
*/ -}}
{{- if not (hasKey .inputs.custom "postgres_bloat_and_slow_queries") }}{{ fail "custom.postgres_bloat_and_slow_queries is missing from mmx_project_settings.yml. Add it, or remove custom_postgres_bloat_and_slow_queries.yml from mmwatchdog_check_files." }}{{ end }}
{{- $settings := .inputs.custom.postgres_bloat_and_slow_queries }}
{{- $database_names := "" }}
{{- range $app_name, $app := .inputs.apps }}{{ $database_names = printf "%s %s" $database_names $app.database_name }}{{ end }}
{{- $database_names = trim $database_names }}
# Managed by MMX from mmwatchdog_checks/custom_postgres_bloat_and_slow_queries.yml in the systems repository.
# This check file comes from the recipe postgres-bloat-and-slow-queries.
# To be woken for a check, set that check's alert_severity to sos.
check_groups:
  # check_every 15m: dead rows and query times change over hours.
  # time_limit_per_run 30s: each query reads statistics views only, and
  # PGOPTIONS stops any statement after 20 seconds.
  # alert_after_failing_for 2h: autovacuum gets two hours to catch up after
  # a big batch of updates or deletes, so a busy afternoon sends nothing.
  # recovered_after_healthy_for 0s: the first healthy run closes the alert.
  # Reason for warn: nothing is down. Both problems grow over days.
  custom_postgres_bloat_and_slow_queries:
    check_every: 15m
    time_limit_per_run: 30s
    alert_after_failing_for: 2h
    recovered_after_healthy_for: 0s
    checks:
      # What to do: find what keeps vacuum from clearing the table, such as a
      # transaction that stays open (pg_stat_activity, state
      # "idle in transaction"), or a long query on a replica, which
      # hot_standby_feedback lets hold back vacuum on the primary. Then
      # run VACUUM (VERBOSE) on the table.
      tables_have_acceptable_dead_tuples:
        shell:
          script: |
            set -u
            dead_rows_report() {
              psql -X -At -v ON_ERROR_STOP=1 -d "$1" \
                -v min_megabytes="$MIN_TABLE_SIZE_MEGABYTES" \
                -v max_percent="$MAX_DEAD_TUPLE_PERCENT" <<'SQL'
            SELECT format('%s: table %I.%I has %s%% dead rows (%s dead, %s live), %s MB, last vacuum %s',
                          current_database(), schemaname, relname,
                          round(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 1),
                          n_dead_tup, n_live_tup,
                          round(pg_relation_size(relid) / 1048576.0, 1),
                          coalesce(to_char(greatest(last_vacuum, last_autovacuum) AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI "UTC"'), 'never'))
            FROM pg_stat_user_tables
            WHERE pg_relation_size(relid) >= :'min_megabytes'::numeric * 1048576
              AND 100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0) > :'max_percent'::numeric
            ORDER BY n_dead_tup DESC;
            SQL
            }
            in_recovery=$(psql -X -At -d postgres -c 'SELECT pg_is_in_recovery()') || {
              echo "cannot ask Postgres whether this server is a standby replica"
              exit 1
            }
            if [ "$in_recovery" = t ]; then
              echo "standby replica; skipped: the primary counts the dead rows"
              exit 0
            fi
            problems=""
            for database in $DATABASE_NAMES; do
              if ! report=$(dead_rows_report "$database" 2>&1); then
                problems+="$database: cannot read the table statistics: $report"$'\n'
                continue
              fi
              if [ -n "$report" ]; then
                problems+="$report"$'\n'
              fi
            done
            if [ -n "$problems" ]; then
              printf '%s' "$problems"
              echo "limit: at most ${MAX_DEAD_TUPLE_PERCENT}% dead rows in a table of ${MIN_TABLE_SIZE_MEGABYTES} MB or more"
              exit 1
            fi
            echo "no table of ${MIN_TABLE_SIZE_MEGABYTES} MB or more has over ${MAX_DEAD_TUPLE_PERCENT}% dead rows in: $DATABASE_NAMES"
          run_as_user_account: postgres
          env:
            PGHOST: /var/run/postgresql
            PGPORT: "5432"
            PGCONNECT_TIMEOUT: "5"
            PGOPTIONS: "-c statement_timeout=20s"
            DATABASE_NAMES: {{ $database_names | toJson }}
            MIN_TABLE_SIZE_MEGABYTES: {{ $settings.min_table_size_megabytes | toString | toJson }}
            MAX_DEAD_TUPLE_PERCENT: {{ $settings.max_dead_tuple_percent | toString | toJson }}
        alert_severity: warn
        no_alerts_or_recovery_actions_while_these_checks_fail: [postgres/postgres_answers]
{{- if $settings.check_slow_queries }}
      # What to do: run EXPLAIN (ANALYZE, BUFFERS) on the query in the app's
      # database, and add the missing index or rewrite the query. After the
      # fix, reset that query's average on each server that reported it:
      #   SELECT pg_stat_statements_reset(0, 0, <queryid>);
      no_slow_queries_above_limit:
        shell:
          script: |
            set -u
            state=$(psql -X -At -F ' ' -v ON_ERROR_STOP=1 -d postgres <<'SQL'
            SELECT (SELECT count(*) FROM pg_extension WHERE extname = 'pg_stat_statements'),
                   current_setting('shared_preload_libraries') ~ '(^|[ ,])pg_stat_statements($|[ ,])';
            SQL
            ) || {
              echo "cannot ask Postgres about pg_stat_statements"
              exit 1
            }
            read -r installed loaded <<< "$state"
            if [ "$loaded" != t ]; then
              echo "pg_stat_statements is not in shared_preload_libraries, so Postgres records no query times."
              echo "Load it as the recipe postgres-bloat-and-slow-queries says, or set check_slow_queries: false."
              exit 1
            fi
            if [ "$installed" = 0 ]; then
              echo "the extension pg_stat_statements does not exist in the database postgres."
              echo "Run CREATE EXTENSION IF NOT EXISTS pg_stat_statements; in the database postgres on the primary."
              exit 1
            fi
            # Only the apps' databases count, so pgBackRest's backup calls and
            # MMWatchdog's own checks, which run in the database postgres, never do.
            if ! report=$(psql -X -At -v ON_ERROR_STOP=1 -d postgres \
                -v database_names="$DATABASE_NAMES" \
                -v min_calls="$SLOW_QUERY_MIN_CALLS" \
                -v max_mean_milliseconds="$SLOW_QUERY_MAX_MEAN_MILLISECONDS" 2>&1 <<'SQL'
            WITH slow AS (
              SELECT d.datname, s.queryid, s.calls, s.mean_exec_time, s.query
              FROM pg_stat_statements AS s
              JOIN pg_database AS d ON d.oid = s.dbid
              WHERE d.datname = ANY (string_to_array(:'database_names', ' '))
                AND s.calls >= :'min_calls'::bigint
                AND s.mean_exec_time > :'max_mean_milliseconds'::numeric
                AND s.query !~* '^\s*(vacuum|analyze)\M'
                AND s.query !~* 'pg_stat_statements'
                AND s.query !~* 'pg_backup_(start|stop)'
            )
            SELECT format('slow query %s of %s: database %s, %s calls, mean %s ms, queryid %s: %s',
                          row_number() OVER (ORDER BY mean_exec_time DESC), count(*) OVER (),
                          datname, calls, round(mean_exec_time::numeric, 1), queryid,
                          left(regexp_replace(query, '\s+', ' ', 'g'), 120))
            FROM slow
            ORDER BY mean_exec_time DESC
            LIMIT 5;
            SQL
            ); then
              echo "cannot read pg_stat_statements: $report"
              exit 1
            fi
            if [ -n "$report" ]; then
              printf '%s\n' "$report"
              echo "limit: a mean of at most ${SLOW_QUERY_MAX_MEAN_MILLISECONDS} ms for a query with ${SLOW_QUERY_MIN_CALLS} calls or more"
              exit 1
            fi
            echo "no query with ${SLOW_QUERY_MIN_CALLS} calls or more has a mean above ${SLOW_QUERY_MAX_MEAN_MILLISECONDS} ms in: $DATABASE_NAMES"
          run_as_user_account: postgres
          env:
            PGHOST: /var/run/postgresql
            PGPORT: "5432"
            PGCONNECT_TIMEOUT: "5"
            PGOPTIONS: "-c statement_timeout=20s"
            DATABASE_NAMES: {{ $database_names | toJson }}
            SLOW_QUERY_MIN_CALLS: {{ $settings.slow_query_min_calls | toString | toJson }}
            SLOW_QUERY_MAX_MEAN_MILLISECONDS: {{ $settings.slow_query_max_mean_milliseconds | toString | toJson }}
        alert_severity: warn
        no_alerts_or_recovery_actions_while_these_checks_fail: [postgres/postgres_answers]
{{- end }}
```

**4. Register the check file.**

On the **Stack**, in `inventories/servers.yml`, add the file at the end of
the `database_servers` group's list. The checks then run on every database
server:

```yaml
  database_servers:
    nodes: [db01]
    vars:
      is_database_server: true
      mmwatchdog_check_files: [every_server.yml, database_servers.yml, custom_postgres_bloat_and_slow_queries.yml]
```

On **Solo**, in `mmx_project_settings.yml`, add the file at the end of
`mmwatchdog_check_files`. The checks then run on `solo01`:

```yaml
  mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_postgres_bloat_and_slow_queries.yml]
```

**5. Record the recipe.** Save this recipe as
`custom_recipes/postgres-bloat-and-slow-queries.md`, with `source_url`,
`source_commit`, and `applied_on` at the top. Then add this entry to
`custom_extensions:` in `monkeymaxxing_stack_checklist.yml` (Stack) or
`monkeymaxxing_solo_checklist.yml` (Solo), with the result of the
verification check below:

```yaml
custom_extensions:
  - id: postgres-bloat-and-slow-queries
    title: Watch Postgres for table bloat and slow queries
    recipe: watchdog-checks/postgres-bloat-and-slow-queries.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/watchdog-checks/postgres-bloat-and-slow-queries.md
    source_commit: "<SHA>"
    applied_on: "2026-11-23"
    state: done
    verification: "mmwatchdog check-now custom_postgres_bloat_and_slow_queries exited 0 on db01"
```

Replace `<SHA>` with the full commit you read, use the UTC date of the
applying commit, and write `solo01` instead of `db01` on Solo.

**6. Validate and apply.** Run `mmx validate every_server` on the Stack, or
`mmx validate solo_server` on Solo. Then follow the system's normal change
steps in `AGENTS.md`: commit, publish, preview with `dryrun`, and run
`every_server` (Stack) or `solo_server` (Solo). On Solo, the dryrun shows the
new settings file and the Postgres restart. MMX renders the check file into a
candidate directory, has `mmwatchdog validate` check it, and only then
installs it into `/etc/mmwatchdog/check_groups/`.

## Verification check

Run these on each database server (Stack) or on `solo01` (Solo):

```sh
sudo mmwatchdog check-now custom_postgres_bloat_and_slow_queries --count-as-scheduled-run --json
echo $?
sudo mmwatchdog status custom_postgres_bloat_and_slow_queries --json
```

`check-now` must exit with status 0, and both checks must be `ok`. The
`stdout` of each check shows what it found:

- `tables_have_acceptable_dead_tuples` on a primary or on Solo:
  `no table of 10 MB or more has over 20% dead rows in: shop`. On a Stack
  replica: `standby replica; skipped: the primary counts the dead rows`.
- `no_slow_queries_above_limit`:
  `no query with 50 calls or more has a mean above 500 ms in: shop`.

`status` must show both checks of the group healthy.

To see the warnings work, on a test system only, set
`max_dead_tuple_percent: 0`, `min_table_size_megabytes: 0`, and
`slow_query_max_mean_milliseconds: 0`, and apply. Any table with a dead row
and any app query with 50 calls then fails, with lines such as:

```text
shop: table public.orders has 3.1% dead rows (412 dead, 12880 live), 4.2 MB, last vacuum 2026-11-23 09:14 UTC
limit: at most 0% dead rows in a table of 0 MB or more
```

```text
slow query 1 of 7: database shop, 812 calls, mean 3.4 ms, queryid -4170133291745913425: SELECT "orders".* FROM "orders" WHERE "orders"."customer_id" = $1
limit: a mean of at most 0 ms for a query with 50 calls or more
```

Then set the values back and apply again.

To start the slow-query averages fresh, such as after fixing several
queries, run `SELECT pg_stat_statements_reset();` in the database `postgres`,
as the account `postgres`, on each server whose statistics you want to clear.

## Clean removal

**1. Remove the checks and settings, in one commit.**

1. Remove `custom_postgres_bloat_and_slow_queries.yml` from
   `mmwatchdog_check_files`, and keep the other entries: in the
   `database_servers` group of `inventories/servers.yml` (Stack), or in
   `mmx_project_settings.yml` (Solo).
2. Delete `mmwatchdog_checks/custom_postgres_bloat_and_slow_queries.yml`.
3. Remove only the `postgres_bloat_and_slow_queries:` key from `custom:` in
   `mmx_project_settings.yml`. Leave `custom: {}` only when no other custom
   settings remain.
4. On **Solo**, swap the `custom_pg_stat_statements` stage for this removal
   stage, in the same place:

   ```yaml
     # Removes the recipe postgres-bloat-and-slow-queries: drops the
     # extension, deletes the settings file, and restarts Postgres once.
     - id: remove_custom_pg_stat_statements
       nodes: solo_server
       on_node_failure: stop_run
       node_tasks:
         - id: drop_the_pg_stat_statements_extension
           shell:
             script: psql -X -v ON_ERROR_STOP=1 -d postgres -c 'DROP EXTENSION IF EXISTS pg_stat_statements'
             run_as_user_account: postgres
             run_only_if_this_command_succeeds: psql -X -At -d postgres -c "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'" | grep -x 1 > /dev/null
         - task_block:
             id: custom_stop_loading_pg_stat_statements
             changes:
               - id: remove_the_pg_stat_statements_settings
                 file:
                   path: "/etc/postgresql/{{ .vars.postgresql_major_version }}/main/conf.d/20-custom-pg-stat-statements.conf"
                   state: absent
             activate:
               - id: restart_postgres_to_unload_pg_stat_statements
                 systemd_service:
                   name: "postgresql@{{ .vars.postgresql_major_version }}-main"
                   state: running
                   refresh: restart
             verify:
               - id: wait_until_postgres_accepts_connections_again
                 wait_for:
                   command_succeeds: '"/usr/lib/postgresql/$POSTGRESQL_MAJOR_VERSION/bin/pg_isready" --quiet --port 5432'
                   env:
                     POSTGRESQL_MAJOR_VERSION: "{{ .vars.postgresql_major_version }}"
                   wait_at_most: 60s
   ```

5. Run `mmx validate`, commit, publish, and run `every_server` (Stack) or
   `solo_server` (Solo). On Solo, warn the person about the short restart
   first.

The run deletes the check file from the candidate directory and from
`/etc/mmwatchdog/check_groups/`, because it is no longer in
`mmwatchdog_check_files`, and MMWatchdog stops the checks. On Solo, check
afterwards, as the account `postgres`:
`psql -X -At -d postgres -c 'SHOW shared_preload_libraries'` prints an empty
line.

**On the Stack, leave `pg_stat_statements` in place.** pg_auto_failover
loaded and created it before this recipe, and the core expects it. If step 2
of the apply steps added `shared_preload_libraries` to
`roles/database_server/main.yml`, remove that line and its note under
`## Custom extensions` in `AGENTS.md` too, and restart the servers with
`operating_procedures/update_and_restart_the_database_servers.md`.

**2. Delete the rest in a second commit.** On Solo, remove the
`remove_custom_pg_stat_statements` stage. On both, delete
`custom_recipes/postgres-bloat-and-slow-queries.md` and remove the
`postgres-bloat-and-slow-queries` entry from `custom_extensions:` in the
checklist file. Run `mmx validate`, commit, and publish. The system is then
the same as before.
