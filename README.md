# AKSARA backend

Django API for a campus textbook exchange. Students sign up with a university email,
list books by ISBN, chat with sellers, and agree on an on-campus meetup. Payment happens
in person.

Stack: Django, Django REST Framework, PostgreSQL (Prisma Postgres in production), and
JWT auth. Deployed on Vercel.

Every endpoint is documented in the [Bruno](https://www.usebruno.com/) collection in the
[apis repo](https://github.com/Aaksara/apis).

## Run it locally

You need Python 3.12 and Docker (for PostgreSQL).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d db
python manage.py migrate
python manage.py seed_meetup_locations
python manage.py createsuperuser
python manage.py runserver
```

- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/
- Emails (verification, password reset) are printed in the terminal.

## Test

```bash
pytest                                  # needs the local database running
ruff check . && ruff format --check .
```

## Layout

```
core/        Django project: settings, URLs, WSGI (Vercel entry point)
accounts/    users, sign-up, email verification, JWT login
books/       books (ISBN lookup) and listings
exchanges/   exchange requests and meetup locations
chat/        conversations and messages
utilities/   shared code: base model, pagination, permissions, error handler, health check
tests/
vercel.json  runs core/wsgi.py on Vercel's Python runtime
```

## How it works

- **Sign-in.** `POST /api/auth/login/` returns `access` and `refresh` JWTs and the user.
  Send `Authorization: Bearer <access>` on other requests. `POST /api/auth/token/refresh/`
  with `{"refresh": ...}` returns new tokens, and `POST /api/auth/logout/` revokes one.
- **Listings** are `sell`, `exchange` or `donate`, and move from `available` to
  `reserved` to `completed`, or to `withdrawn`.
- **Exchanges** go from `pending` to `accepted` to `completed`, or end as `rejected` or
  `cancelled`. Accepting reserves the book(s), and completing closes the other requests.
- **Chat** is plain REST. The app polls `GET /api/conversations/` (unread counts) and
  `GET /api/conversations/{id}/messages/` for new messages.

## Deploy (Vercel + Prisma Postgres)

1. **Database.** Create a Prisma Postgres database (Vercel → Storage → Prisma Postgres, or
   console.prisma.io). Copy its **direct** connection string:
   `postgres://...@db.prisma.io:5432/postgres?sslmode=require`. Django cannot use the
   `prisma+postgres://` (Accelerate) URL.
2. **Image storage.** Vercel has no lasting disk, so create an S3-compatible bucket, e.g.
   Cloudflare R2, and an access key for it.
3. **Vercel project.** Import this repo. Framework preset: **Other**. `vercel.json` runs
   `core/wsgi.py`. Add these environment variables (see `.env.example`):

   | Variable | Value |
   | --- | --- |
   | `DJANGO_DEBUG` | `false` |
   | `DJANGO_SECRET_KEY` | a long random string |
   | `DJANGO_ALLOWED_HOSTS` | the API domain, e.g. `aksara-api.vercel.app` |
   | `DATABASE_URL` | the Prisma Postgres direct URL |
   | `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | the frontend URL, e.g. `https://aksara.vercel.app` |
   | `UNIVERSITY_EMAIL_DOMAINS` | your university's email domains |
   | `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL` | the bucket |
   | `EMAIL_BACKEND` | `utilities.email_backend.BrevoEmailBackend` (Brevo drops SMTP logins from Vercel) |
   | `BREVO_API_KEY` | a Brevo API key (`xkeysib-...`, under SMTP & API → API Keys) |
   | `DEFAULT_FROM_EMAIL` | a sender verified in Brevo, e.g. `Akshara <you@example.com>` |
   | `NUM_PROXIES` | `1` |
   | `REDIS_URL` | optional, recommended: an Upstash Redis URL, so rate limits are shared |

4. **Migrations.** Vercel does not run them. After each deploy that adds a migration, run
   from your machine:

   ```bash
   DATABASE_URL='<prisma direct url>' python manage.py migrate
   ```

   The first time, also run `seed_meetup_locations` and `createsuperuser` the same way.

Limits on Vercel: request bodies are capped at 4.5 MB (image uploads are limited to 4 MB),
and each request has a time limit, so the ISBN lookup times out after 4 seconds per catalogue.
