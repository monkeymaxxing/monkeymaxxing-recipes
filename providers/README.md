# Provider guides

These guides let the Monkeymaxxing Stack run at a server provider beyond the
two that ship with it, Hetzner Cloud and OVHcloud Public Cloud. They are
reference documents, not add-on services, so each one keeps the shape of the
Stack's own provider guides. Each guide starts with the
[recipe frontmatter](../CONTRACT.md#frontmatter) and the trust banner.

| Provider | Guide |
| --- | --- |
| DigitalOcean | [digitalocean.md](digitalocean.md) |
| Vultr | [vultr.md](vultr.md) |
| Scaleway | [scaleway.md](scaleway.md) |
| AWS EC2 | [aws-ec2.md](aws-ec2.md) |
| Google Compute Engine | [google-compute-engine.md](google-compute-engine.md) |

## What a provider guide contains

The Stack's [provider script contract](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/skills/monkeymaxxing-stack/systems_repository_template/server_management_scripts/README.md#write-the-teams-provider-scripts)
says that a team's coding agent writes five provider scripts: they list
servers, create a server, destroy a server, power a server off, and read the
monthly price at the provider. Each guide here holds the provider's request
function and those five scripts, written for that provider's API. The Stack's
[provider guides README](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/skills/monkeymaxxing-stack/systems_repository_template/provider_guides/README.md)
explains the shared rules, including how the person types the provider key
on the laptop.

Your coding agent copies the guide for the chosen provider into
`provider_guides/` in your systems repository, then writes your scripts
from it.

## Script tests

Each guide has a test in `providers/<id>/<name>_provider_scripts_test.py`. The
test builds the five scripts from the guide's own code blocks and runs them
against a fake provider API, so it needs no account and spends no money:

```sh
python3 providers/digitalocean/digitalocean_provider_scripts_test.py
```

CI runs all five tests on every pull request. When you change a guide's code
blocks, run its test.

## A new provider needs one line in the Stack

A provider whose API takes a token in a header only works after its API
address is added to `providerGuideAPIAddresses` in the Stack's
[`set_up_outside_services/personal_token.go`](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/set_up_outside_services/personal_token.go).
That list keeps a coding agent from sending the person's provider token to
any other host. The Stack already lists DigitalOcean, Vultr, and Scaleway,
and it signs requests for AWS EC2 and Google Compute Engine itself, so the
five guides above work out of the box.

A guide for a **new** header-token provider, such as Netcup, UpCloud, or
Linode, must say this plainly, and its pull request links the matching
one-line change to
[monkeymaxxing-stack](https://github.com/monkeymaxxing/monkeymaxxing-stack).
This is rule 10 of the [Recipe Contract](../CONTRACT.md#core-rules-every-recipe-keeps).
