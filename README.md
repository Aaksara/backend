# AKSARA backend

Django API for a campus textbook exchange. Students sign up with a university email,
list books, chat with sellers, and hand books over in person on campus. Payment happens
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
books/       books (by title, or by ISBN lookup) and listings
exchanges/   exchange requests: request, accept, hand over
chat/        conversations and messages
cms/         storefront content: home page slides and sections, plus their public read API
console/     the admin console's API under /api/admin/, for the super admin only
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
- **Admin console.** One super admin runs the platform from the frontend's `/admin`. They
  sign in through the normal login, and `GET /api/auth/me/` returns `is_superuser: true`.
  Everything under `/api/admin/` refuses anyone else (`utilities.permission.IsSuperAdmin`).
  `createsuperuser` refuses to create a second super admin; use `changepassword` instead.
- **Storefront content.** The console edits the slides of the site's three sliders (home
  page top, home page safety, sign-in pages) and which home page sections show, in what
  order. The storefront reads them without sign-in from `GET /api/cms/slides/?slider=...`
  and `GET /api/cms/home-sections/`. An empty slider can be given the site's built-in slides,
  to edit from there: with the "Add the built-in slides" button in the console, or
  `python manage.py seed_slides` for every empty slider at once.
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
   `core/wsgi.py`. Under Settings → Environment Variables, set the variables from
   `.env.example`, which explains each one. For production:

   - `DJANGO_DEBUG=false`, `NUM_PROXIES=1`
   - `DJANGO_ALLOWED_HOSTS`: the API domain
   - `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`: the frontend URL
   - `UNIVERSITY_EMAIL_DOMAINS`, `DEFAULT_FROM_EMAIL` (a sender verified in Brevo)
   - `EMAIL_BACKEND=utilities.email_backend.BrevoEmailBackend` (Brevo drops SMTP logins
     from Vercel)
   - `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`: the bucket

   These are secrets. Keep them only in Vercel, never in a committed file:
   `DJANGO_SECRET_KEY`, `DATABASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
   `BREVO_API_KEY` and `REDIS_URL` (optional, so rate limits are shared across instances).
   `.env` and `.env.*` are git-ignored; only `.env.example`, with empty values, is
   committed.

4. **Releases.** Pushing to `main` runs `.github/workflows/ci.yml`: tests, then
   `migrate` on the production database, then the Vercel deploy, in that order, so code
   never goes live before its tables exist. Vercel's own deploys of `main` are switched off
   in `vercel.json`; other branches still get preview deploys. One-time setup, in the
   GitHub repo, add these under Settings → Secrets and variables → Actions:

   - `PRODUCTION_DATABASE_URL`: the Prisma Postgres direct URL
   - `VERCEL_TOKEN`: from Vercel → Account Settings → Tokens
   - `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`: from `.vercel/project.json` after `vercel link`

   Also create a `production` environment (Settings → Environments); add required
   reviewers there to approve each release by hand.

   When a migration drops or renames a column, release the code that stops using it first,
   and the migration in a later release.

5. **First run.** Seed the slides and create the super admin, who signs in to the
   frontend's `/admin`:

   ```bash
   # With the AWS_* storage variables set too, so the images go to the bucket:
   DATABASE_URL='<prisma direct url>' python manage.py seed_slides
   DATABASE_URL='<prisma direct url>' python manage.py createsuperuser
   ```

   There can only be one super admin. To change its password later, run
   `changepassword <email>` the same way.

Limits on Vercel: request bodies are capped at 4.5 MB (image uploads are limited to 4 MB),
and each request has a time limit, so the ISBN lookup times out after 4 seconds per catalogue.
