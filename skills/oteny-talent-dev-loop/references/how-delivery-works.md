# How your files reach the bot

You never copy files onto the bot. You never give Oteny your GitHub password.

1. You **push** your branch to GitHub. Your laptop login stays on your laptop.
2. You tell Oteny a **URL + branch** (`oteny reload`, or a launcher that calls `request_dev_bot`).
3. Oteny **pulls** that commit with **its own** read-only deploy key. That key lives on Oteny's router. It never lands on the bot.
4. The overlay copies those files onto the bot.

The bot never runs `git clone`. Files you have not pushed never reach it.

Every pull is linted, staged, swapped in, and rolled back if the self-check fails.

## Two keys — do not mix them

| Key | What it does |
| --- | --- |
| **Account key** (`OTENY_ACCOUNT_KEY`) | Talks to Oteny `/json/2/`. It is not a GitHub key. |
| **Oteny's deploy key** | Oteny uses this to pull a private repo. You never hold it. |

An empty `auth_handle` on a deploy-key source is normal. It is not a missing credential.

HTTPS on your laptop `origin` is fine. Oteny rewrites HTTPS to SSH when it pulls with a deploy key.

## When the bot is ready

`active` means the box booted. It does **not** mean your Talent is on it.

Wait until `talent_delivered` is true, or `hh.talent.source.last_status` reads `delivered`. Then test.

If delivery failed, read `last_error`. Push the fix. Then `oteny reload --ref`.

## Private repo Oteny does not own

A **public** repo needs no extra GitHub step.

A private repo Oteny already hosts (for example `otenycom/radar`) already has the key.

A private repo **you** own: a repo admin adds Oteny's read-only Deploy Key once (GitHub → Settings → Deploy keys; leave write access off). Until the GitHub App ships, that is the extra step.
