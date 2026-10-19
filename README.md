# BookX — Student Book Exchange (Backend)

REST + WebSocket API for a campus textbook exchange. Students with an institutional
email can list books by ISBN, search and filter listings, chat in real time, and
arrange in-person hand-overs at approved campus locations. No online payments:
money changes hands in person (cash / digital wallet).

**Stack:** Django 5.2 · Django REST Framework · PostgreSQL · SimpleJWT · Django Channels
(Redis) · drf-spectacular (OpenAPI) · Docker · GitHub Actions

## Quick start (Docker)

```bash
cp .env.example .env            # optional; compose has sensible dev defaults
docker compose up -d --build    # web :8000, postgres :5434, redis
docker compose exec web python manage.py seed_meetup_locations
docker compose exec web python manage.py createsuperuser
```

- API docs (Swagger): http://localhost:8000/api/docs/
- OpenAPI schema: http://localhost:8000/api/schema/
- Admin: http://localhost:8000/admin/

In development, verification and password-reset emails are printed to the `web`
container log (`docker compose logs web`).

## Local run (without Docker for the app)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d db          # or point DATABASE_URL at your own Postgres
python manage.py migrate
python manage.py runserver       # daphne serves both HTTP and WebSockets
```

Without `REDIS_URL`, an in-memory channel layer is used (fine for one process).

## Tests & quality

```bash
pytest                 # needs Postgres reachable via DATABASE_URL
ruff check . && ruff format --check .
```

CI (`.github/workflows/ci.yml`) runs lint, a missing-migration check, Django
deploy checks, the test suite against Postgres, and a Docker build.

## Project layout

```
config/            settings, URLs, ASGI (HTTP + WebSocket routing)
apps/core/         shared base model, pagination, permissions, health check
apps/accounts/     custom User (email login), registration, verification, JWT
apps/books/        Book catalogue, ISBN normalisation & lookup, Listings, images
apps/exchanges/    MeetupLocation, ExchangeRequest lifecycle
apps/chat/         Conversations, Messages, WebSocket consumers
tests/             pytest suite
```

## Domain rules

- **University only:** registration requires an email on `UNIVERSITY_EMAIL_DOMAINS`
  (subdomains allowed); login is refused until the email is verified.
- **ISBN:** ISBN-10/13 (with or without hyphens) is validated and stored as ISBN-13.
  `GET books/lookup/?isbn=` imports unknown ISBNs from Open Library, falling back to
  Google Books; books not found anywhere can be added with `POST books/`. A listing is
  then created with that book's `book_id`.
- **Listings** are `sell` (price required), `exchange` (swap for another book) or
  `donate`. Status: `available → reserved → completed`, or `withdrawn`. Sellers can only
  toggle `available`/`withdrawn`; the rest is driven by exchanges.
- **Exchanges:** `pending → accepted → completed` (or `rejected` / `cancelled`).
  Accepting requires an active campus meetup location and a future time, and reserves
  the listing (and the offered book in a swap). Completing marks both books completed
  and auto-rejects other pending requests. Transitions lock rows to prevent
  double-booking.

## API overview

All endpoints are under `/api/` and require `Authorization: Bearer <access>` unless noted.

| Area | Endpoints |
|---|---|
| Auth (public) | `POST auth/register/`, `auth/verify-email/`, `auth/resend-verification/`, `auth/login/`, `auth/token/refresh/`, `auth/password/reset/`, `auth/password/reset/confirm/` |
| Account | `GET/PATCH auth/me/`, `POST auth/password/change/`, `POST auth/logout/`, `GET auth/users/{id}/` |
| Catalogue | `GET/POST books/`, `GET books/{id}/`, `GET books/lookup/?isbn=` |
| Listings | `GET/POST listings/`, `GET/PATCH/DELETE listings/{id}/`, `GET listings/mine/`, `POST listings/{id}/images/`, `DELETE listings/{id}/images/{image_id}/` |
| Exchanges | `GET meetup-locations/`, `GET/POST exchanges/`, `GET exchanges/{id}/`, `POST exchanges/{id}/accept|reject|cancel|complete/` |
| Chat | `GET/POST conversations/`, `GET/POST conversations/{id}/messages/`, `POST conversations/{id}/read/` |

**Listing filters:** `search`, `isbn`, `title`, `author`, `course_code`, `condition`
(multi), `listing_type` (multi), `status` (multi; default `available`), `min_price`,
`max_price`, `book`, `seller`, `preferred_location`, `ordering=price|-price|created_at|-created_at`.

**Exchange filters:** `role=requester|seller`, `status`, `listing`.

## Real-time chat (WebSocket)

Connect with the JWT access token as the `bearer` subprotocol, from an origin listed in
`CORS_ALLOWED_ORIGINS`:

```js
new WebSocket("ws://localhost:8000/ws/chat/<conversation_id>/", ["bearer", access]);
new WebSocket("ws://localhost:8000/ws/inbox/", ["bearer", access]); // new-message feed
```

Client → server: `{"type":"message","body":"..."}`, `{"type":"typing","is_typing":true}`, `{"type":"read"}`
Server → client: `{"type":"message","message":{...}}`, `{"type":"typing",...}`, `{"type":"read",...}`, `{"type":"error",...}`

Messages sent via `POST conversations/{id}/messages/` are broadcast to sockets too.
Missing/expired tokens are closed with code 4401, non-participants with 4403. Sockets
allow 30 messages per user per minute.

## Production

- Set `DJANGO_DEBUG=false`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
  `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS` and an SMTP `EMAIL_*` setup.
- Set `REDIS_URL`: chat fan-out and rate limits must be shared between processes.
- Set `NUM_PROXIES` to the number of proxies in front of Django that append to
  `X-Forwarded-For` (browser → TLS proxy → Next.js → Django is `1`). Otherwise every
  request appears to come from the proxy and shares one rate limit.
- Terminate TLS at a reverse proxy and turn on `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS`.
- Static files are served by WhiteNoise. Uploaded media (`/media/`) is not served when
  `DEBUG` is off: point the reverse proxy at the `media` volume.
- Migrations run on container start; set `RUN_MIGRATIONS=0` on all but one replica.

Frontend developers: see [docs/FRONTEND_INTEGRATION.md](docs/FRONTEND_INTEGRATION.md).
