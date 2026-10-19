# BookX backend

Django API for a campus textbook exchange. Students sign up with a university email,
list books by ISBN, chat with sellers, and agree on an on-campus meetup. Payment happens
in person.

Stack: Django, Django REST Framework, PostgreSQL, Channels (WebSockets) and Redis.

Every endpoint is documented in the [Bruno](https://www.usebruno.com/) collection in
[`apis/`](apis/): open that folder in Bruno and pick the **Local** environment.

## Run it

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py seed_meetup_locations
docker compose exec web python manage.py createsuperuser
```

- Admin: http://localhost:8000/admin/
- Emails (verification, password reset) are printed in `docker compose logs web`.

## Test

```bash
pytest                                  # needs Postgres at DATABASE_URL
ruff check . && ruff format --check .
```

## Layout

```
apis/            Bruno collection: every endpoint with an example and its docs
config/          settings, URLs, ASGI routing
apps/core/       shared base model, pagination, health check
apps/accounts/   users, sign-up, email verification, cookie login
apps/books/      books (ISBN lookup) and listings
apps/exchanges/  exchange requests and meetup locations
apps/chat/       conversations, messages, WebSockets
tests/
```

## How it works

- **Sign-in.** `POST /api/auth/login/` sets two httpOnly cookies: the access token and
  the refresh token. The browser sends them automatically (`credentials: "include"`).
  `POST /api/auth/token/refresh/` renews them, and `POST /api/auth/logout/` clears them.
  Writes made with the cookies must come from an origin in `CORS_ALLOWED_ORIGINS`.
- **Listings** are `sell`, `exchange` or `donate`, and move from `available` to
  `reserved` to `completed`, or to `withdrawn`.
- **Exchanges** go from `pending` to `accepted` to `completed`, or end as `rejected` or
  `cancelled`. Accepting reserves the book(s), and completing closes the other requests.
- **Chat.** Connect to `ws://<host>/ws/chat/<conversation_id>/` or `ws://<host>/ws/inbox/`.
  The access cookie signs you in. Messages are JSON objects like
  `{"type": "message", "body": "..."}`.

## Production

Set these environment variables (see `.env.example`):

- `DJANGO_DEBUG=false` and a long random `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
- `REDIS_URL`, so chat and rate limits work across processes
- `NUM_PROXIES`: the number of reverse proxies in front of Django
- the SMTP `EMAIL_*` settings

Serve `/media/` (uploaded images) from the `media` volume with your reverse proxy. Run
migrations from one replica only; set `RUN_MIGRATIONS=0` on the others. Serve the
frontend and the API under the same parent domain (for example `app.example.com` and
`api.example.com`) so the browser sends the auth cookies.
