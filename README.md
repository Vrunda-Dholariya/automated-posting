\# Automated Multi-Platform Posting API



A FastAPI service with one endpoint, `POST /posting`. It validates a short message containing one link, then publishes it to five third-party platforms \*\*at the same time\*\* and returns a per-platform report. If one platform fails, the others still post.



\## Platforms



| Platform | Authentication | How `public\_access` is verified |

|---|---|---|

| Bluesky | Handle + app password | Asks Bluesky's public API (no login) whether the post exists |

| Dev.to | API key | Asks Dev.to's public API (no key) for the article |

| Mastodon | Access token | Asks the server for the post \*\*without\*\* a token |

| Telegram (public channel) | Bot token | Looks for the message on the channel's public web preview (`t.me`, falling back to `telegram.me`) |

| GitHub Gist | Personal access token (`gist` scope) | Asks GitHub's API for the gist \*\*without\*\* a token |



`public\_access` is a \*\*checked fact, not a hard-coded value\*\*: after posting, the app looks at the post the way an anonymous visitor would.



\## Quick start



Requires Python 3.10 or newer.



```bash

git clone <your-repo-url>

cd automated-posting

python -m venv .venv

```



Activate the virtual environment:



```bash

\# Windows (PowerShell)

.venv\\Scripts\\Activate.ps1

\# macOS / Linux

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



\## Credentials



Every secret is read from environment variables (`.env`). Nothing is committed. A platform with missing or invalid credentials reports `failed` while the others continue.



| Variable | Where to get it |

|---|---|

| `BLUESKY\_HANDLE`, `BLUESKY\_APP\_PASSWORD` | https://bsky.app/settings/app-passwords |

| `DEVTO\_API\_KEY` | https://dev.to/settings/extensions ("DEV API Keys") |

| `MASTODON\_BASE\_URL`, `MASTODON\_ACCESS\_TOKEN` | `<your-server>/settings/applications`, with the `write:statuses` permission |

| `TELEGRAM\_BOT\_TOKEN` | Create a bot with @BotFather |

| `TELEGRAM\_CHAT\_ID` | Your \*\*public\*\* channel as `@username`. The bot must be an admin with "Post Messages". |

| `GITHUB\_GIST\_TOKEN` | https://github.com/settings/tokens/new?scopes=gist |

| `DISCORD\_WEBHOOK\_URL` | Reserved for a future platform, not used yet |



\## API



\### Request



```bash

curl -X POST http://localhost:4000/posting \\

&#x20; -H "Content-Type: application/json" \\

&#x20; -d '{"message": "Testing my posting API https://example.com"}'

```



On Windows PowerShell:



```powershell

curl.exe -X POST http://localhost:4000/posting -H "Content-Type: application/json" -d "{\\"message\\": \\"Testing my posting API https://example.com\\"}"

```



\### Validation rules



\- The message must not be empty and must not exceed \*\*200 characters\*\*.

\- It must contain \*\*exactly one\*\* link starting with `http://` or `https://`.

\- The link must be a valid URL.



Invalid input returns \*\*HTTP 422\*\* with a readable reason, and nothing is posted.



```json

{

&#x20; "detail": \[

&#x20;   {

&#x20;     "type": "value\_error",

&#x20;     "loc": \["body", "message"],

&#x20;     "msg": "Value error, Message must contain exactly one link starting with http:// or https://; found 0.",

&#x20;     "input": "No link here"

&#x20;   }

&#x20; ]

}

```



\### Response (HTTP 200)



```json

{

&#x20; "success": true,

&#x20; "results": \[

&#x20;   {

&#x20;     "platform": "Bluesky",

&#x20;     "status": "success",

&#x20;     "posted\_url": "https://bsky.app/profile/did:plc:qqxdyhse2ansqap3om7rwi2b/post/3n2lkheghya2f",

&#x20;     "public\_access": true,

&#x20;     "date": "2026-11-18",

&#x20;     "time": "12:25:20",

&#x20;     "error": null

&#x20;   }

&#x20; ]

}

```



(Shortened to one platform. The full real response with all five platforms is in \[`docs/sample-response.json`](docs/sample-response.json).)



A failed platform looks like this:



```json

{

&#x20; "platform": "Dev.to",

&#x20; "status": "failed",

&#x20; "posted\_url": null,

&#x20; "public\_access": false,

&#x20; "date": null,

&#x20; "time": null,

&#x20; "error": "Authentication failed (check your credentials)"

}

```



\- `success` is `true` when \*\*at least one\*\* platform succeeded.

\- `date` and `time` are in \*\*UTC\*\*.

\- A valid request always returns HTTP 200, even if every platform fails. The error is reported per platform, and 4xx codes are reserved for bad input.



\## Design



```text

app/

&#x20; main.py                    FastAPI app and the /posting route (thin, no logic)

&#x20; schemas.py                 Request validation and response models

&#x20; config.py                  Settings loaded from environment variables

&#x20; platforms/

&#x20;   base.py                  Platform contract, safe publish(), public-access check

&#x20;   bluesky.py devto.py mastodon.py telegram.py gist.py

&#x20; services/

&#x20;   posting\_service.py       Runs all platforms concurrently, builds the response

tests/                       Offline tests (no real network calls)

```



\*\*Decisions worth knowing:\*\*



\- \*\*One contract, one file per platform.\*\* Each platform implements `is\_configured()` and `\_send()`. Adding a platform means one new file and one line in `default\_platforms()`.

\- \*\*Concurrent posting.\*\* `asyncio.gather` posts to every platform at once, so the total time is about the slowest platform, not the sum. A test measures overlap by counting how many platforms are in flight at once, instead of timing.

\- \*\*Failure isolation in two layers.\*\* `Platform.publish()` converts every error into a failed result. The service adds a second safety net with `gather(return\_exceptions=True)`.

\- \*\*Honest `public\_access`.\*\* Each platform verifies visibility without credentials. If it cannot confirm, it reports `false`, never a guess of `true`.

\- \*\*Secrets stay secret.\*\* Credentials come from the environment, error messages never include tokens, and `httpx` request logging is silenced because Telegram's API URL contains the bot token.



\## Testing



```bash

python -m pytest -q

```



Tests run offline. Platform calls are replaced with `httpx.MockTransport`, and the endpoint tests replace the posting service. They cover validation, each platform's success and failure paths, concurrency, failure isolation, and token non-leakage.



\## Evidence



| What | File |

|---|---|

| Successful request, 5 platforms | `docs/screenshots/swagger-200.png` |

| Validation error (422) | `docs/screenshots/swagger-422.png` |

| Server logs | `docs/screenshots/uvicorn-logs.png` |

| Full real response | `docs/sample-response.json` |



\## Known limitations



\- \*\*Dev.to publishes articles\*\*, so the title is derived from the start of the message (link removed). Repeated promotional posts may be rate-limited or flagged by Dev.to.

\- \*\*Bluesky logs in on every request.\*\* That is fine for this scale. A production version would cache the session token.

\- \*\*The Telegram public check depends on the channel's public web preview\*\* (`t.me/s/<channel>`). If that preview is disabled or both hosts are unreachable, it reports `false` even though the post exists. Private channels always report `false`.

\- \*\*`public\_access` is verified at posting time only.\*\* It does not account for later moderation or deletion.

\- The API has \*\*no authentication or rate limiting\*\* of its own. It is designed to run locally for this assessment.

