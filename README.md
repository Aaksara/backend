# AKSARA backend

Django API for a campus textbook exchange. Students sign up with a university email,
list books by ISBN, chat with sellers, and agree on an on-campus meetup. Payment happens
in person.

Stack: Django, Django REST Framework, PostgreSQL, Channels (WebSockets) and Redis.

Every endpoint is documented in the [Bruno](https://www.usebruno.com/) collection in the
[apis repo](https://github.com/Aaksara/apis).

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
core/        Django project: settings, URLs, ASGI routing
accounts/    users, sign-up, email verification, JWT login
books/       books (ISBN lookup) and listings
exchanges/   exchange requests and meetup locations
chat/        conversations, messages, WebSockets
utilities/   shared code: base model, pagination, permissions, error handler, health check
tests/
```

## How it works

- **Sign-in.** `POST /api/auth/login/` returns `access` and `refresh` JWTs and the user.
  Send `Authorization: Bearer <access>` on other requests. `POST /api/auth/token/refresh/`
  with `{"refresh": ...}` returns new tokens, and `POST /api/auth/logout/` revokes one.
- **Listings** are `sell`, `exchange` or `donate`, and move from `available` to
  `reserved` to `completed`, or to `withdrawn`.
- **Exchanges** go from `pending` to `accepted` to `completed`, or end as `rejected` or
  `cancelled`. Accepting reserves the book(s), and completing closes the other requests.
- **Chat.** Connect to `ws://<host>/ws/chat/<conversation_id>/?token=<access>` or
  `ws://<host>/ws/inbox/?token=<access>`. Messages are JSON objects like
  `{"type": "message", "body": "..."}`.

## Production

Set these environment variables (see `.env.example`):

- `DJANGO_DEBUG=false` and a long random `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
- `REDIS_URL`, so chat and rate limits work across processes
- `NUM_PROXIES`: the number of reverse proxies in front of Django
- the SMTP `EMAIL_*` settings

Serve `/media/` (uploaded images) from the `media` volume with your reverse proxy. Run
migrations from one replica only; set `RUN_MIGRATIONS=0` on the others.
