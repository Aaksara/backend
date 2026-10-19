# Frontend Integration Guide

How the BookX backend is organised from a client's point of view: what to call, in
what order, and what comes back. For exact request/response schemas, the live
OpenAPI docs are the source of truth:

- Swagger UI: `http://localhost:8000/api/docs/`
- OpenAPI schema: `http://localhost:8000/api/schema/` (feed it to e.g.
  `openapi-typescript` to generate TypeScript types)

## 1. The big picture

```
Frontend (http://localhost:3000)
   │
   ├── REST  ──►  http://localhost:8000/api/...      JSON, JWT in Authorization header
   └── WS    ──►  ws://localhost:8000/ws/...         JWT as the "bearer" subprotocol
```

The API is split into five areas, one per backend app:

| Area | Base path | What it covers |
|---|---|---|
| Auth & account | `/api/auth/` | Register, verify email, login, tokens, profile, passwords |
| Catalogue | `/api/books/` | Books by ISBN (shared by all listings of that edition) |
| Listings | `/api/listings/` | A student's copy of a book for sale / swap / donation |
| Exchanges | `/api/exchanges/`, `/api/meetup-locations/` | Requesting a listing and arranging the hand-over |
| Chat | `/api/conversations/`, `/ws/chat/`, `/ws/inbox/` | Buyer ↔ seller messaging, live updates |

`GET /api/health/` (no auth) returns `{"status": "ok"}`.

Core relationships:

```
User ──< Listing >── Book            one Book (ISBN) has many Listings
User ──< ExchangeRequest >── Listing  a request for someone else's listing
              └── offered_listing     (swaps: one of the requester's own listings)
User ──< Conversation >── Listing     one conversation per (listing, buyer)
              └──< Message
```

## 2. Conventions

**Authentication.** Every endpoint needs `Authorization: Bearer <access>` except
register, verify-email, resend-verification, login, token refresh, and the two
password-reset endpoints.

**Content type.** JSON everywhere, except image uploads (`multipart/form-data`).

**Pagination.** List endpoints return:

```json
{ "count": 42, "next": "http://…?page=2", "previous": null, "results": [ … ] }
```

Use `?page=N` and `?page_size=N` (default 20, max 100). Exception:
`GET /api/meetup-locations/` returns a plain array.

**Errors.** Every error body is an object in one of two shapes:

```json
{ "detail": "Human-readable message." }
{ "price": ["A selling price is required."], "listing": ["This listing is not available."] }
```

Field errors are keyed by the request field name, so they can be shown next to
form inputs. Some errors also carry a machine-readable `code` (see login below).

| Status | Meaning |
|---|---|
| 400 | Validation error (field errors or `detail`) |
| 401 | Missing/expired access token, or bad credentials |
| 403 | Authenticated but not allowed (e.g. editing someone else's listing) |
| 404 | Not found, **or not visible to you** (e.g. another user's withdrawn listing) |
| 429 | Rate limited. Auth endpoints allow 10 requests/min per client |

**Data formats.** Money (`price`, `offered_price`) is a decimal **string**, e.g.
`"25.00"`. Timestamps are ISO 8601 in UTC, e.g. `"2026-10-12T14:30:00Z"`; send
`meetup_time` the same way (include the timezone). Image fields are absolute URLs.

## 3. Auth flows

### Registration and email verification

```
1. POST /api/auth/register/
   { "email": "jane@university.edu", "full_name": "Jane Doe", "password": "…",
     "student_id": "", "department": "", "phone": "" }        → 201
2. Backend emails a link:  {FRONTEND_URL}/verify-email?uid=<uid>&token=<token>
3. Your /verify-email page reads uid + token from the URL and calls
   POST /api/auth/verify-email/  { "uid": "…", "token": "…" }  → 200
4. User can now log in.
```

- Only university email domains are accepted (400 on `email` otherwise).
- Password strength errors are returned on the `password` field.
- "Resend email" button: `POST /api/auth/resend-verification/ { "email": "…" }`.
  It always returns 200 with a generic message, whether or not the account exists.

In development, emails are printed to the backend log (`docker compose logs web`)
instead of being sent, so copy the link from there.

### Login and tokens

```
POST /api/auth/login/  { "email": "…", "password": "…" }
→ 200 { "access": "<jwt>", "refresh": "<jwt>", "user": { …profile… } }
```

- Wrong credentials: `401 {"detail": "No active account found with the given credentials"}`.
- Unverified email: `401 {"detail": "Please verify your email address before logging in.", "code": "email_not_verified"}`.
  Check `code` to show a "resend verification" prompt.

Token lifetimes: **access 30 min**, **refresh 7 days**.

**Refreshing:**

```
POST /api/auth/token/refresh/  { "refresh": "<refresh>" }
→ 200 { "access": "<new access>", "refresh": "<new refresh>" }
```

Refresh tokens **rotate**: each refresh returns a new refresh token and the old one
stops working. Always store the new one. A typical client:

1. Call the API with the access token.
2. On 401, call refresh once, store both new tokens, and retry the request.
3. If refresh also returns 401, clear the tokens and send the user to login.

If several requests can fail at the same time, make sure only one refresh call
runs and the rest wait for it. Two parallel refreshes with the same token will log
the user out.

**Logout:** `POST /api/auth/logout/ { "refresh": "<refresh>" }` → 205. Then drop both tokens.

**Password changes revoke every session.** After a password change or reset, all
existing refresh tokens stop working, so the user must log in again on every device.

### Password reset

```
1. POST /api/auth/password/reset/ { "email": "…" }      → 200 (always, generic message)
2. Email link: {FRONTEND_URL}/reset-password?uid=<uid>&token=<token>
3. POST /api/auth/password/reset/confirm/
   { "uid": "…", "token": "…", "new_password": "…" }    → 200
```

An invalid or expired link returns 400 `{"detail": "Invalid or expired link."}`.

### Profile

| Call | Notes |
|---|---|
| `GET /api/auth/me/` | `id, email, full_name, student_id, department, phone, avatar, is_email_verified, date_joined` |
| `PATCH /api/auth/me/` | Any of `full_name, student_id, department, phone, avatar`. `email` cannot be changed. Send `avatar` as multipart (max 5 MB). |
| `POST /api/auth/password/change/` | `{ "current_password", "new_password" }` |
| `GET /api/auth/users/{id}/` | Public profile of another student: `id, full_name, department, avatar, date_joined` |

## 4. Books and listings

### Creating a listing (typical "Sell a book" screen)

```
1. User enters an ISBN (10 or 13 digits, hyphens OK).
2. GET /api/books/lookup/?isbn=978-0-262-03384-8
   → 200 Book       (found locally, or imported from Open Library / Google Books)
   → 404            (unknown everywhere: show a manual form)
   → 400 on "isbn"  (not a valid ISBN)
3. If 404: POST /api/books/ { "isbn_13": "<what the user typed>", "title": "…", "authors": "…", … }
4. POST /api/listings/ { "book_id": <book.id>, "condition": "good",
                         "listing_type": "sell", "price": "25.00", … }
5. Optional photos: POST /api/listings/{id}/images/ (multipart, field "image")
```

### Book

`id, isbn_13, isbn_10, title, subtitle, authors, publisher, published_year, edition,
page_count, cover_url, description, available_listings, lowest_price`

- `authors` is a single comma-separated string.
- `available_listings` / `lowest_price` summarise the book's available listings, so a
  catalogue page can show "3 copies from $12.00".
- `GET /api/books/?search=…&ordering=title|published_year|available_listings|lowest_price`
- Only staff can edit books. Students can create them.

### Listing

| Field | Read | Write | Notes |
|---|---|---|---|
| `id` | ✓ | | |
| `book` | ✓ (summary object) | | `id, isbn_13, title, authors, edition, cover_url` |
| `book_id` | | ✓ (required on create) | Cannot be changed after create |
| `seller` | ✓ (public user) | | Set automatically |
| `is_owner` | ✓ | | `true` if the current user is the seller. Use it to show edit controls |
| `condition` | ✓ | ✓ | `new`, `like_new`, `good`, `fair`, `poor` |
| `listing_type` | ✓ | ✓ | `sell` (default), `exchange`, `donate` |
| `price` | ✓ | ✓ | Required for `sell`; forced to `null` for `donate` |
| `description` | ✓ | ✓ | |
| `course_code` | ✓ | ✓ | Stored upper-case, e.g. `CS101` |
| `preferred_location` | ✓ (id) | ✓ | A meetup location id, or `null` |
| `status` | ✓ | ✓ (limited) | See below |
| `images` | ✓ | | `[{ id, image, uploaded_at }]` |
| `created_at`, `updated_at` | ✓ | | |

**Status:** `available → reserved → completed`, or `withdrawn`.
Sellers can only switch between `available` and `withdrawn`. `reserved` and
`completed` are set by exchanges, and while a listing is in either state the seller
can't change its status.

**Endpoints:**

| Call | Notes |
|---|---|
| `GET /api/listings/` | Browse. Shows only `available` listings unless you pass `status` |
| `GET /api/listings/mine/` | All of the current user's listings, any status |
| `GET /api/listings/{id}/` | Withdrawn listings are 404 for everyone except the seller |
| `POST /api/listings/` | Create |
| `PATCH /api/listings/{id}/` | Seller only |
| `DELETE /api/listings/{id}/` | Seller only. 400 if reserved. If it has exchange history it is set to `withdrawn` instead of deleted (still 204) |
| `POST /api/listings/{id}/images/` | Seller only, multipart `image`, max 5 images, 5 MB each |
| `DELETE /api/listings/{id}/images/{image_id}/` | Seller only |

**Browse filters** (query params, combinable):

| Param | Example |
|---|---|
| `search` | `?search=algorithms` (title, authors, ISBN, course code, description) |
| `isbn` | `?isbn=0262033844` (any ISBN format) |
| `title`, `author` | partial, case-insensitive |
| `course_code` | exact, case-insensitive |
| `condition`, `listing_type`, `status` | repeat for multiple: `?condition=new&condition=like_new` |
| `min_price`, `max_price` | `?min_price=5&max_price=30` |
| `book`, `seller`, `preferred_location` | ids |
| `ordering` | `price`, `-price`, `created_at`, `-created_at` (default newest first) |

## 5. Exchanges

An exchange is one student asking for another student's listing. Payment happens in
person; the backend only tracks agreement and hand-over.

```
           requester creates
                 │
              pending ──── seller rejects ───► rejected
                 │   └──── requester cancels ─► cancelled
          seller accepts
       (location + future time)
                 │
             accepted ──── either cancels ────► cancelled   (listings back to available)
                 │
          either completes
                 │
             completed                          (listings → completed; other pending
                                                 requests for them auto-rejected)
```

| Call | Who | Body |
|---|---|---|
| `GET /api/meetup-locations/` | anyone | Plain array of `{ id, name, description }` |
| `POST /api/exchanges/` | requester | `{ "listing": id, "offered_price"?: "20.00", "offered_listing"?: id, "message"?: "…" }` |
| `GET /api/exchanges/` | both sides | Filters: `role=requester\|seller`, `status` (multi), `listing` |
| `GET /api/exchanges/{id}/` | both sides | |
| `POST /api/exchanges/{id}/accept/` | seller | `{ "meetup_location": id, "meetup_time": "2026-10-12T14:30:00Z" }` |
| `POST /api/exchanges/{id}/reject/` | seller | — |
| `POST /api/exchanges/{id}/cancel/` | requester (pending/accepted), seller (accepted only) | — |
| `POST /api/exchanges/{id}/complete/` | either | — |

Rules on create, by listing type:

- `sell`: `offered_price` defaults to the listing price if omitted.
- `exchange`: `offered_listing` is required and must be one of your own available listings.
- `donate`: `offered_price` is ignored.

You can't request your own listing, request an unavailable one, or have two active
requests for the same listing.

Each exchange in a response includes `listing_detail`, `offered_listing_detail`,
`meetup_location_detail`, `requester`, `seller`, and **`role`** (`"seller"` or
`"requester"`, from the current user's point of view). Use `role` together with
`status` to decide which buttons to show:

| `status` | `role = seller` | `role = requester` |
|---|---|---|
| `pending` | Accept, Reject | Cancel |
| `accepted` | Complete, Cancel | Complete, Cancel |
| other | — | — |

All transition endpoints return the updated exchange.

## 6. Chat

### REST

| Call | Notes |
|---|---|
| `POST /api/conversations/ { "listing": id }` | Start a chat with a listing's seller. Returns the existing conversation (200) if there already is one, else 201 |
| `GET /api/conversations/` | Your conversations, most recently active first. Filter `?listing=` |
| `GET /api/conversations/{id}/` | |
| `GET /api/conversations/{id}/messages/` | History, **newest first**, paginated |
| `POST /api/conversations/{id}/messages/ { "body": "…" }` | Send (max 2000 chars). Also pushed over WebSockets |
| `POST /api/conversations/{id}/read/` | Mark the other person's messages read → `{ "marked_read": n }` |

A conversation has `id, listing_detail, buyer, seller, last_message, unread_count,
created_at, updated_at`. A message has `id, conversation, sender (user id), body,
created_at, read_at`.

### WebSockets

```
ws://localhost:8000/ws/chat/<conversation_id>/   one open conversation
ws://localhost:8000/ws/inbox/                    new messages anywhere (badges)
```

Browsers cannot set headers on a WebSocket, so send the **access** token as a
subprotocol (it stays out of proxy logs, unlike a query string):

```js
new WebSocket(url, ["bearer", accessToken]);
```

The page's origin must be listed in `CORS_ALLOWED_ORIGINS`. The token is checked only
when the socket connects, so an open socket stays up after the token expires. After a
reconnect, send a fresh token.

**Close codes:** `4401` missing/invalid token (refresh, then reconnect),
`4403` not a participant (don't retry).

**Chat socket, client → server:**

```json
{ "type": "message", "body": "Is this still available?" }
{ "type": "typing", "is_typing": true }
{ "type": "read" }
```

**Chat socket, server → client:**

```json
{ "type": "message", "message": { "id": 1, "conversation": 3, "sender": 7, "body": "…", "created_at": "…", "read_at": null } }
{ "type": "typing", "user": 7, "is_typing": true }
{ "type": "read", "reader": 7, "read_at": "…" }
{ "type": "error", "detail": "…" }
```

- Your own messages are echoed back as `message` events. Add messages to the UI from
  the socket event, not optimistically, to avoid duplicates.
- `typing` events are not sent back to the user who is typing.
- Each user can send 30 messages a minute over sockets; beyond that you get an `error`.
- The **inbox** socket only sends `{ "type": "message", "message": {…} }` for messages
  from the *other* person. Use it to update `unread_count` and conversation order.

Suggested chat screen flow: load history with `GET …/messages/`, open the chat
socket, send `{"type":"read"}` while the conversation is on screen, and close the
socket when leaving the page.

## 7. Local setup for frontend work

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py seed_meetup_locations
docker compose exec web python manage.py createsuperuser   # admin at /admin/
```

Defaults that matter to the frontend (all set in `.env`):

| Setting | Default | Purpose |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Origins allowed to call the API and open WebSockets |
| `FRONTEND_URL` | `http://localhost:3000` | Base for email links (`/verify-email`, `/reset-password`) |
| `UNIVERSITY_EMAIL_DOMAINS` | `university.edu` | Domains allowed to register |

If your dev server runs on a different port or host, update `CORS_ALLOWED_ORIGINS`,
then restart the `web` container.
