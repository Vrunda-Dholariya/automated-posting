# Automated Multi-Platform Posting API

A FastAPI service with one endpoint, `POST /posting`. It validates a short message containing one link, then publishes it to five third-party platforms **at the same time** and returns a per-platform report. If one platform fails, the others still post.

## Platforms

| Platform | Authentication | How `public_access` is verified |
|---|---|---|
| Bluesky | Handle + app password | Asks Bluesky's public API (no login) whether the post exists |
| Dev.to | API key | Asks Dev.to's public API (no key) for the article |
| Mastodon | Access token | Asks the server for the post **without** a token |
| Telegram (public channel) | Bot token | Looks for the message on the channel's public web preview (`t.me`, falling back to `telegram.me`) |
| GitHub Gist | Personal access token (`gist` scope) | Asks GitHub's API for the gist **without** a token |

`public_access` is a **checked fact, not a hard-coded value**: after posting, the app looks at the post the way an anonymous visitor would.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone <your-repo-url>
cd automated-posting
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

Install and configure:

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` and fill in your credentials (see the table below), then start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Interactive docs: http://localhost:4000/docs

## Credentials

Every secret is read from environment variables (`.env`). Nothing is committed. A platform with missing or invalid credentials reports `failed` while the others continue.

| Variable | Where to get it |
|---|---|
| `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | https://bsky.app/settings/app-passwords |
| `DEVTO_API_KEY` | https://dev.to/settings/extensions ("DEV API Keys") |
| `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | `<your-server>/settings/applications`, with the `write:statuses` permission |
| `TELEGRAM_BOT_TOKEN` | Create a bot with @BotFather |
| `TELEGRAM_CHAT_ID` | Your **public** channel as `@username`. The bot must be an admin with "Post Messages". |
| `GITHUB_GIST_TOKEN` | https://github.com/settings/tokens/new?scopes=gist |
| `DISCORD_WEBHOOK_URL` | Reserved for a future platform, not used yet |

## API

### Request

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "Testing my posting API https://example.com"}'
```

On Windows PowerShell:

```powershell
curl.exe -X POST http://localhost:4000/posting -H "Content-Type: application/json" -d "{\"message\": \"Testing my posting API https://example.com\"}"
```

### Validation rules

- The message must not be empty and must not exceed **200 characters**.
- It must contain **exactly one** link starting with `http://` or `https://`.
- The link must be a valid URL.

Invalid input returns **HTTP 422** with a readable reason, and nothing is posted.

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "message"],
      "msg": "Value error, Message must contain exactly one link starting with http:// or https://; found 0.",
      "input": "No link here"
    }
  ]
}
```

### Response (HTTP 200)

```json
{
  "success": true,
  "results": [
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/did:plc:qqxdyhse2ansqap3om7rwi2b/post/3n2lkheghya2f",
      "public_access": true,
      "date": "2026-11-18",
      "time": "12:25:20",
      "error": null
    }
  ]
}
```

(Shortened to one platform. The full real response with all five platforms is in [`docs/sample-response.json`](docs/sample-response.json).)

A failed platform looks like this:

```json
{
  "platform": "Dev.to",
  "status": "failed",
  "posted_url": null,
  "public_access": false,
  "date": null,
  "time": null,
  "error": "Authentication failed (check your credentials)"
}
```

- `success` is `true` when **at least one** platform succeeded.
- `date` and `time` are in **UTC**.
- A valid request always returns HTTP 200, even if every platform fails. The error is reported per platform, and 4xx codes are reserved for bad input.

## Design

```text
app/
  main.py                    FastAPI app and the /posting route (thin, no logic)
  schemas.py                 Request validation and response models
  config.py                  Settings loaded from environment variables
  platforms/
    base.py                  Platform contract, safe publish(), public-access check
    bluesky.py devto.py mastodon.py telegram.py gist.py
  services/
    posting_service.py       Runs all platforms concurrently, builds the response
tests/                       Offline tests (no real network calls)
```

**Decisions worth knowing:**

- **One contract, one file per platform.** Each platform implements `is_configured()` and `_send()`. Adding a platform means one new file and one line in `default_platforms()`.
- **Concurrent posting.** `asyncio.gather` posts to every platform at once, so the total time is about the slowest platform, not the sum. A test measures overlap by counting how many platforms are in flight at once, instead of timing.
- **Failure isolation in two layers.** `Platform.publish()` converts every error into a failed result. The service adds a second safety net with `gather(return_exceptions=True)`.
- **Honest `public_access`.** Each platform verifies visibility without credentials. If it cannot confirm, it reports `false`, never a guess of `true`.
- **Secrets stay secret.** Credentials come from the environment, error messages never include tokens, and `httpx` request logging is silenced because Telegram's API URL contains the bot token.

## Testing

```bash
python -m pytest -q
```

Tests run offline. Platform calls are replaced with `httpx.MockTransport`, and the endpoint tests replace the posting service. They cover validation, each platform's success and failure paths, concurrency, failure isolation, and token non-leakage.

## Evidence

| What | File |
|---|---|
| Successful request, 5 platforms | `docs/screenshots/swagger-200.png` |
| Validation error (422) | `docs/screenshots/swagger-422.png` |
| Server logs | `docs/screenshots/uvicorn-logs.png` |
| Full real response | `docs/sample-response.json` |

## Known limitations

- **Dev.to publishes articles**, so the title is derived from the start of the message (link removed). Repeated promotional posts may be rate-limited or flagged by Dev.to.
- **Bluesky logs in on every request.** That is fine for this scale. A production version would cache the session token.
- **The Telegram public check depends on the channel's public web preview** (`t.me/s/<channel>`). If that preview is disabled or both hosts are unreachable, it reports `false` even though the post exists. Private channels always report `false`.
- **`public_access` is verified at posting time only.** It does not account for later moderation or deletion.
- The API has **no authentication or rate limiting** of its own. It is designed to run locally for this assessment.
