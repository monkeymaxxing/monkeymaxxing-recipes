---
id: scheduled-tasks
title: Run scheduled app tasks with systemd timers
category: services
applies_to: [stack, solo]
summary: Runs your app's own commands on a schedule, such as a nightly cleanup, in a one-off container of the live release, on one server, with MMWatchdog checks for failed or missed runs.
author: monkeymaxxing
vetted_on: 2026-11-23
vetted_against:
  stack: v0.3.1
  solo: v0.1.0
vetted_method: live-checkpoint
---

# Run scheduled app tasks with systemd timers

> [!IMPORTANT]
> Reviewed once when added. Recipes are not re-tested on every Stack or Solo release and are outside core support.

This recipe runs your app's own commands at set times, such as a nightly
cleanup, a billing sweep, or a weekly report. Each run starts a one-off
container of the release that is live at that moment, with the app's own
settings and secrets, and removes the container when the command ends.

## When to use this (and when you don't need it)

Use this recipe when the app has a command that must run on a schedule and
the app has no scheduler of its own that already works. For example:

```sh
bin/rails runner 'Session.cleanup_expired!'
python manage.py clearsessions
node scripts/send_weekly_report.js
```

You may not need it:

- **The app's job queue has a scheduler.** Solid Queue's recurring tasks,
  GoodJob's cron, Oban's cron plugin, Sidekiq-cron, Celery beat, and
  BullMQ's repeatable jobs run scheduled work inside the job container that
  the Stack and Solo already run, with the queue's own retries and records.
  Prefer that when the app has one: the schedule then deploys with the app.
- **The work is part of a request.** Expiring a record on read, or cleaning
  a few rows at each sign-in, needs no schedule at all.

Choose this recipe when the app has no job queue, or the command is a
plain script that is easier to run on a schedule than to turn into a job.

**One server runs each task.** A nightly billing sweep must run once, not
once on each app server. On Solo there is one server, `solo01`. On the Stack
the recipe runs every task on the one server you name in `run_on_node`, such
as `app001` or `jobs001`, and on no other.

## What it adds and what it costs

| Part | What it is |
| --- | --- |
| A program | `/usr/local/sbin/run_custom_scheduled_task`, a short Python 3 script (Python 3 is already on every Stack and Solo server). It finds the app's live release, runs the command in a one-off container, and writes the result. |
| A settings file | `/etc/custom_scheduled_tasks/settings.json` (mode `0600`): the tasks and where to find each app's release |
| Two systemd units per task | `custom-task-<name>.timer` starts `custom-task-<name>.service` on the schedule. MMX's `systemd_scheduled_job` writes both. |
| A result file per task | `/var/lib/custom-scheduled-tasks/<name>.json`, rewritten after every run |
| A role | `roles/custom_scheduled_tasks/` with `main.yml`, `files/settings.json`, and `files/run_custom_scheduled_task` |
| A fleet stage | `custom_scheduled_tasks`, inside the `# --- Custom extensions ---` lines |
| Settings | `custom.scheduled_tasks` in `mmx_project_settings.yml` |
| An MMWatchdog check file | `mmwatchdog_checks/custom_scheduled_tasks.yml`, with the check group `custom_scheduled_tasks` |
| Records | `custom_recipes/scheduled-tasks.md` and an entry under `custom_extensions:` in the checklist file |

**Cost:** $0 a month. Each run uses the memory and CPU of one more app
container for as long as the command takes. Schedule heavy tasks in a quiet
hour, and away from the core's own nightly work (`nightly_work_starts_at`),
such as the backups.

**Ongoing work:**

- **No change after a deploy.** Each run reads the live release when it
  starts, so a deploy never needs a change to the timers.
- A new task, a changed schedule, or a removed task is a settings change and
  a run of one fleet stage.
- Read a task's output with `journalctl -u custom-task-<name>.service`, and
  the next run time with `systemctl list-timers 'custom-task-*'`.

## Data, security, and backups

- **Stateless.** The recipe keeps nothing but the small result file of each
  task, which it writes again at the next run. Whatever a task changes, it
  changes in the app's own database, which the core backups already cover.
- **The same container limits as the app's migrations and web containers.**
  Each run is `podman run --rm --network host --userns=auto --read-only
  --cap-drop=all --security-opt=no-new-privileges` with the core's AppArmor
  profile (`solo-app-containers` on Solo, `monkeymaxxing-app-containers` on
  the Stack). It mounts the app's `writable_temporary_directories` as empty
  memory-backed folders, as the app's own containers do.
- **The app's own settings and secrets, and nothing more.** The container
  reads the same env files as the app's migrations:
  `/etc/<app>/<app>_settings.env`, `/etc/<app>/<app>.env`, and the database
  file: `/etc/<app>/<app>_database.env` on Solo, or
  `/etc/<app>/<app>_database_direct_to_postgres.env` on the Stack. On the
  Stack that file connects straight to Postgres, not through PgBouncer, so a
  task may hold a whole Postgres session, as a migration may.
- **No new secret, no open port, no firewall rule, no WireGuard
  connection.** The settings file holds only task names, commands, and
  schedules. It is still mode `0600`, because commands sometimes hold a
  customer's name or an ID that nobody else on the server needs to read.
- **No overlap.** systemd never starts a task's service while the last run
  of the same task still runs. The program also takes a lock,
  `/run/custom-scheduled-tasks/<name>.lock`, so a second start by hand waits
  for nothing and does nothing. A run that passes `timeout_seconds` is
  stopped and recorded as failed, with exit code `124`.
- **MMWatchdog checks added**, in the check group `custom_scheduled_tasks`
  (underscores only, so the triage agent can run it), two for each task:
  1. `<name>_timer_is_active`: `custom-task-<name>.timer` is active, so the
     task still has a schedule.
  2. `<name>_last_run_succeeded_recently`: the last run exited with 0, and a
     run succeeded within `max_age_hours`. It fails when a run fails, and
     also when runs stop happening at all, such as after someone stopped the
     timer by hand.

  Both send a `warn` alert. Set `alert_severity` to `sos` for a task whose
  failure must wake someone, such as billing. A new task counts as
  succeeded at the moment the role installs it, so the second check alerts
  only when no run succeeds within `max_age_hours` after that.

## Apply steps

This recipe touches none of the vault's keys, `sudoers`, `ssh/`, the
firewall, or the files that the Stack's desk review watches.

**The coding agent adapts these values:** each task's `name`, `app`,
`command`, `on_calendar`, `max_age_hours`, and `timeout_seconds`, and on the
Stack, `run_on_node`.

- `name` uses lowercase letters, digits, and underscores, and starts with a
  letter (`^[a-z][a-z0-9_]*$`). It names the units, the result file, and the
  checks.
- `app` is a name under `apps:`.
- `command` is the program and its arguments, as you would type them. It is
  split like a shell line (quotes group words) but no shell runs it, so `&&`,
  `|`, `>`, and `$VARIABLE` do nothing. For a pipeline, put a script in the
  app and run that script.
- `on_calendar` is a systemd calendar time, **always ending in `UTC`**, such
  as `*-*-* 02:30:00 UTC` (every day at 02:30) or `Mon *-*-* 06:00:00 UTC`
  (Mondays at 06:00). Server schedules are in UTC. Check a value with
  `systemd-analyze calendar '*-*-* 02:30:00 UTC'`.
- `max_age_hours` is the longest time without a successful run before the
  check warns: the time between two runs plus some margin, such as `26` for a
  daily task and `170` for a weekly one.
- `timeout_seconds` is the longest one run may take before it is stopped.
- `run_on_node` (Stack only) names one app server or jobs server that runs
  the app's containers. Pick a server that is not removed by a scale-down:
  `app001` or `jobs001`.

### 1. The settings, in `mmx_project_settings.yml`

Replace `custom: {}` with the block below. When `custom:` already has other
keys, add only the `scheduled_tasks:` key under it. On Solo, leave out
`run_on_node`.

```yaml
# mmx_project_settings.yml, between the Custom extensions lines
  custom:
    scheduled_tasks:
      run_on_node: app001               # Stack only: the one server that runs every task
      tasks:
        - name: nightly_cleanup
          app: shop
          command: "bin/rails runner 'Session.cleanup_expired!'"
          on_calendar: "*-*-* 02:30:00 UTC"
          # Reason for 26: a daily task, plus 2 hours for a slow night.
          max_age_hours: 26
          # Reason for 1800: the cleanup takes about a minute; 30 minutes
          # means something is stuck.
          timeout_seconds: 1800
      # Names of tasks you took out of tasks above. The role removes their
      # timers and results. Empty the list once a run has removed them.
      removed_tasks: []
```

### 2. The program, `roles/custom_scheduled_tasks/files/run_custom_scheduled_task`

```python
#!/usr/bin/env python3
"""Runs one scheduled task of an app in a one-off container of its live release.

Managed by MMX from roles/custom_scheduled_tasks/files/run_custom_scheduled_task
in the systems repository, from the recipe custom_recipes/scheduled-tasks.md.
custom-task-<name>.service runs it as root:

    run_custom_scheduled_task NAME

It reads the task from /etc/custom_scheduled_tasks/settings.json, finds the
image of the app's live release on this server, runs the command in a
one-off container with the same limits and env files as the app's
migrations, and writes the result to /var/lib/custom-scheduled-tasks/NAME.json,
which MMWatchdog checks. It exits with the command's exit code.

The live release: on a server with web containers, the port in
LIVE_WEB_PORTS_DIRECTORY/<app> names the live web container, and the Image=
line of its Quadlet file names the image. On a Stack jobs server, which has
no web container, the Image= line of <app>-jobs.container names it. A deploy
changes both, so the next run uses the new release with no change here.

Only the Python standard library is used.
"""
import datetime
import fcntl
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

SETTINGS_FILE = Path("/etc/custom_scheduled_tasks/settings.json")
RESULTS_DIRECTORY = Path("/var/lib/custom-scheduled-tasks")
LOCK_DIRECTORY = Path("/run/custom-scheduled-tasks")
QUADLET_DIRECTORY = Path("/etc/containers/systemd")
EXIT_CODE_OF_A_TIMEOUT = 124
SECONDS_TO_STOP_THE_CONTAINER = 30


class Stopped(Exception):
    """systemd asked the task to stop (SIGTERM), such as at a shutdown."""


def stop_requested(signal_number, frame):
    raise Stopped()


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def image_of_the_live_release(app, live_web_ports_directory):
    port_file = Path(live_web_ports_directory) / app
    if port_file.exists():
        port = port_file.read_text().strip()
        if not port.isdigit():
            raise RuntimeError("%s must hold one port number, not %r" % (port_file, port))
        quadlet_file = QUADLET_DIRECTORY / ("%s-web-%d.container" % (app, int(port)))
    else:
        quadlet_file = QUADLET_DIRECTORY / ("%s-jobs.container" % app)
    if not quadlet_file.exists():
        raise RuntimeError(
            "%s is missing, so this server runs no live release of %s. Run the task on a "
            "server that runs the app's web or job containers." % (quadlet_file, app))
    for line in quadlet_file.read_text().splitlines():
        if line.startswith("Image="):
            return line[len("Image="):].strip()
    raise RuntimeError("%s has no Image= line" % quadlet_file)


def last_success(name):
    try:
        return json.loads((RESULTS_DIRECTORY / ("%s.json" % name)).read_text()).get("epoch_last_success")
    except (OSError, ValueError):
        return None


def write_the_result(name, result):
    RESULTS_DIRECTORY.mkdir(mode=0o755, exist_ok=True)
    path = RESULTS_DIRECTORY / ("%s.json" % name)
    temporary = RESULTS_DIRECTORY / (".%s.json.new" % name)
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    os.chmod(temporary, 0o644)          # MMWatchdog's check reads it as the account mmwatchdog
    os.replace(temporary, path)


def main():
    if len(sys.argv) != 2:
        print("Usage: run_custom_scheduled_task NAME", file=sys.stderr)
        return 2
    name = sys.argv[1]
    settings = json.loads(SETTINGS_FILE.read_text())
    task = next((task for task in settings["tasks"] if task["name"] == name), None)
    if task is None:
        print("run_custom_scheduled_task: %s has no task named %s" % (SETTINGS_FILE, name), file=sys.stderr)
        return 2

    LOCK_DIRECTORY.mkdir(mode=0o755, exist_ok=True)
    lock = open(LOCK_DIRECTORY / ("%s.lock" % name), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("run_custom_scheduled_task: %s is already running, so this start does nothing" % name, file=sys.stderr)
        return 0
    signal.signal(signal.SIGTERM, stop_requested)

    app = task["app"]
    container_name = "custom-task-%s" % name
    started_at = now_utc()
    image = None
    exit_code = 1
    try:
        image = image_of_the_live_release(app, settings["live_web_ports_directory"])
        arguments = [
            "podman", "run", "--rm", "--replace", "--name", container_name,
            "--network", "host", "--userns=auto", "--read-only", "--read-only-tmpfs",
            "--cap-drop=all", "--security-opt=no-new-privileges",
            "--security-opt", "apparmor=%s" % settings["apparmor_profile"],
            "--env-file", "/etc/%s/%s_settings.env" % (app, app),
            "--env-file", "/etc/%s/%s.env" % (app, app),
            "--env-file", "/etc/%s/%s%s.env" % (app, app, settings["database_env_file_suffix"]),
        ]
        for directory in settings["writable_temporary_directories"].get(app) or []:
            arguments += ["--tmpfs", "%s:mode=1777" % directory]
        arguments += [image] + shlex.split(task["command"])
        print("Running %s for %s in %s" % (name, app, image), flush=True)
        process = subprocess.Popen(arguments)
        try:
            exit_code = process.wait(timeout=int(task["timeout_seconds"]))
        except subprocess.TimeoutExpired:
            print("%s ran longer than %s seconds, so it is stopped" % (name, task["timeout_seconds"]),
                  file=sys.stderr, flush=True)
            subprocess.run(["podman", "stop", "--time", str(SECONDS_TO_STOP_THE_CONTAINER), container_name], check=False)
            process.wait()
            exit_code = EXIT_CODE_OF_A_TIMEOUT
        except Stopped:
            print("%s was asked to stop, so the container is stopped" % name, file=sys.stderr, flush=True)
            subprocess.run(["podman", "stop", "--time", str(SECONDS_TO_STOP_THE_CONTAINER), container_name], check=False)
            process.wait()
            exit_code = 143
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print("run_custom_scheduled_task: %s" % error, file=sys.stderr, flush=True)
        exit_code = 1
    except Stopped:
        exit_code = 143

    finished_at = now_utc()
    write_the_result(name, {
        "task": name,
        "app": app,
        "image": image,
        "exit_code": exit_code,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "epoch_finished": int(finished_at.timestamp()),
        "epoch_last_success": int(finished_at.timestamp()) if exit_code == 0 else last_success(name),
    })
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

### 3. The settings file template, `roles/custom_scheduled_tasks/files/settings.json`

```text
{{- /*
  The settings of run_custom_scheduled_task:
  /etc/custom_scheduled_tasks/settings.json, mode 0600, root. It reads the
  role inputs tasks, apps, live_web_ports_directory, database_env_file_suffix,
  and apparmor_profile.
*/ -}}
{{- $directories := dict -}}
{{- range $app_name, $app := .inputs.apps -}}
{{- $_ := set $directories $app_name (get $app "writable_temporary_directories" | default list) -}}
{{- end -}}
{{- range .inputs.tasks -}}
{{- if not (hasKey $.inputs.apps .app) }}{{ fail (printf "custom.scheduled_tasks.tasks %q names app %q, which is not under apps: in mmx_project_settings.yml." .name .app) }}{{ end -}}
{{- end -}}
{{ toPrettyJson (dict
  "live_web_ports_directory" .inputs.live_web_ports_directory
  "database_env_file_suffix" .inputs.database_env_file_suffix
  "apparmor_profile" .inputs.apparmor_profile
  "writable_temporary_directories" $directories
  "tasks" .inputs.tasks) }}
```

### 4. The role, `roles/custom_scheduled_tasks/main.yml`

```yaml
# roles/custom_scheduled_tasks/main.yml
# Runs the apps' scheduled tasks from systemd timers, from the recipe
# custom_recipes/scheduled-tasks.md. Each task is a timer and a oneshot
# service (MMX's systemd_scheduled_job) that runs
# /usr/local/sbin/run_custom_scheduled_task NAME. That program runs the
# command in a one-off container of the app's live release and writes
# /var/lib/custom-scheduled-tasks/NAME.json, which MMWatchdog checks.
inputs:
  apps:                                     # vars.apps from mmx_project_settings.yml
    type: mapping
    required: true
  tasks:                                    # custom.scheduled_tasks.tasks
    type: list
    required: true
  removed_tasks:                            # custom.scheduled_tasks.removed_tasks
    type: list
    default: []
  live_web_ports_directory:                 # where the core records each app's live web port
    type: string
    required: true
  database_env_file_suffix:                 # _database on Solo, _database_direct_to_postgres on the Stack
    type: string
    required: true
  apparmor_profile:                         # the core's AppArmor profile for app containers
    type: string
    required: true

node_tasks:
  # A bad name or a missing app stops the run before anything changes.
  - id: each_task_is_written_correctly
    loop: "{{ .inputs.tasks }}"
    as: task
    assert:
      that:
        all:
          - matches: ["{{ .task.name }}", '^[a-z][a-z0-9_]*$']
          - matches: ["{{ .task.on_calendar }}", 'UTC$']
          - number_at_least: ["{{ .task.max_age_hours }}", 1]
          - number_at_least: ["{{ .task.timeout_seconds }}", 1]
          - not: {equals: ["{{ .task.command }}", ""]}
          - not: {equals: ["{{ .task.app }}", ""]}
      message: >-
        The scheduled task "{{ .task.name }}" in custom.scheduled_tasks.tasks needs a
        name of lowercase letters, digits, and underscores that starts with a
        letter; an app that is under apps:; a command; an on_calendar that ends in
        UTC; and whole numbers for max_age_hours and timeout_seconds. Nothing changed.

  - id: install_the_program_that_runs_a_task
    file:
      path: /usr/local/sbin/run_custom_scheduled_task
      source: files/run_custom_scheduled_task
      owner: root
      group: root
      permissions_mode: "0755"
  - id: create_the_settings_directory
    directory:
      path: /etc/custom_scheduled_tasks
      owner: root
      group: root
      permissions_mode: "0755"
  - id: write_the_settings_of_the_tasks
    file:
      path: /etc/custom_scheduled_tasks/settings.json
      template: files/settings.json
      owner: root
      group: root
      permissions_mode: "0600"
  # MMWatchdog's check reads the results as the account mmwatchdog.
  - id: create_the_results_directory
    directory:
      path: /var/lib/custom-scheduled-tasks
      owner: root
      group: root
      permissions_mode: "0755"

  # A new task counts as succeeded when it is installed, so its check alerts
  # only when no run succeeds within max_age_hours after that. An existing
  # result is never replaced.
  - id: record_each_new_task_as_installed
    loop: "{{ .inputs.tasks }}"
    as: task
    shell:
      script: |
        jq -n --arg task "$TASK" --arg app "$APP" \
          '{task: $task, app: $app, image: null, exit_code: 0, started_at: null, finished_at: null,
            epoch_finished: null, epoch_last_success: (now | floor), note: "installed; no run yet"}' \
          > "$RESULT_FILE.new"
        chmod 0644 "$RESULT_FILE.new"
        mv "$RESULT_FILE.new" "$RESULT_FILE"
      env:
        TASK: "{{ .task.name }}"
        APP: "{{ .task.app }}"
        RESULT_FILE: "/var/lib/custom-scheduled-tasks/{{ .task.name }}.json"
      skip_if_this_path_exists: "/var/lib/custom-scheduled-tasks/{{ .task.name }}.json"

  # systemd never starts the service while its last run still runs.
  # run_missed_job_after_downtime runs a task once after a boot when its time
  # passed while the server was off, such as during a reboot after updates.
  # stop_a_run_after is a backstop in case the wrapper itself hangs; the
  # wrapper enforces each task's own timeout_seconds and stops the container.
  # Reason for 6h: longer than ordinary nightly tasks while still stopping a
  # stuck wrapper. Raise it if a task's timeout_seconds approaches 6 hours.
  - id: schedule_each_task
    loop: "{{ .inputs.tasks }}"
    as: task
    systemd_scheduled_job:
      name: "custom-task-{{ .task.name }}"
      systemd_calendar_schedule: "{{ .task.on_calendar }}"
      run_as_user_account: root
      run_missed_job_after_downtime: true
      stop_a_run_after: 6h
      script: exec /usr/local/sbin/run_custom_scheduled_task "$TASK_NAME"
      env:
        TASK_NAME: "{{ .task.name }}"

  - id: remove_each_removed_task
    loop: "{{ .inputs.removed_tasks }}"
    as: name
    systemd_scheduled_job:
      name: "custom-task-{{ .name }}"
      run_as_user_account: root
      state: absent
  - id: remove_the_result_of_each_removed_task
    loop: "{{ .inputs.removed_tasks }}"
    as: name
    file:
      path: "/var/lib/custom-scheduled-tasks/{{ .name }}.json"
      state: absent
```

### 5. The fleet stage

Put the stage between the `# --- Custom extensions (start) ---` and
`# --- Custom extensions (end) ---` lines, above the last "Keep these three
boundary comment lines" line.

On Solo, in `playbooks/solo_server.yml`:

```yaml
  - id: custom_scheduled_tasks
    nodes: solo_server
    on_node_failure: stop_run
    node_tasks:
      - role: custom_scheduled_tasks
        inputs:
          apps: "{{ .vars.apps }}"
          tasks: "{{ .vars.custom.scheduled_tasks.tasks }}"
          removed_tasks: "{{ .vars.custom.scheduled_tasks.removed_tasks }}"
          live_web_ports_directory: /var/lib/solo/live_web_ports
          database_env_file_suffix: _database
          apparmor_profile: solo-app-containers
```

On the Stack, in `playbooks/every_server.yml`. `nodes:` reads `run_on_node`,
so the stage runs on that one server only. A name that is not in the
inventory, such as a server that was replaced, stops the run with
`no node or inventory group named "app001"`, so the tasks never stop
running without a word: write the new server's name and run again.

```yaml
  - id: custom_scheduled_tasks
    nodes: "{{ .vars.custom.scheduled_tasks.run_on_node }}"
    on_node_failure: stop_fleet_stage
    node_tasks:
      - role: custom_scheduled_tasks
        inputs:
          apps: "{{ .vars.apps }}"
          tasks: "{{ .vars.custom.scheduled_tasks.tasks }}"
          removed_tasks: "{{ .vars.custom.scheduled_tasks.removed_tasks }}"
          live_web_ports_directory: /var/lib/monkeymaxxing-stack/live_web_ports
          database_env_file_suffix: _database_direct_to_postgres
          apparmor_profile: monkeymaxxing-app-containers
```

On a brand-new server, this stage runs before the app's own stage in the
same run. That is fine: the role only installs the timers, and the first
run happens at the first scheduled time, after the app is up.

**Moving the tasks to another Stack server.** To move from `app001` to
`jobs001`, first run the removal stage from "Clean removal" with
`nodes: app001`, then change `run_on_node`, and move the check file to the
new server's group list in step 6. Two servers must never hold the same
timers.

### 6. The checks, `mmwatchdog_checks/custom_scheduled_tasks.yml`

Create the file. Then append `custom_scheduled_tasks.yml` to the end of the
`mmwatchdog_check_files` list that already exists. Never replace the list.

- Solo: in `mmx_project_settings.yml`. A default list then reads
  `mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_scheduled_tasks.yml]`.
- Stack: in `inventories/servers.yml`, in the group of the `run_on_node`
  server: `app_servers` for `app001`, or `jobs_servers` for `jobs001`. The
  file renders the task checks on the `run_on_node` server only, and an
  empty file on the other servers of the group, so they never warn about
  timers they do not have.

```yaml
{{- /*
  The checks of the scheduled tasks, from the recipe
  custom_recipes/scheduled-tasks.md. On the Stack the group's other servers
  get an empty file: only custom.scheduled_tasks.run_on_node runs the tasks.
*/ -}}
{{- $settings := .inputs.custom.scheduled_tasks -}}
{{- $run_on_node := get $settings "run_on_node" | default "" -}}
# Managed by MMX from mmwatchdog_checks/custom_scheduled_tasks.yml in the systems repository.
# To be woken for a task, set its checks' alert_severity to sos.
{{- if and $run_on_node (ne $run_on_node .node.name) }}
check_groups: {}
{{- else }}
check_groups:
  custom_scheduled_tasks:
    # Reason for 5 minutes: a task runs hours apart, so a minute's detail adds nothing.
    check_every: 5m
    time_limit_per_run: 10s
    alert_after_failing_for: 10m
    recovered_after_healthy_for: 5m
    checks:
{{- range $settings.tasks }}
      # Reason for warn: a task that failed once usually runs again at its next time.
      {{ .name }}_timer_is_active:
        systemd_unit_state:
          systemd_unit: custom-task-{{ .name }}.timer
          fail_when: the_unit_is_not_active
        alert_severity: warn
      # Fails when the last run exited with another code than 0, or when no
      # run succeeded within max_age_hours. jq prints the reason.
      {{ .name }}_last_run_succeeded_recently:
        shell:
          script: |
            jq -e --argjson max_age_seconds "$MAX_AGE_SECONDS" '
              if .exit_code != 0 then error("the last run of \(.task) exited with \(.exit_code) at \(.finished_at); read journalctl -u custom-task-\(.task).service")
              elif (now - .epoch_last_success) > $max_age_seconds then error("no run of \(.task) succeeded in the last \($max_age_seconds / 3600) hours")
              else true end' "$RESULT_FILE" > /dev/null
          env:
            RESULT_FILE: /var/lib/custom-scheduled-tasks/{{ .name }}.json
            MAX_AGE_SECONDS: "{{ mul .max_age_hours 3600 }}"
        alert_severity: warn
{{- end }}
{{- end }}
```

### 7. Record it

Save this recipe as `custom_recipes/scheduled-tasks.md` with `source_url`,
`source_commit`, and `applied_on` at the top. Add an entry to
`custom_extensions:` in your checklist file (`monkeymaxxing_stack_checklist.yml`
or `monkeymaxxing_solo_checklist.yml`):

```yaml
custom_extensions:
  - id: scheduled-tasks
    title: Run scheduled app tasks with systemd timers
    recipe: services/scheduled-tasks.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/services/scheduled-tasks.md
    source_commit: "<SHA>"
    applied_on: "2026-11-23"
    state: done
    verification: "The four steps of the Verification check section passed."
```

Replace `<SHA>` with the full commit you read and the date with the UTC date
of the applying commit.

Then follow your `AGENTS.md`: run `mmx validate`, commit, publish, run
`mmx dryrun`, and run. On the Stack, run `every_server`:
`./server_management_scripts/run_mmx_on_util01 run every_server`. On Solo,
run `mmx run solo_server`. A later change to the tasks needs only the
stage: `--only-fleet-stages custom_scheduled_tasks`.

## Verification check

Run these on the server that runs the tasks. On the Stack, use
`./server_management_scripts/run_mmx_on_util01 run-command --nodes app001 -- COMMAND`
(the `run_on_node` server). On Solo, use
`mmx run-command --nodes solo_server -- COMMAND`. The examples use the task
`nightly_cleanup`.

1. **The timer is set, for the right time:**

   ```sh
   systemctl list-timers 'custom-task-*' --no-pager
   ```

   Expected: one line for each task, such as `custom-task-nightly_cleanup.timer`,
   with the next run at the UTC time of its `on_calendar`.

2. **One run by hand works.** This runs the task now, exactly as the timer
   will. Ask the person first when the task changes data, such as a billing
   sweep: it runs for real.

   ```sh
   systemctl start custom-task-nightly_cleanup.service
   journalctl -u custom-task-nightly_cleanup.service -n 20 --no-pager
   ```

   Expected: `systemctl start` returns after the command ends, with exit
   code 0. The journal shows `Running nightly_cleanup for shop in` and the
   app's live image, then the command's own output.

3. **The result is recorded:**

   ```sh
   cat /var/lib/custom-scheduled-tasks/nightly_cleanup.json
   ```

   Expected: `"exit_code": 0`, the live image in `"image"`, and
   `"epoch_last_success"` equal to `"epoch_finished"`.

4. **MMWatchdog is happy:**

   ```sh
   sudo mmwatchdog check-now custom_scheduled_tasks --count-as-scheduled-run --json
   ```

   Expected: exit code 0, with `nightly_cleanup_timer_is_active` and
   `nightly_cleanup_last_run_succeeded_recently` healthy. On the Stack, the
   other servers of the group have no `custom_scheduled_tasks` group, so the
   same command fails there.

## Clean removal

1. **Swap the stage for a removal stage.** In the `# --- Custom extensions ---`
   block, replace the `custom_scheduled_tasks` stage with this stage. List
   every task name that the settings ever had in `loop:`. On the Stack, write
   the `run_on_node` server in `nodes:` and `on_node_failure: stop_fleet_stage`.

   ```yaml
     - id: remove_the_custom_scheduled_tasks
       nodes: solo_server
       on_node_failure: stop_run
       node_tasks:
         # Stops and disables each timer, then removes the timer, the service,
         # and MMX's environment file of the job.
         - id: remove_each_timer_and_service
           loop: [nightly_cleanup]
           as: name
           systemd_scheduled_job:
             name: "custom-task-{{ .name }}"
             run_as_user_account: root
             state: absent
         - id: remove_the_program
           file:
             path: /usr/local/sbin/run_custom_scheduled_task
             state: absent
         - id: remove_the_settings
           directory:
             path: /etc/custom_scheduled_tasks
             state: absent
             also_delete_everything_inside: true
         - id: remove_the_results
           directory:
             path: /var/lib/custom-scheduled-tasks
             state: absent
             also_delete_everything_inside: true
         - id: remove_the_locks
           directory:
             path: /run/custom-scheduled-tasks
             state: absent
             also_delete_everything_inside: true
   ```

2. **Remove the checks.** Remove `custom_scheduled_tasks.yml` from each
   `mmwatchdog_check_files` list that you appended it to, keeping the other
   entries. MMX then removes the check group. Delete
   `mmwatchdog_checks/custom_scheduled_tasks.yml`.
3. **Remove the settings.** Delete the `scheduled_tasks:` key under
   `custom:`. When it was the only key, write `custom: {}` again.
4. **Run it.** Commit, publish, and run `every_server` (Solo:
   `solo_server`). Check that `systemctl list-timers 'custom-task-*'` lists
   nothing, and that `ls /etc/custom_scheduled_tasks /var/lib/custom-scheduled-tasks
   /usr/local/sbin/run_custom_scheduled_task` fails.
5. **Delete the rest in a second commit.** Remove the
   `remove_the_custom_scheduled_tasks` stage, the folder
   `roles/custom_scheduled_tasks/`, `custom_recipes/scheduled-tasks.md`, and
   the `scheduled-tasks` entry of `custom_extensions:`. Run `mmx validate`,
   commit, and publish. The system is then the same as before.
