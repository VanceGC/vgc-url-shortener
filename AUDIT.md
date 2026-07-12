# VGC URL Shortener — Project Audit

Audit of the repository as of July 2026 (`main` @ 9a2743e), covering the Flask
backend (`vgc-url-shortener/`), React frontend (`vgc-frontend/`), and deployment
configuration. Findings are ordered by severity.

## Critical

### 1. The backend as committed crashes on startup — FIXED in this branch
`src/routes/url.py` contained a duplicated copy of every route (lines 451–847):
dead code pasted after `redirect_url`'s `return`, followed by a second
registration of every endpoint on the same blueprint. Flask refuses duplicate
endpoint names, so importing the app raised:

```
AssertionError: View function mapping is overwriting an existing endpoint function: url.get_url_info
```

Whatever is running in production is not what was committed. The duplicate
block has been removed on this branch; the app now imports cleanly with 27
routes (verified).

### 2. Admin password hardcoded in source
`src/routes/auth.py:11` — `AUTH_PASSWORD = "B33fst3\/\/"` is committed to git.
Anyone with repo access owns the service, and git history retains it even after
removal. **Recommendation:** move it to an environment variable, rotate the
password, and consider the current one burned.

### 3. API key is ephemeral and inconsistent across workers
`API_KEY` falls back to `secrets.token_urlsafe(32)` generated at import time
when `VGC_API_KEY` is unset (`auth.py:15`). Consequences:
- The key changes on every server restart, silently breaking N8N/scripts/apps.
- Under gunicorn with `WORKERS=4` (per `.env.example`), each worker generates a
  *different* key, so requests randomly fail depending on which worker serves them.
- `POST /api/auth/regenerate-api-key` only mutates the in-memory global of one
  worker and is lost on restart.

**Recommendation:** always set `VGC_API_KEY` in the environment (the iOS app
depends on a stable key), or persist keys in the database.

## High

### 4. No rate limiting or brute-force protection on login
`/api/auth/login` accepts unlimited password attempts. `.env.example` advertises
`RATE_LIMIT_*` flags, but nothing in the code reads them. **Recommendation:**
add Flask-Limiter (e.g. `5/minute` on login).

### 5. SSRF via automatic title fetching
`get_page_title()` (`url.py:18`) makes a server-side GET to any user-supplied
URL when creating/editing links. An authenticated caller can probe internal
networks/cloud metadata (e.g. `http://169.254.169.254/`). Redirects are also
followed by default. **Recommendation:** resolve and reject private/link-local
addresses, disable redirects, and cap response size.

### 6. Session cookies not marked Secure
`SESSION_COOKIE_SECURE = False` (`main.py:23`) even though the site is
HTTPS-only behind Caddy. The session cookie (which grants full admin) can leak
over plaintext HTTP. Also, `SECRET_KEY` falls back to a hardcoded default
(`main.py:19`) — with it, anyone can forge session cookies.

### 7. Unauthenticated user CRUD API
`src/routes/user.py` exposes `/api/users` (list/create/update/delete) with **no
authentication**. It appears to be unused boilerplate. **Recommendation:**
delete the blueprint (and `src/models/user.py`'s `User` model) or protect it
with `@auth_required`.

## Medium

### 8. Password comparison is weak
`check_password` compares unsalted SHA-256 hashes with `==` — hashing both sides
of the comparison adds nothing, and `==` is not constant-time. Use
`hmac.compare_digest` (and a salted KDF if passwords are ever stored).

### 9. "Daily stats for last 30 days" only returns today
`get_url_stats` filters `Click.clicked_at >= today at 00:00` (`url.py:321`), so
the "last 30 days" query returns at most one day. The chart data the API
promises is never produced. Same pattern in `Url.to_dict(include_stats=True)`
is intentional (clicks today) but the stats endpoint is not.

### 10. `unique_clicks` is never computed correctly
`UrlStats.unique_clicks` is set to 1 when a row is created and never updated on
subsequent clicks (`url.py:439-445`).

### 11. Redirect route swallows analytics failures with a 500
The click-tracking write in `redirect_url` isn't wrapped in try/except — a DB
hiccup turns a redirect (the product's core function) into a 500. Track
best-effort and always redirect.

### 12. `main.py` short-code fallback conflicts with SPA routes
`serve()` treats any 3+ char alphanumeric path as a short code (`main.py:68`),
so SPA routes like `/dashboard` are looked up as short codes (and 404 from the
redirect handler instead of serving the SPA).

### 13. Duplicate redirect registration
The redirect route is registered both at root level (`main.py:39`) and under the
`url_bp` prefix as `/api/<short_code>`, which shadows unknown `/api/...` paths.

## Low / housekeeping

- **Broad `except Exception` blocks** in `shorten_url`/`edit_url` hide real
  errors (they also masked the duplicate-code bug); log the exception at minimum.
- **`search=` uses `LIKE %term%`** on four columns with no index — fine at small
  scale, worth FTS later.
- **`.DS_Store` committed** at repo root; add it to `.gitignore`.
- **Built frontend committed twice** (`vgc-frontend/dist/` and
  `vgc-url-shortener/src/static/`) — easy for the two to drift; build in CI or
  a Docker multi-stage instead.
- **Watchtower** in `docker-compose.yml` has Docker-socket access (effectively
  root on the host) to auto-update a locally-built image it can't actually
  update — consider removing it.
- **`flask-app` `depends_on: caddy`** is backwards; Caddy proxies to Flask.
- **SQLite + 4 gunicorn workers** is workable at this scale but expect
  `database is locked` under concurrent writes; enable WAL mode.

## What's in good shape

- Clean REST surface with pagination, search, sorting, soft delete/restore,
  edit history, and per-link stats — the iOS app maps onto it 1:1.
- Dual auth (session cookie for the web UI, `X-API-Key` header for clients) is
  a sensible design; the iOS app uses the API-key path exclusively.
- CORS is restricted to known origins with credentials support.
- Docker/Caddy deployment with healthchecks and persisted volumes is solid.
