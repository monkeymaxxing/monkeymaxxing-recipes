---
id: redis-cache-pool
title: Add a Redis cache
category: services
applies_to: [stack]
summary: Adds private Redis cache servers that your app reaches over WireGuard, with MMWatchdog checks. Redis keeps no data that needs a backup.
author: monkeymaxxing
vetted_on: 2026-11-21
vetted_against:
  stack: v0.3.0
vetted_method: review-only
---

# Add a Redis cache

> [!IMPORTANT]
> Reviewed once when added. Recipes are not re-tested on every Stack or Solo release and are outside core support.

This recipe adds one new server, `cache001`, that runs Redis as a cache for
your apps. Redis is an in-memory store. Your apps keep copies of data that
is slow to build in it, such as rendered fragments, rate-limit counters, and
the results of costly queries.

## When to use this (and when you don't need it)

**Most small apps do not need this recipe.** The Stack already gives you
two caches:

- **Cloudflare's cache** serves public pages and files from Cloudflare's
  servers, before a request reaches your servers at all.
- **Postgres** is fast for most reads. Its own memory (the shared buffers
  and the operating system's file cache) keeps the rows your app reads most
  often in memory. A plain index or a better query often removes the need
  for a cache.

Add Redis only when you have a **measurement** that says a separate cache
would help. For example:

- The same costly query or page fragment runs thousands of times a minute,
  and Postgres CPU on the database servers is the part that is full.
- The app keeps short-lived counters or locks (rate limits, "send this email
  once") that would otherwise write to Postgres on every request.
- The framework's cache or rate limiter has a Redis option, and the app
  server's local memory is not enough because several app servers must share
  one cache.

**Use Redis for data you can rebuild, never for data you cannot.** This
recipe builds a *cache*: it keeps nothing on disk, and it throws away the
oldest keys when it is full. If your app stores something only in Redis
that cannot be rebuilt from Postgres, such as orders, payments, or the only
copy of a login session, then losing `cache001` loses it for good. Keep
that data in Postgres. A Redis that must keep data is a different design:
it needs locked backups and a restore drill, and this recipe does not
provide them.

## What it adds and what it costs

| Part | What it is |
| --- | --- |
| A new server pool | `cache_servers`, with one server, `cache001`, at `10.20.5.1`, in the address block `10.20.5.0/24` |
| Software | Debian's own `redis-server` package, which Debian's security updates cover. No program from outside the distribution. |
| Network | WireGuard peers between `cache001` and the app servers, and a firewall rule on `cache001` that opens TCP port `6379` to the app servers only, through `connections_between_server_pools` |
| One vault secret | `shop_REDIS_PASSWORD` (named for your app: `<app>_REDIS_PASSWORD`), a random 64-character password that nobody sees |
| A role | `roles/custom_redis_server/main.yml` |
| A fleet stage | `custom_redis_cache_server` in `playbooks/every_server.yml`, inside the `# --- Custom extensions ---` lines |
| Three edits outside the extension block | One `shop_REDIS_PASSWORD` line in each `app_secrets:` of `playbooks/every_server.yml` (the `jobs_server`, `app_server`, and `app_server_on_staging01` stages), so the secret reaches the apps. Step 3 explains why. |
| One setting | `custom.redis_cache.max_memory_megabytes` in `mmx_project_settings.yml` |
| An MMWatchdog check file | `mmwatchdog_checks/custom_redis.yml`, with the check groups `custom_redis_cache` and `custom_redis_cache_capacity` |
| Records | `custom_recipes/redis-cache-pool.md` and an entry under `custom_extensions:` in `monkeymaxxing_stack_checklist.yml` |

**Cost:** about €6 a month for one small server (a Hetzner Cloud `cx23` or a
similar size). Check your provider's current price before you add it: the
pool has no entry in `growth_limits`, so the coding agent must ask you, with
the price, before it creates the server.

**Ongoing work:**

- Debian security updates install by themselves. A new kernel needs a reboot,
  which `reboot_servers_after_updates` does in your weekly maintenance
  window. Because `cache001` is the only server of its pool, it reboots only
  inside that window. A reboot empties the cache, so for a few minutes the
  apps read from Postgres again. To reboot it outside the window, add
  `--var reboot_the_only_server_of_a_pool_outside_the_maintenance_window=true`
  to `./server_management_scripts/run_mmx_on_util01 run reboot_servers_after_updates`.
- A Debian security update to `redis-server` restarts Redis, and a restart
  empties the cache, the same as a reboot does. Expect a short rise in
  Postgres reads when it happens.
- The first `every_server` run after you add the new env settings and the
  secret restarts the app containers on each app server (and jobs server),
  one server at a time, as any change to an app's settings does.
- The cache's size is a setting you choose. If the apps' hit rate is low
  because the cache is too small, raise `max_memory_megabytes` and run
  `every_server`. A cache that is too big for its server fails the
  `memory_is_below_75_percent` check, so keep the setting below about half of
  the server's memory.
- MMWatchdog's `redis` check reports only that Redis answers. It does not
  report evictions or the hit rate. Read those yourself with
  `redis-cli INFO stats` (`evicted_keys`, `keyspace_hits`, `keyspace_misses`)
  or from the app's own metrics.
- **One server, one cache.** With a second server (`cache002`), each server
  would be a separate cache, and the app would have to choose a server for
  each key. This recipe covers one server. A bigger pool needs changes in the
  app, and it is a different recipe.

## Data, security, and backups

**Stateless.** `cache001` keeps no data that matters, so this recipe has no
backup and no restore drill. The role writes these settings, so a restart or a
lost server loses only cached copies:

- `save ""` turns off snapshots to disk.
- `appendonly no` turns off the append-only log.
- `maxmemory` is `custom.redis_cache.max_memory_megabytes`, and
  `maxmemory-policy allkeys-lru` throws away the least recently used keys
  when the memory is full, so Redis never refuses a write for lack of room.

Losing `cache001` therefore loses zero durable data. Replace it by adding a
new server with [Add a server](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_a_server.md)
(your systems repository has its own copy under `operating_procedures/`).
The triage agent's replacement playbooks replace only app, jobs, and
load-balancer servers, so a person replaces a failed `cache001`.
**Never put a session, a job, an order, or any value that you cannot rebuild
in this cache.** If the app needs that, keep it in Postgres, or write a
different recipe that adds locked backups.

**Network.** Redis listens only on `127.0.0.1` and on `cache001`'s WireGuard
address (`private_ip`, `10.20.5.1`), on port `6379`. It never listens on
`0.0.0.0` or on the public address, and the recipe opens no public port.

| Connection | Where it comes from |
| --- | --- |
| WireGuard peers between `app_servers` and `cache_servers` | One line in `connections_between_server_pools` |
| UFW: TCP `6379` on `cache001`, from every app server | The same line |
| The same for `jobs_servers` | An optional second line, only when the apps' job containers use the cache |
| MMWatchdog on `cache001` to Redis | Inside `cache001`, over `127.0.0.1:6379`, so it needs no rule |

The two pools talk over WireGuard, which already encrypts the traffic, so
Redis itself runs without TLS. The MMWatchdog check says so with
`connection_security: unencrypted`, as MMWatchdog asks for every check.

**Password.** Redis needs a password (`requirepass`). It is one vault key,
`shop_REDIS_PASSWORD`, which the person's `set-up-outside-services secrets`
command makes at random, without showing it to anyone. It reaches three
places and never Git:

- `cache001`'s Redis settings, `/etc/redis/redis.conf` (mode `0600`, owner
  `redis`).
- `/etc/mmwatchdog/secrets/custom_redis` (mode `0600`, owner `root`), which
  MMWatchdog's built-in `redis` check reads as `login_password_file`.
- The app's own secrets file, `/etc/shop/shop.env`, as `REDIS_PASSWORD`,
  which the Stack already writes for every secret in `secrets_from_vault`.

> [!NOTE]
> **Why the vault key is `shop_REDIS_PASSWORD` and not a `custom_` name.**
> The person's command, `set-up-outside-services secrets`, makes only the
> keys that the apps list under `secrets_from_vault`. It refuses a key that
> no app lists, so a key such as `custom_redis_password` would have no way
> into the vault without the coding agent seeing the value. Listing the key
> under the app that uses the cache is the way the Stack supports. The
> cost: one app owns the password. A second app that uses the cache would
> get its own, different random password, so this recipe covers one app.

**MMWatchdog.** One new file, `mmwatchdog_checks/custom_redis.yml`, with two
check groups. Both names use underscores only, so they match `^[a-z0-9_]+$`
and the triage agent may run `mmwatchdog check-now` on them:

- `custom_redis_cache`: `redis-server.service` is active, and Redis answers
  `PING` after logging in with the password (a `warn`: a cache outage slows
  the site down, but the apps read from Postgres meanwhile).
- `custom_redis_cache_capacity`: CPU below 70% and memory below 75%, copied
  from the jobs servers' limits.

**Files that stay as they are.** The recipe touches no vault key but its own,
no `sudoers`, no `ssh/`, and no file that the desk review (`ssh desk01-review`)
watches, so the coding agent has no reason to stop and ask for those. It does
change two things that the team owns, outside the extension block: the app's
entry under `apps:` in `mmx_project_settings.yml`, and three lines in the
`app_secrets:` lists of `playbooks/every_server.yml` (step 3). A later Stack
upgrade merges `every_server.yml` with `--3way`, so those lines survive unless
upstream changes the same lines. Record them under `## Custom extensions` in
your systems repository's `AGENTS.md`.

## Apply steps

Read the [Add a new kind of server pool](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_a_new_kind_of_server_pool.md)
procedure in your systems repository first: this recipe is its six decisions,
written out for Redis. Then follow it, section by section. Each step says
what the coding agent adapts to your system.

**The coding agent adapts these values:** the app's name (`shop` below), the
next free address block (`10.20.5.0/24`, if `10.20.5.x` is taken), the
server's `server_type` and `location` (use the same as the app servers'
`location`), and `max_memory_megabytes`.

### 1. The pool, in `inventories/servers.yml`

Add the address block under `vars.private_ip_ranges`:

```yaml
# inventories/servers.yml, under vars.private_ip_ranges
    cache_servers: 10.20.5.0/24
```

Add the connection under `vars.connections_between_server_pools`. The first
line is always needed. Add the second line only when the app's job
containers use the cache:

```yaml
# inventories/servers.yml, under vars.connections_between_server_pools
    - from_pool: app_servers
      to_pool: cache_servers
      tcp_ports: [6379]
      why: The apps keep cached data in Redis on the cache servers.
    - from_pool: jobs_servers
      to_pool: cache_servers
      tcp_ports: [6379]
      why: The apps' job containers on the jobs servers use the same Redis.
```

Add the flag among the other `is_..._server` flags in the top-level `vars`.
No role reads this flag today. It records what kind of pool this is, for
later playbooks and for the next coding agent, as the pool procedure asks:

```yaml
# inventories/servers.yml, in vars, beside the other is_..._server flags
  is_cache_server: false
```

Add the group at the end of `groups:`, with no server yet:

```yaml
# inventories/servers.yml, under groups
  # The Redis cache, from the redis-cache-pool recipe. cache001 is added with
  # operating_procedures/add_a_server.md after mmx validate passes.
  cache_servers:
    nodes: []
    vars:
      is_cache_server: true
      mmwatchdog_check_files: [every_server.yml, custom_redis.yml]
```

Add the pool's row to the table "Server names and private addresses" in your
systems repository's `AGENTS.md`: `cache001` | `cache_servers` | `10.20.5.N`.

### 2. The setting, in `mmx_project_settings.yml`

Put the setting between the `# --- Custom extensions ---` lines. Replace
`custom: {}` with the first form below. If `custom:` already has other
keys, add only the `redis_cache:` key under it:

```yaml
# mmx_project_settings.yml, between the Custom extensions lines
  custom:
    redis_cache:
      # The most memory Redis may use for cached data. When it is full, Redis
      # throws away the least recently used keys. Reason for 512: room for a
      # small app's hot data on a 4 GB server, and well under the 75%
      # memory check. Raise it when the apps' hit rate is low and the
      # server has memory to spare; keep it below about half of the server's memory.
      max_memory_megabytes: 512
```

### 3. The password, through the app's `secrets_from_vault`

Add the connection settings and the secret to the app's entry under `apps:`
in `mmx_project_settings.yml`. Add each line under the key that already
exists (`env:` and `secrets_from_vault:`):

```yaml
# mmx_project_settings.yml, in apps.shop.env
        REDIS_HOST: 10.20.5.1
        REDIS_PORT: "6379"
```

```yaml
# mmx_project_settings.yml, in apps.shop.secrets_from_vault
        REDIS_PASSWORD:
          where_the_value_comes_from: generated_by_the_setup
```

The Stack writes `REDIS_HOST` and `REDIS_PORT` to the app's plain settings
file, and `REDIS_PASSWORD` to its secrets file, on every server that runs the
app. The app builds its Redis connection from these three values. The
password is only letters and digits, so it needs no URL escaping if the app
joins them into a `redis://:PASSWORD@10.20.5.1:6379/0` address.

**Staging.** `staging01`, if the team has it, has no connection to `cache001`
in this recipe, so it must never try production's `10.20.5.1`. The app's
`env:` applies to staging too, unless `staging_env:` replaces a name. Replace
both names with empty values, under the app's existing `staging_env:` key:

```yaml
# mmx_project_settings.yml, in apps.shop.staging_env
        REDIS_HOST: ""
        REDIS_PORT: ""
```

The app must then treat an empty `REDIS_HOST` as "no cache". If staging needs
a real cache, the person decides to add a small cache server for it. Ask the
person.

**Pass the secret to the servers.** The Stack gives each server only the
secrets that `app_secrets:` names in `playbooks/every_server.yml`. Without a
line there, `REDIS_PASSWORD` never reaches `/etc/shop/shop.env`. Add one line
to each of the three `app_secrets:` lists, in the stages `jobs_server`,
`app_server`, and `app_server_on_staging01`, beside the app's other secrets.
Staging reads its own key, whose value the app ignores because `REDIS_HOST`
is empty there:

```yaml
# playbooks/every_server.yml, in the app_secrets of jobs_server and app_server
            shop_REDIS_PASSWORD: "{{ .secrets.shop_REDIS_PASSWORD }}"
```

```yaml
# playbooks/every_server.yml, in the app_secrets of app_server_on_staging01
            shop_REDIS_PASSWORD: "{{ .secrets.staging_shop_REDIS_PASSWORD }}"
```

These three lines are outside the `# --- Custom extensions ---` lines. Keep
them in the same place as the app's other `shop_...` secrets.

Commit and push. Then the person makes the password on the laptop:

```sh
ssh desk01-secrets
```

The command makes `shop_REDIS_PASSWORD` at random and pushes the vault. The
coding agent never opens it. If the team has staging01, the command also
makes `staging_shop_REDIS_PASSWORD`, which staging's `app_secrets` line reads.

**Check:** the key exists. On the laptop, run
`ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
and read that `shop_REDIS_PASSWORD` is listed and not `not defined`.

### 4. The role, `roles/custom_redis_server/main.yml`

```yaml
# roles/custom_redis_server/main.yml
# Redis as a stateless cache on the cache servers, from the redis-cache-pool
# recipe. Redis comes from Debian's redis-server package, so Debian's security
# updates cover it. MMX keeps the package from starting Redis while it
# installs, so Redis first starts below, with these settings.
#
# Redis listens only on 127.0.0.1 and on the server's WireGuard address, never
# on 0.0.0.0. The apps reach it over WireGuard at private_ip:6379 (the firewall
# line comes from connections_between_server_pools). MMWatchdog on this server
# checks 127.0.0.1:6379.
#
# Redis keeps nothing on disk: no snapshots (save ""), no append-only log
# (appendonly no). When the memory is full, the least recently used keys go
# (allkeys-lru). Losing this server loses only cached copies.
inputs:
  private_ip:                               # vars.private_ip: this server's WireGuard address
    type: string
    required: true
  max_memory_megabytes:                     # vars.custom.redis_cache.max_memory_megabytes
    type: integer
    required: true
  redis_password:                           # the vault key <app>_REDIS_PASSWORD
    type: string
    required: true
    secret: true

node_tasks:
  - id: install_redis
    apt_package:
      packages:
        - {name: redis-server, version: newest_when_first_installed}

  # MMWatchdog's check reads the password from this file. The directories and
  # modes are the same as the ones mmwatchdog_joined_node sets, so the two
  # roles never disagree. This role runs first, so the file is already there
  # when the new server joins the fleet hub.
  - id: create_the_mmwatchdog_configuration_directory
    directory:
      path: /etc/mmwatchdog
      owner: root
      group: root
      permissions_mode: "0755"
  - id: create_the_mmwatchdog_secrets_directory
    directory:
      path: /etc/mmwatchdog/secrets
      owner: root
      group: root
      permissions_mode: "0700"
  - id: write_the_password_for_the_mmwatchdog_redis_check
    file:
      path: /etc/mmwatchdog/secrets/custom_redis
      content: "{{ .inputs.redis_password }}\n"
      owner: root
      group: root
      permissions_mode: "0600"

  - task_block:
      id: redis
      changes:
        - id: write_the_redis_settings
          file:
            path: /etc/redis/redis.conf
            # The file holds the password, so only its owner, the redis account that runs Redis, reads it.
            owner: redis
            group: redis
            permissions_mode: "0600"
            content: |
              # Managed by MMX from roles/custom_redis_server/main.yml in the systems repository.
              # Only the loopback address and the WireGuard address: never 0.0.0.0.
              bind 127.0.0.1 {{ .inputs.private_ip }}
              port 6379
              protected-mode yes
              requirepass "{{ .inputs.redis_password }}"
              # A cache keeps nothing on disk.
              save ""
              appendonly no
              maxmemory {{ .inputs.max_memory_megabytes }}mb
              maxmemory-policy allkeys-lru
              dir /var/lib/redis
              pidfile /run/redis/redis-server.pid
              # Standard output goes to the systemd journal.
              logfile ""
              loglevel notice
        - id: settings_of_the_redis_unit
          systemd_unit:
            name: redis-server.service
            drop_in: 10-monkeymaxxing-recipes.conf
            content: |
              # Managed by MMX from roles/custom_redis_server/main.yml in the systems repository.
              [Unit]
              # Redis listens on this server's WireGuard address, which wg0 holds.
              After=wg-quick@wg0.service
              Wants=wg-quick@wg0.service
      activate:
        - id: run_redis
          systemd_service:
            name: redis-server
            state: running
            start_at_boot: true
            refresh: restart
      verify:
        - id: wait_until_redis_accepts_connections_on_the_wireguard_address
          wait_for:
            tcp_port_accepts_connections: 6379
            tcp_host: "{{ .inputs.private_ip }}"
            wait_at_most: 30s
```

### 5. The fleet stage, in `playbooks/every_server.yml`

Put the stage between the `# --- Custom extensions (start) ---` and
`# --- Custom extensions (end) ---` lines, which sit before the stage
`mmwatchdog_joins_the_fleet_hub_after_the_roles`, so the checks find Redis
running and the password file in place. Keep the boundary comments intact.

```yaml
# playbooks/every_server.yml, between the Custom extensions lines
  - id: custom_redis_cache_server
    nodes: cache_servers
    skip_when_no_nodes_are_selected: true     # a system with no cache server yet
    max_nodes_at_once: 1
    on_node_failure: stop_fleet_stage
    node_tasks:
      - role: custom_redis_server
        inputs:
          private_ip: "{{ .vars.private_ip }}"
          max_memory_megabytes: "{{ .vars.custom.redis_cache.max_memory_megabytes }}"
          redis_password: "{{ .secrets.shop_REDIS_PASSWORD }}"
```

### 6. The check file, `mmwatchdog_checks/custom_redis.yml`

```yaml
# mmwatchdog_checks/custom_redis.yml
# Managed by MMX from mmwatchdog_checks/custom_redis.yml in the systems repository.
# The Redis cache on the cache servers, from the redis-cache-pool recipe.
# A cache outage slows the site down but loses no data, because the apps read
# from Postgres meanwhile. So every check here is warn. To be woken for a
# check, set that check's alert_severity to sos. Each value has its reason
# beside it; change a value only with a reason of your own.
check_groups:
  # Group names use underscores only, so triage's mmwatchdog check-now can run them.
  custom_redis_cache:
    check_every: 1m
    time_limit_per_run: 10s
    # 3 minutes ignores a restart in progress, such as a package update.
    alert_after_failing_for: 3m
    recovered_after_healthy_for: 1m
    checks:
      # Reason for warn: systemd restarts Redis after a crash; the warning means it did not stay up.
      redis_server_runs:
        systemd_unit_state:
          systemd_unit: redis-server.service
          fail_when: the_unit_is_not_active
        alert_severity: warn
      # The check logs in with the password, sends PING, and expects PONG.
      # Reason for 127.0.0.1: Redis listens there too, so the check needs no
      # firewall rule. Reason for unencrypted: the connection never leaves the
      # server, and the apps' own connections cross WireGuard, which encrypts.
      redis_answers_ping:
        redis:
          connection_security: unencrypted
          address: 127.0.0.1:6379
          login_password_file: /etc/mmwatchdog/secrets/custom_redis
        alert_severity: warn

  # Each reading covers the 5 minutes since the previous reading. A warning
  # goes out after 15 minutes past a limit.
  custom_redis_cache_capacity:
    check_every: 5m
    time_limit_per_run: 10s
    alert_after_failing_for: 15m
    recovered_after_healthy_for: 5m
    checks:
      # Reason for 70%: the same limit as the jobs servers, so a pool keeps 30% of CPU as headroom.
      cpu_is_below_70_percent:
        node_resource: cpu
        fail_when_measurement_above:
          cpu_used_percent: 70
        alert_severity: warn
      # Reason for 75%: Redis may use up to max_memory_megabytes, and the
      # operating system needs the rest. Above 75% the setting is too big for
      # the server: lower it, or add a bigger server. Reason for warn: the
      # cache slows down, no data is lost.
      memory_is_below_75_percent:
        node_resource: memory
        fail_when_measurement_above:
          memory_used_percent: 75
        alert_severity: warn
```

Disk space is already checked on every server by `every_server.yml`, which
`mmwatchdog_check_files` lists first.

### 7. Add the server, then apply

1. Run `mmx validate`, commit, and push.
   **Check:** `mmx validate` passes.
2. Add `cache001` with `operating_procedures/add_a_server.md`: name
   `cache001`, group `cache_servers`, `private_ip: 10.20.5.1`, and the
   `server_type` and `location` that the provider script's receipt records.
   Ask the person first, with the monthly price.
   **Check:** the checks of `add_a_server.md`. The run applies
   `custom_redis_cache_server` and joins MMWatchdog to the fleet hub.
3. Preview and run `every_server`, as the Stack's "Making a change" says: push,
   `dryrun`, then run.
   **Check:** the dryrun proposes only `cache001`'s changes, the changes
   to the firewall and WireGuard of the app servers (and the jobs servers),
   and the new `REDIS_` settings in the app's settings and secrets files, which
   restart the app containers.
4. Let the app use it. Change the app so that its cache uses Redis through
   `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD`, then deploy it as the
   Stack says. The app must keep working when Redis is empty or down, since
   Redis is only a cache.
   **Check:** the app's cache works with Redis (the app's own check, or the
   hit counters in the verification below).

### 8. The records

Copy this recipe to `custom_recipes/redis-cache-pool.md` in your systems
repository, with `source_url`, `source_commit` (the commit you read), and
`applied_on` (the UTC date of the applying commit) at the top, as the
Stack's "Using a recipe" says. Then add the entry to `custom_extensions:` in
`monkeymaxxing_stack_checklist.yml`:

```yaml
# monkeymaxxing_stack_checklist.yml, in custom_extensions
  - id: redis-cache-pool
    title: Add a Redis cache
    recipe: services/redis-cache-pool.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/services/redis-cache-pool.md
    source_commit: "<SHA>"
    applied_on: "2026-11-21"
    state: done
    verification: "Redis listens only on 127.0.0.1 and 10.20.5.1; MMWatchdog's custom_redis_cache group is healthy."
```

Replace `<SHA>` with the full commit you read, the date with the UTC date of
the applying commit, and the `verification` text with what you measured. Also add one line about the pool under `## Custom extensions` in
your systems repository's `AGENTS.md`, and `cache001` to the README's list of
servers.

## Verification check

Run these on the laptop, after the apply steps. They only read. The laptop
reaches only the systems desk, so each command goes through
`ssh desk01-agent`. It runs in the desk's checkout of your systems repository,
where `ssh -F ssh/config` reaches the servers. The coding agent never reads
the password, so none of these commands shows it.

**1. The firewall and WireGuard on `cache001`:**

```sh
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.5.1 "ufw status verbose; ufw show added; wg show wg0 allowed-ips"'
```

Expect the default `deny (incoming)`. Port `6379/tcp` is allowed from the
app servers' addresses only, such as `10.20.1.1` (and the jobs servers'
addresses, if you added the second line). No rule opens `6379` to
`Anywhere`. `wg show wg0 allowed-ips` lists the app servers, `util01`, and
the systems desks, and no other peer.

**2. Redis listens only where it should:**

```sh
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.5.1 "ss -tlnp | grep 6379"'
```

Expect exactly two lines, `127.0.0.1:6379` and `10.20.5.1:6379`, each from
`redis-server`. The output must have no `0.0.0.0:6379`, no `*:6379`, no
`[::]:6379`, and no public address.

**3. The app server reaches Redis, and Redis refuses a client with no password.**
This sends `PING` without a login, so no secret is used. The line between
the two `EOF` lines runs on the app server. The quotes in `<<'EOF'` stop the
laptop and the desk from changing it:

```sh
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 bash -s' <<'EOF'
timeout 5 bash -c 'exec 3<>/dev/tcp/10.20.5.1/6379 && printf "PING\r\n" >&3 && head -n 1 <&3'
EOF
```

Expect `-NOAUTH Authentication required.` That proves the app server reaches
`cache001` over WireGuard and that Redis asks for the password. Run the same
three lines with `root@10.20.2.1` (`db01`, a server outside the app pool) in
place of `root@10.20.1.1`. There the command must fail (for example with `No
route to host`, or by timing out) and must never print `-NOAUTH`.

**4. The secret reached the app server.** This counts the lines that start
with `REDIS_PASSWORD=` and never prints the value:

```sh
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 "grep -c ^REDIS_PASSWORD= /etc/shop/shop.env"'
```

Expect `1`. A `0` means the `app_secrets` line of step 3 is missing from the
`app_server` stage (or from the `jobs_server` stage, when you run this on a
jobs server).

**5. Redis answers with the password:** MMWatchdog reads the password file
itself, so the check is a login and `PING` that never shows the password:

```sh
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.5.1 "mmwatchdog check-now custom_redis_cache --json && mmwatchdog status custom_redis_cache --json"'
```

Expect both checks, `redis_server_runs` and `redis_answers_ping`, healthy. The
message of `redis_answers_ping` reads `the Redis server at 127.0.0.1:6379
answered PING`. Also run `mmwatchdog status custom_redis_cache_capacity --json`
the same way and expect healthy.

**6. The app uses it.** Run the app's own cache check, or use the app for a
few minutes and then read Redis's counters from the app's metrics. The
coding agent never reads the password, so it runs no `redis-cli` login.
Record in the `verification` field of the checklist entry what you measured.

## Clean removal

Take everything out in this order, so no app points at a Redis that is gone.
Each step is a commit, pushed and applied as the Stack's "Making a change"
says.

1. **Stop the apps from using it.** Remove the app's use of `REDIS_HOST`,
   `REDIS_PORT`, and `REDIS_PASSWORD` in the app's code, and deploy. Remove
   `REDIS_HOST` and `REDIS_PORT` from `apps.shop.env` (and the two empty
   lines from `apps.shop.staging_env`) and `REDIS_PASSWORD` from
   `apps.shop.secrets_from_vault` in `mmx_project_settings.yml`. Remove the
   three `shop_REDIS_PASSWORD` lines from the `app_secrets:` lists of the
   `jobs_server`, `app_server`, and `app_server_on_staging01` stages in
   `playbooks/every_server.yml`, and take the note about them out of
   `AGENTS.md`. Run `every_server`.
   **Check:** the app works, and `/etc/shop/shop.env` has no
   `REDIS_PASSWORD` (the Stack removes it when the key leaves
   `secrets_from_vault`).
2. **Remove `cache001`** with `operating_procedures/remove_a_server.md`
   (`server_name: cache001`), which takes the server out of service,
   out of the inventory, and out of the peers and firewall rules, and then
   destroys it at the provider. The person agrees to the destroy.
   The server's Redis data goes with it. It was only a cache.
3. **In one commit, remove the rest:**
   - the fleet stage `custom_redis_cache_server` from
     `playbooks/every_server.yml` (keep the boundary comments);
   - `roles/custom_redis_server/`;
   - `mmwatchdog_checks/custom_redis.yml`;
   - from `inventories/servers.yml`: the `cache_servers` group, the
     `is_cache_server` flag, the `cache_servers` line in
     `private_ip_ranges`, and the `connections_between_server_pools` lines
     that name `cache_servers` (the run refuses a line for a pool that no
     longer exists);
   - `custom.redis_cache` from `mmx_project_settings.yml` (leave
     `custom: {}` when nothing else is there);
   - the `custom_extensions:` entry in `monkeymaxxing_stack_checklist.yml`,
     `custom_recipes/redis-cache-pool.md`, and the pool's row and note in
     `AGENTS.md` and the README.
4. **Leave the vault key.** `mmx secrets` has no command that deletes a key,
   and the coding agent never opens the vault. Step 1 took `REDIS_PASSWORD`
   out of `secrets_from_vault`, so nothing reads or asks for
   `shop_REDIS_PASSWORD` any more. It stays in `secrets_vault.age` as a random
   password for a server that no longer exists, and `mmx secrets list-keys`
   still lists it. This is the one thing removal leaves behind.
5. **Run `every_server`.**
   **Check:** `mmx validate` passes, and the dryrun of `every_server` proposes no
   change. The firewall rules and WireGuard peers for `cache_servers` are gone
   from the app servers (`ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 "ufw show added; wg show wg0 allowed-ips"'`
   shows no `10.20.5.` address). MMWatchdog on the remaining servers has no
   `custom_redis_cache` group (`mmwatchdog status --json`).
