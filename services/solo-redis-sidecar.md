---
id: solo-redis-sidecar
title: Add a Redis cache sidecar on Solo
category: services
applies_to: [solo]
summary: Runs Redis as a cache in a locked-down container on solo01, on 127.0.0.1 only, with MMWatchdog checks. Redis keeps no data that needs a backup.
author: monkeymaxxing
vetted_on: 2026-11-23
vetted_against:
  solo: v0.1.0
vetted_method: live-checkpoint
---

# Add a Redis cache sidecar on Solo

> [!IMPORTANT]
> Reviewed once when added. Recipes are not re-tested on every Stack or Solo release and are outside core support.

This recipe runs Redis next to your app on `solo01`, in a Podman container
that listens on `127.0.0.1:6379` only. Redis is an in-memory store. Your app
keeps copies of data that is slow to build in it, such as rendered
fragments, rate-limit counters, and the results of costly queries.

## When to use this (and when you don't need it)

**Most small apps do not need this recipe.** Solo already gives you two
caches:

- **Cloudflare's cache** serves public pages and files from Cloudflare's
  servers, before a request reaches `solo01` at all.
- **Postgres** is fast for most reads. Its shared buffers and the operating
  system's file cache keep the rows your app reads most often in memory. A
  plain index or a better query often removes the need for a cache.

Add Redis only when you have a **measurement** that says a separate cache
would help. For example:

- The same costly query or page fragment runs thousands of times a minute,
  and Postgres is the part of `solo01` that is busy.
- The app keeps short-lived counters or locks (rate limits, "send this email
  once") that would otherwise write to Postgres on every request.
- The framework's cache, rate limiter, or Action Cable has a Redis option
  that works better than its Postgres option.

**Use Redis for data you can rebuild, never for data you cannot.** This
recipe builds a *cache*: it keeps nothing on disk, and it throws away the
least recently used keys when it is full. A restart of the container, a
reboot, or a Redis update empties it. If your app keeps something only in
Redis that it cannot rebuild from Postgres, such as orders, payments, a job
queue, or the only copy of a login session, that data is gone after the
next restart. Keep that data in Postgres. A Redis that must keep data needs
locked backups and a restore drill, and this recipe does not provide them.

For a Redis on its own server, shared by several app servers, use the
Stack and its [Add a Redis cache](redis-cache-pool.md) recipe.

## What it adds and what it costs

| Part | What it is |
| --- | --- |
| A container | `custom-redis.container`, a Podman Quadlet file, which systemd runs as `custom-redis.service` on `solo01` |
| Software | The official Redis image, `docker.io/library/redis:7.4-alpine`, pinned by its SHA-256 digest, and the `podman` package, which Solo installs anyway |
| One vault secret | `shop_REDIS_PASSWORD` (named for your app: `<app>_REDIS_PASSWORD`), a random 64-character password that nobody sees |
| A role | `roles/custom_solo_redis/main.yml` and one file, `roles/custom_solo_redis/files/start_redis` |
| A fleet stage | `custom_solo_redis` in `playbooks/solo_server.yml`, inside the `# --- Custom extensions ---` lines |
| Two edits outside the extension block | The app's `env:` and `secrets_from_vault:` in `mmx_project_settings.yml`, and one line in the `app_secrets:` of the `apps_and_tunnel` stage in `playbooks/solo_server.yml`. Step 3 explains why. |
| One setting | `custom.solo_redis` in `mmx_project_settings.yml` |
| An MMWatchdog check file | `mmwatchdog_checks/custom_solo_redis.yml`, with the check group `custom_solo_redis` |
| Records | `custom_recipes/solo-redis-sidecar.md` and an entry under `custom_extensions:` in `monkeymaxxing_solo_checklist.yml` |

**Cost:** $0 a month in new servers. Redis uses up to
`max_memory_megabytes` of `solo01`'s memory (256 MB by default) plus a few
megabytes for itself. Solo's own memory check warns at 75% of the server's
memory, so keep the setting well below what the app and Postgres leave free.
Look with `free -m` before you raise it.

**Ongoing work:**

- **Updates are yours.** The image is pinned, so a Redis security fix does
  not arrive by itself. Watch the Redis 7.4 release notes. To update, put the
  new tag and its digest in `custom.solo_redis.image` and run `solo_server`.
  The run pulls the new image and restarts Redis, which empties the cache.
- **The first run after the change restarts the app's containers**, as any
  change to an app's settings does, because the app gets three new settings.
  On Solo that is a short break of a few seconds.
- MMWatchdog's `redis` check reports only that Redis answers. It does not
  report evictions or the hit rate. Read those yourself with
  `podman exec custom-redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli INFO stats'`
  (`evicted_keys`, `keyspace_hits`, `keyspace_misses`), or from the app's
  own metrics. `REDISCLI_AUTH` keeps the password off `redis-cli`'s command
  line.

## Data, security, and backups

**Stateless.** Redis keeps no data that matters, so this recipe has no
backup and no restore drill. The start script writes these settings, so a
restart loses only cached copies:

- `save ""` turns off snapshots to disk.
- `appendonly no` turns off the append-only log.
- `maxmemory` is `custom.solo_redis.max_memory_megabytes`, and
  `maxmemory-policy allkeys-lru` throws away the least recently used keys
  when the memory is full, so Redis never refuses a write for lack of room.

Solo's backups of Postgres stay as they are. **Never put a session, a job,
an order, or any value that you cannot rebuild in this cache.**

**No open port.** The container uses the server's own network
(`Network=host`), and Redis binds `127.0.0.1` only, so only programs on
`solo01` reach it. The app's containers use the same network, so they reach
it at `127.0.0.1:6379`. The recipe adds no firewall rule and no WireGuard
connection. It never listens on `0.0.0.0`, on the WireGuard address, or on
the public address.

**A locked-down container.** It has the same limits as the app's own
containers:

- `ReadOnly=true` and `ReadOnlyTmpfs=true`: the image's files cannot change,
  and `/tmp`, `/run`, and Redis's working directory are empty memory-backed
  folders.
- `UserNS=auto`: root inside the container is not root on the server.
  `User=redis` runs Redis as the image's own unprivileged account as well.
- `DropCapability=all` and `NoNewPrivileges=true`: no Linux capability and no
  way to gain one.
- `--security-opt=apparmor=solo-app-containers`: Solo's own AppArmor profile
  for app containers.

**Password.** Redis needs a password (`requirepass`), so that another
program on `solo01` cannot read the cache without it. It is one vault key,
`shop_REDIS_PASSWORD`, which the coding agent makes at random with
`set-up-solo-services secrets generate`, so nobody sees it. It never reaches
Git, the Redis command line, or a file inside the container:

- `/etc/custom_redis/redis.env` (mode `0600`, owner `root`): Podman passes
  it to the container as environment variables. The start script writes the
  Redis settings, password included, to Redis's standard input
  (`redis-server -`), so `ps` never shows the password and no settings file
  holds it inside the container.
- `/etc/mmwatchdog/secrets/custom-redis-password` (mode `0600`, owner
  `root`): MMWatchdog's built-in `redis` check reads it as
  `login_password_file`.
- The app's own secrets file, `/etc/shop/shop.env`, as `REDIS_PASSWORD`,
  which Solo already writes for every name in `secrets_from_vault`.

> [!NOTE]
> **Why the vault key is `shop_REDIS_PASSWORD` and not a `custom_` name.**
> The app needs the same password. Solo gives an app a secret only through
> its `secrets_from_vault`, whose vault key is `<app>_<VARIABLE>`. One key
> for both Redis and the app means one password to rotate, never two copies
> that can drift apart. The cost: one app owns the password. A second app
> that uses the same Redis reads the first app's key in its own
> `app_secrets` line.

**MMWatchdog.** One new file, `mmwatchdog_checks/custom_solo_redis.yml`,
with the check group `custom_solo_redis`. The name uses underscores only, so
it matches `^[a-z0-9_]+$`:

- `solo_redis_container_runs`: `custom-redis.service` is active.
- `solo_redis_answers_ping`: Redis answers `PING` after logging in with the
  password.

Both send a `warn` alert. A cache outage slows the site down, but the app
reads from Postgres meanwhile. Change `alert_severity` to `sos` to be woken.

## Apply steps

> [!WARNING]
> **This recipe adds a vault key** (`shop_REDIS_PASSWORD`). The coding agent
> tells the person so, and waits for yes, before it starts. It touches no
> `sudoers`, no `ssh/`, and no firewall rule.

**The coding agent adapts these values:** the app's name (`shop` below),
`max_memory_megabytes`, and `listen_port` when something else on `solo01`
already uses 6379 (`ss -tlnp | grep ':6379'` shows nothing when it is free).

### 1. The setting, in `mmx_project_settings.yml`

Replace `custom: {}` with the block below. When `custom:` already has other
keys, add only the `solo_redis:` key under it.

```yaml
# mmx_project_settings.yml, between the Custom extensions lines
  custom:
    solo_redis:
      # The official Redis image, pinned by tag and by digest. Podman pulls
      # by the digest, so the image cannot change under the same tag. To
      # update, replace both with the new release's tag and digest.
      image: docker.io/library/redis:7.4-alpine@sha256:7f7d30b7fdd09467bac58198a1f166dd69789d348d4fe859cccb20e0cf287fbe
      # Redis's port on 127.0.0.1. Reason for 6379: Redis's usual port, which
      # most Redis clients use by default.
      listen_port: 6379
      # The most memory Redis may use for cached data. When it is full, Redis
      # throws away the least recently used keys. Reason for 256: room for a
      # small app's hot data on a 4 GB server, well under the 75% memory
      # check. Raise it when the hit rate is low and free -m shows room.
      max_memory_megabytes: 256
```

### 2. The password, in the vault

Run this in the systems repository. It makes a random 64-character password
of letters and digits inside MMX and never prints it:

```sh
set-up-solo-services secrets generate --repo-dir . --key shop_REDIS_PASSWORD --length 64
```

**Check:** `set-up-solo-services secrets list --repo-dir .` lists
`shop_REDIS_PASSWORD`.

### 3. The app's connection settings

Add the connection settings and the secret to the app's entry under `apps:`
in `mmx_project_settings.yml`. Add each line under the key that already
exists (`env:` and `secrets_from_vault:`):

```yaml
# mmx_project_settings.yml, in apps.shop.env
        REDIS_HOST: 127.0.0.1
        REDIS_PORT: "6379"
```

```yaml
# mmx_project_settings.yml, in apps.shop.secrets_from_vault
        REDIS_PASSWORD:
          where_the_value_comes_from: generated_by_the_setup
```

Then pass the secret to the app. Solo gives the app only the secrets that
`app_secrets:` names. In `playbooks/solo_server.yml`, in the `apps_and_tunnel`
stage, add one line to `app_secrets:`, beside the app's other secrets:

```yaml
# playbooks/solo_server.yml, in the app_secrets of the apps_and_tunnel stage
            shop_REDIS_PASSWORD: "{{ .secrets.shop_REDIS_PASSWORD }}"
```

These lines are outside the `# --- Custom extensions ---` lines. A Solo
upgrade can leave a conflict in them, so record them under
`## Custom extensions` in your systems repository's `AGENTS.md`.

Solo writes `REDIS_HOST` and `REDIS_PORT` to `/etc/shop/shop_settings.env`
and `REDIS_PASSWORD` to `/etc/shop/shop.env`. The app builds its connection
from the three values. The password is only letters and digits, so it needs
no URL escaping when the app joins them into one address:

```text
redis://:REDIS_PASSWORD@127.0.0.1:6379/0
```

For example, Rails reads them in `config/environments/production.rb`:

```ruby
config.cache_store = :redis_cache_store, {
  url: "redis://#{ENV.fetch('REDIS_HOST')}:#{ENV.fetch('REDIS_PORT')}/0",
  password: ENV.fetch("REDIS_PASSWORD"),
}
```

A Node app passes `{ socket: { host, port }, password }` to `createClient`
of the `redis` package. Let the app treat a Redis error as a cache miss, so a
Redis restart never fails a request.

### 4. The role, `roles/custom_solo_redis/`

Create `roles/custom_solo_redis/files/start_redis`. Podman mounts it
read-only into the container, and it is the program the container runs:

```sh
#!/bin/sh
# Managed by MMX from roles/custom_solo_redis/files/start_redis in the systems repository.
# Starts Redis as a cache that keeps nothing on disk, from the recipe
# custom_recipes/solo-redis-sidecar.md. The settings, password included, go
# to Redis on its standard input (redis-server -), so the password is never
# on a command line that ps shows and never in a file inside the container.
# The values come from /etc/custom_redis/redis.env, which Podman passes in
# as environment variables.
set -eu
: "${REDIS_PASSWORD:?REDIS_PASSWORD is missing from /etc/custom_redis/redis.env}"
: "${REDIS_PORT:?REDIS_PORT is missing from /etc/custom_redis/redis.env}"
: "${REDIS_MAX_MEMORY_MB:?REDIS_MAX_MEMORY_MB is missing from /etc/custom_redis/redis.env}"
# exec makes Redis the container's first process, so Podman's stop signal
# reaches Redis itself.
exec redis-server - <<EOF
bind 127.0.0.1
port ${REDIS_PORT}
protected-mode yes
save ""
appendonly no
maxmemory ${REDIS_MAX_MEMORY_MB}mb
maxmemory-policy allkeys-lru
requirepass "${REDIS_PASSWORD}"
EOF
```

Create `roles/custom_solo_redis/main.yml`:

```yaml
# roles/custom_solo_redis/main.yml
# Redis as a stateless cache in a Podman container on solo01, from the recipe
# custom_recipes/solo-redis-sidecar.md. Redis listens on 127.0.0.1 only. The
# apps' containers use the server's network, so they reach it there.
#
# Redis keeps nothing on disk: no snapshots (save ""), no append-only log
# (appendonly no). When the memory is full, the least recently used keys go
# (allkeys-lru). A restart loses only cached copies.
#
# The role installs Podman itself. Reason: the custom extension stages run
# before the apps_and_tunnel stage, which installs Podman for the apps, so a
# new or rebuilt solo01 would not have it yet. apps_and_tunnel installs the
# same package later in the run, which changes nothing.
inputs:
  image:                                    # custom.solo_redis.image: a tag and a sha256 digest
    type: string
    required: true
  listen_port:                              # custom.solo_redis.listen_port, on 127.0.0.1 only
    type: integer
    required: true
  max_memory_megabytes:                     # custom.solo_redis.max_memory_megabytes
    type: integer
    required: true
  redis_password:                           # the vault key <app>_REDIS_PASSWORD
    type: string
    required: true
    secret: true

node_tasks:
  # A pin without a digest could change under the same tag.
  - id: the_image_is_pinned_by_its_digest
    assert:
      that:
        matches: ["{{ .inputs.image }}", '^docker\.io/library/redis:[0-9A-Za-z._-]+@sha256:[0-9a-f]{64}$']
      message: >-
        custom.solo_redis.image in mmx_project_settings.yml is "{{ .inputs.image }}".
        Write the image with its tag and its digest, such as
        docker.io/library/redis:7.4-alpine@sha256:<64 hexadecimal characters>.
        Nothing changed.

  - id: install_podman
    apt_package:
      packages:
        - {name: podman, version: newest_when_first_installed}

  # MMWatchdog's redis check reads the password from this file. base_server
  # created /etc/mmwatchdog/secrets (mode 0700) earlier in the run.
  - id: write_the_password_for_the_mmwatchdog_redis_check
    file:
      path: /etc/mmwatchdog/secrets/custom-redis-password
      content: "{{ .inputs.redis_password }}\n"
      owner: root
      group: root
      permissions_mode: "0600"

  - id: pull_the_redis_image
    podman_image:
      image: "{{ .inputs.image }}"
      pull_image: when_missing

  - task_block:
      id: custom_solo_redis
      changes:
        - id: create_the_settings_directory
          directory:
            path: /etc/custom_redis
            owner: root
            group: root
            permissions_mode: "0755"
        # Only root reads it. Podman passes it to the container.
        - id: write_the_redis_environment_file
          file:
            path: /etc/custom_redis/redis.env
            content: |
              # Managed by MMX from roles/custom_solo_redis/main.yml in the systems repository.
              REDIS_PASSWORD={{ .inputs.redis_password }}
              REDIS_PORT={{ .inputs.listen_port }}
              REDIS_MAX_MEMORY_MB={{ .inputs.max_memory_megabytes }}
            owner: root
            group: root
            permissions_mode: "0600"
        # Holds no secret: it reads the password from the environment.
        - id: install_the_start_script
          file:
            path: /etc/custom_redis/start_redis
            source: files/start_redis
            owner: root
            group: root
            permissions_mode: "0755"
        - id: install_the_quadlet_file
          podman_quadlet:
            name: custom-redis.container
            content: |
              # Managed by MMX from roles/custom_solo_redis/main.yml in the systems repository.
              [Unit]
              Description=Redis cache for the apps (loopback only, keeps nothing on disk)

              [Container]
              ContainerName=custom-redis
              Image={{ .inputs.image }}
              # The server's own network, as the apps' containers have. Redis
              # binds 127.0.0.1 only (see start_redis), so nothing outside
              # solo01 reaches it.
              Network=host
              EnvironmentFile=/etc/custom_redis/redis.env
              Volume=/etc/custom_redis/start_redis:/usr/local/bin/start_redis:ro
              Exec=/usr/local/bin/start_redis
              User=redis
              LogDriver=journald
              # The same limits as the apps' containers: a read-only file
              # system, root inside is not root on the server, no capability,
              # and Solo's AppArmor profile for app containers.
              # --image-volume=tmpfs keeps the image's /data volume in memory.
              ReadOnly=true
              ReadOnlyTmpfs=true
              UserNS=auto
              DropCapability=all
              NoNewPrivileges=true
              PodmanArgs=--security-opt=apparmor=solo-app-containers --image-volume=tmpfs
              StopTimeout=10

              [Service]
              Restart=always

              [Install]
              WantedBy=multi-user.target
      activate:
        - id: run_redis
          systemd_service:
            name: custom-redis.service
            state: running
            refresh: restart
      verify:
        - id: wait_until_redis_accepts_connections
          wait_for:
            tcp_port_accepts_connections: "{{ .inputs.listen_port }}"
            wait_at_most: 30s
```

### 5. The fleet stage, in `playbooks/solo_server.yml`

Put this stage between the `# --- Custom extensions (start) ---` and
`# --- Custom extensions (end) ---` lines, above the last "Keep these three
boundary comment lines" line. The block runs after `postgres_and_backups` and
before `monitoring_and_outside_alarm` and `apps_and_tunnel`, so Redis runs
before MMWatchdog checks it and before the app starts.

```yaml
# playbooks/solo_server.yml, between the Custom extensions lines
  - id: custom_solo_redis
    nodes: solo_server
    on_node_failure: stop_run
    node_tasks:
      - role: custom_solo_redis
        inputs:
          image: "{{ .vars.custom.solo_redis.image }}"
          listen_port: "{{ .vars.custom.solo_redis.listen_port }}"
          max_memory_megabytes: "{{ .vars.custom.solo_redis.max_memory_megabytes }}"
          redis_password: "{{ .secrets.shop_REDIS_PASSWORD }}"
```

### 6. The check file, `mmwatchdog_checks/custom_solo_redis.yml`

Create the file, then append `custom_solo_redis.yml` to the end of the
`mmwatchdog_check_files` list in `mmx_project_settings.yml`. Never replace
the list. A default list then reads
`mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_solo_redis.yml]`.

```yaml
# Managed by MMX from mmwatchdog_checks/custom_solo_redis.yml in the systems repository.
# The Redis cache on solo01, from the recipe custom_recipes/solo-redis-sidecar.md.
# A cache outage slows the site down but loses no data, because the app
# reads from Postgres meanwhile. So every check here is warn. To be woken for
# a check, set that check's alert_severity to sos.
check_groups:
  custom_solo_redis:
    check_every: 1m
    time_limit_per_run: 10s
    # Reason for 3 minutes: it ignores a restart in progress, such as an image update.
    alert_after_failing_for: 3m
    recovered_after_healthy_for: 1m
    checks:
      # systemd restarts the container after a crash; the warning means it did not stay up.
      solo_redis_container_runs:
        systemd_unit_state:
          systemd_unit: custom-redis.service
          fail_when: the_unit_is_not_active
        alert_severity: warn
      # Logs in with the password, sends PING, and expects PONG. Reason for
      # unencrypted: the connection never leaves solo01.
      solo_redis_answers_ping:
        redis:
          connection_security: unencrypted
          address: "127.0.0.1:{{ .inputs.custom.solo_redis.listen_port }}"
          login_password_file: /etc/mmwatchdog/secrets/custom-redis-password
        alert_severity: warn
```

### 7. Record it

Save this recipe as `custom_recipes/solo-redis-sidecar.md` with `source_url`,
`source_commit`, and `applied_on` at the top. Add an entry to
`custom_extensions:` in `monkeymaxxing_solo_checklist.yml`:

```yaml
custom_extensions:
  - id: solo-redis-sidecar
    title: Add a Redis cache sidecar on Solo
    recipe: services/solo-redis-sidecar.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/services/solo-redis-sidecar.md
    source_commit: "<SHA>"
    applied_on: "2026-11-23"
    state: done
    verification: "The three steps of the Verification check section passed."
```

Replace `<SHA>` with the full commit you read and the date with the UTC date
of the applying commit. Also add one line under `## Custom extensions` in your
systems repository's `AGENTS.md`: this recipe adds `REDIS_*` lines to the app
and one `app_secrets` line in `playbooks/solo_server.yml`.

Then follow your `AGENTS.md`: run `mmx validate solo_server`, commit, push,
run `mmx dryrun solo_server`, tell the person that the run restarts the app
for a few seconds, and run `mmx run solo_server`.

## Verification check

Run these on `solo01` with `mmx run-command --nodes solo_server -- COMMAND`.

1. **Only the loopback address listens:**

   ```sh
   ss -tlnp | grep ':6379'
   ```

   Expected: exactly one line, with `127.0.0.1:6379` and `redis-server` in the
   process column. A line with `0.0.0.0:6379`, `*:6379`, `[::]:6379`, or
   `solo01`'s WireGuard address means the recipe is wrong: stop and fix it.

2. **The container runs:**

   ```sh
   systemctl status custom-redis.service --no-pager
   ```

   Expected: `Active: active (running)`.

3. **MMWatchdog is happy:**

   ```sh
   sudo mmwatchdog check-now custom_solo_redis --count-as-scheduled-run --json
   ```

   Expected: exit code 0, both checks healthy, and the `redis` check's
   message `the Redis server at 127.0.0.1:6379 answered PING`.

Optionally, prove that the app reaches it: after the app's next request
that uses the cache, `podman exec custom-redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli DBSIZE'`
prints a number above 0.

## Clean removal

Remove everything, in this order, so the app never tries a Redis that is
gone and no alert fires while it goes.

1. **Take the app off Redis first.** Change the app so it no longer needs
   Redis, deploy that release, and remove `REDIS_HOST`, `REDIS_PORT`, and
   `REDIS_PASSWORD` from the app's `env:` and `secrets_from_vault:`. Remove
   the `shop_REDIS_PASSWORD` line from `app_secrets:` in the `apps_and_tunnel`
   stage.
2. **Remove the checks.** Remove `custom_solo_redis.yml` from
   `mmwatchdog_check_files`, keeping the other entries, and delete
   `mmwatchdog_checks/custom_solo_redis.yml`. MMX then removes the check
   group from `solo01`.
3. **Swap the stage for a removal stage.** In the `# --- Custom extensions ---`
   block, replace the `custom_solo_redis` stage with this stage:

   ```yaml
     - id: remove_the_custom_solo_redis
       nodes: solo_server
       on_node_failure: stop_run
       node_tasks:
         # Stops custom-redis.service, deletes the Quadlet file, and reloads systemd.
         - id: remove_the_redis_container
           podman_quadlet:
             name: custom-redis.container
             state: file_and_service_removed_named_volumes_kept
         - id: remove_the_redis_settings
           directory:
             path: /etc/custom_redis
             state: absent
             also_delete_everything_inside: true
         - id: remove_the_password_of_the_mmwatchdog_check
           file:
             path: /etc/mmwatchdog/secrets/custom-redis-password
             state: absent
         - id: remove_the_redis_image
           shell:
             script: podman image rm --ignore "$IMAGE"
             env:
               IMAGE: docker.io/library/redis:7.4-alpine@sha256:7f7d30b7fdd09467bac58198a1f166dd69789d348d4fe859cccb20e0cf287fbe
   ```

   Write the image you had in `custom.solo_redis.image`. The stage leaves the
   `podman` package in place: Solo installs it for the apps.
4. **Remove the setting.** Delete the `solo_redis:` key under `custom:`.
   When it was the only key, write `custom: {}` again.
5. **Run it.** Run `mmx validate solo_server`, commit, push, and run
   `mmx run solo_server`. Check that `systemctl status custom-redis.service`
   says the unit could not be found, that `ss -tlnp | grep ':6379'` prints
   nothing, and that `ls /etc/custom_redis /etc/mmwatchdog/secrets/custom-redis-password`
   fails.
6. **Delete the rest in a second commit.** Remove the
   `remove_the_custom_solo_redis` stage, the folder `roles/custom_solo_redis/`,
   `custom_recipes/solo-redis-sidecar.md`, the `solo-redis-sidecar` entry of
   `custom_extensions:`, and the note under `## Custom extensions` in
   `AGENTS.md`. The vault key `shop_REDIS_PASSWORD` stays in the vault, unused,
   which does no harm. Run `mmx validate solo_server`, commit, and push. The
   system is then the same as before.
