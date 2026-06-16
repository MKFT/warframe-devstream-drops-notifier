English | [繁體中文](README.zh-TW.md)

# Warframe Devstream & Drops Notifier

Watches the Warframe [Livestreams forum](https://forums.warframe.com/forum/113-livestreams/) and posts a Discord message for every new **Devstream** or **Twitch Drop event** announcement.

Pure Python standard library, no dependencies, runs on GitHub Actions.

> The Discord messages are written in Traditional Chinese. Edit `build_message` in `main.py` for another language.

## How it works

Each scheduled run of `main.py`:

1. Fetches the Livestreams RSS feed (`/forum/113-livestreams.xml`). Topic pages are blocked by Cloudflare, but the feed itself is accessible.
2. Selects threads to track **by title**, deduplicated by thread ID:
   - Excludes the weekly **stream schedules** (title contains `Community Stream Schedule`).
   - Title contains `Devstream` → treated as a **Devstream announcement**.
   - Title contains `Twitch Drops` / `Drops Campaign` → treated as a **Twitch Drop event announcement**.
3. Posts a Discord message for each new announcement:
   - 🎮 **Devstream**: labels its drop status from the post body — 🎁 Twitch Drop detected (includes the matching sentence) / ❌ explicitly none this time / ❓ couldn't tell (check the post yourself).
   - 📣 **Twitch Drop event**: just notifies and links to the original post; the body is not parsed.

### Why decide by title instead of the body?

Almost every weekly schedule mentions Twitch Drops in its body (it lists which streams have drops this week, how to link your account), so **judging by the body would misclassify every schedule as a drop event**. The title, by contrast, is clean: across 255 historical posts that were checked, **none** of the 165 schedules had `Twitch Drops` in their title. So "the title decides whether to send, the body only labels" is the design least likely to go wrong.

The Twitch Drop event announcements don't try to parse out rewards and times because DE has used several different post templates over the years and writes titles and bodies very loosely — parsing is fragile and error-prone, so it just notifies and links to the original.

## State & heartbeat (the `state` branch)

The dedupe file `seen.json` lives on a separate `state` branch; `main` holds only code. Each run pulls `seen.json` from `state`, then commits it back together with a `last_run.txt` heartbeat.

"New announcement" commits are kept as a change log (the timestamps let you analyse announcement frequency); heartbeat-only commits are force-pushed/rolled so they don't pile up. So `state` is roughly all the real-change commits plus at most one trailing heartbeat.

The heartbeat exists to dodge GitHub's "disable scheduled workflows after 60 days of inactivity": new announcements only update `seen.json` about monthly, which is too sparse, so every run commits to keep the repo active. The commit message states whether it was a real update or just a heartbeat.

When writing back, `seen.json` keeps only IDs still present in the RSS feed; older threads that scrolled off are dropped, so the file never grows unbounded.

## Deploy

1. Fork this repo.
2. Create a Discord webhook: channel → Edit Channel → Integrations → Webhooks → copy the URL.
3. Add a repo secret `DISCORD_WEBHOOK_URL`: Settings → Secrets and variables → Actions.
4. Enable the workflow under the Actions tab (forked repos have scheduled workflows disabled by default).

The first run posts every tracked announcement currently in the feed (Devstreams + Twitch Drop events, ~5) so you can confirm it works; after that, only new ones. The schedule lives in `.github/workflows/check.yml` (`cron`). To reset the seen history, delete the `state` branch — it rebuilds on the next run.

## Send failures

Sending to Discord is retried up to 3 times; if all attempts fail the post is given up (not retried forever) and the run exits non-zero, so it's marked failed and emails you. One failure doesn't affect the other posts, and progress is still written back.

## Local testing

```bash
# With no seen.json, every currently-tracked announcement is treated as new
python3 main.py

# Without DISCORD_WEBHOOK_URL it only logs the detection status; export it to actually send:
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 main.py
```

| Env var | Notes |
|---|---|
| `DISCORD_WEBHOOK_URL` | If unset, only logs — does not send |
| `SEEN_PATH` | Path to `seen.json`, defaults to next to the script |

## Known limitation

A Devstream's drop label relies entirely on the RSS body (in practice it carries the full first post, not a truncated excerpt). It only labels the message and never gates sending, so even unfamiliar wording flagged as "couldn't tell" still reaches you — nothing is missed. Twitch Drop event announcements are always notify-and-link only; rewards and times are not parsed.
