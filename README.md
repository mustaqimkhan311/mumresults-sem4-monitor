# Mumbai University M.Sc. IT Semester IV Result Monitor

This monitor checks https://www.mumresults.in/ every 15 minutes using GitHub Actions.

It looks specifically for:

- Program code: `1113161`
- Course: `Master of Science(Information Technology)`
- Semester: `Semester - IV`

When the listing appears or changes, it sends a Telegram notification.

## 1. Create the Telegram bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`.
3. Follow the prompts and copy the bot token.
4. Open your new bot and send it a message such as `test`.
5. To get your chat ID, open:
   `https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates`
6. Find `"chat":{"id": ...}` and copy the numeric ID.

Do not publish the bot token.

## 2. Create a GitHub repository

Create a new repository, for example:

`mumresults-sem4-monitor`

Upload:

- `monitor.py`
- `requirements.txt`
- `.github/workflows/check.yml`
- `state.json`

For `state.json`, use:

```json
{}
```

## 3. Add GitHub Secrets

Repository → Settings → Secrets and variables → Actions → New repository secret

Create:

- `TELEGRAM_BOT_TOKEN` = your BotFather token
- `TELEGRAM_CHAT_ID` = your Telegram chat ID

## 4. Enable Actions

Open the repository's **Actions** tab and make sure workflows are allowed.

You can also run the workflow manually with **Run workflow**.

## 5. How it behaves

Every 15 minutes GitHub runs the script.

- Target not present → no message.
- Target appears → Telegram alert.
- Target remains unchanged → no duplicate alert.
- Target link/date changes → another alert.

The script keeps the last detected result in `state.json`.

## Important

The monitor intentionally watches the **main Online Results listing**, not only a guessed PDF URL. This is more robust because Mumbai University can publish a result under a new PDF filename/path.

The program code is kept as `1113161`; if the university changes the code in a future academic pattern, update `PROGRAM_CODE` in `monitor.py`.
