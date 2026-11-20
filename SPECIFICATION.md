# Kudos System Specification

**Product:** Kudos, a feature of the internal employee portal  
**Candidate:** Anthony Jones  
**Context:** Datacom Automation AI Accelerator — Task 2, Create a process flow  
**Status:** Approved for implementation  
**Date:** 20 November 2026 (America/New_York)

This document is the single source of truth for the feature. It was produced with a
general-purpose agentic coding assistant from the high-level request below, then
reviewed and refined before any application code was written. The refinement step
added authentication, content moderation, and the edge cases the original request
left out.

**Initial request:**

> Create a feature for our internal web app that allows users to give 'kudos' to
> their colleagues. A user should be able to select another user from a list,
> write a short message of appreciation, and submit it. There should also be a
> public feed on the main dashboard where all recently submitted kudos are visible.

**Intended public repository name:** `kudos-internal-portal`  
The local project lives in this directory. It has not been pushed. Add the public
clone URL here after the repository is published.

---

## Functional Requirements

### User Stories

1. As a signed-in employee, I can authenticate with my username and password, stay
   signed in for the session, and sign out.
2. As a signed-in employee, I can select another user from a dropdown list of
   colleagues.
3. As a signed-in employee, I can write a message of appreciation of at most 500
   characters.
4. As a signed-in employee, I can submit the kudos, which is stored in the
   database and then appears on the public feed.
5. As a signed-in employee, I can view a feed of recent kudos on the dashboard.
   Only messages that have not been hidden by an administrator are shown.
6. As an administrator, I can hide or delete inappropriate kudos messages, and I
   can restore a hidden message so it appears on the feed again.

### Acceptance Criteria

**Story 1 — Authentication**

- Visiting any page other than the login page, or any API endpoint other than
  `POST /api/login` and `GET /api/csrf`, requires a valid session.
- A correct username and password (case-insensitive username) creates a session
  and redirects to the dashboard, or returns the current user as JSON from the
  API.
- An incorrect username or password returns a generic error and does not reveal
  whether the username exists.
- Signing out clears the session. A later request is treated as unauthenticated.
- Passwords are stored only as hashes, never in plain text.

**Story 2 — Colleague list**

- The give-kudos form and `GET /api/colleagues` list every user except the
  signed-in user, sorted by display name.
- Each entry includes `id`, `username`, and `display_name`.
- The list is a dropdown (or equivalent select control) on the give-kudos page.

**Story 3 — Message**

- The message is required.
- After trimming leading and trailing whitespace, the message must be between 1
  and 500 characters inclusive.
- A client-side character count is shown on the form. Server-side validation is
  authoritative and rejects values outside that range with HTTP 400.
- The message is stored and displayed as plain text. HTML is escaped on output.

**Story 4 — Submission**

- A successful submit stores a kudos row with `from_user_id` set to the signed-in
  user, `to_user_id` set to the selected colleague, the trimmed message,
  `created_at` in UTC, and `is_visible = 1`.
- The submitter cannot send kudos to themselves (HTTP 400).
- An unknown `to_user_id` returns HTTP 404.
- On success the HTML form redirects to the dashboard with a confirmation, and
  the API returns HTTP 201 with the created kudos.

**Story 5 — Public feed**

- The dashboard and `GET /api/kudos` return kudos with `is_visible = 1` only,
  newest first.
- Each item shows the sender's display name, the recipient's display name, the
  message, and the timestamp.
- Results are paginated: `page` (default 1) and `per_page` (default 20, maximum
  50). The API also returns `total` and `total_pages`.
- An empty feed shows a friendly empty state, not an error.

**Story 6 — Moderation**

- Only users with `role = admin` can hide, restore, or delete kudos. Other users
  receive HTTP 403.
- **Hide** sets `is_visible = 0`, records `moderated_by` (the admin's user id),
  `moderated_at` (UTC now), and a required `reason_for_moderation` (trimmed, 1–500
  characters). The kudos disappears from the public feed but remains in the
  database and on the admin list.
- **Restore** sets `is_visible = 1` and updates `moderated_by` and `moderated_at`.
  The reason may be updated or left as the last hide reason. The kudos reappears
  on the public feed.
- **Delete** permanently removes the row. It no longer appears on the public feed
  or the admin list. This is distinct from hiding.
- Hiding or deleting a missing id returns HTTP 404.
- The admin list (`GET /admin` and `GET /api/admin/kudos`) shows all kudos,
  including hidden ones, with visibility, moderator, time, and reason. It is
  paginated the same way as the public feed.
- Ordinary employees have no link to the admin page; a direct visit redirects or
  returns HTTP 403.

### Edge Cases

The original request did not mention these. They are in scope.

- **Self-kudos:** rejected, as above.
- **Duplicate submissions:** if the same sender submits the same recipient and
  the same message (comparison is case-insensitive and ignores surrounding
  whitespace) within 24 hours, the request is rejected with HTTP 409. A different
  message, a different recipient, or the same message after the 24-hour window is
  allowed.
- **Spam / flooding:** a sender may create at most 10 kudos in any rolling
  60-minute window. Further attempts return HTTP 429.
- **Inappropriate content:** there is no automated language filter in this
  version. Administrators hide or delete messages that should not stay on the
  feed, and must record a reason when hiding.
- **Empty, whitespace-only, or overlong messages:** HTTP 400.
- **Missing or invalid recipient:** HTTP 400 if omitted or not an integer, HTTP
  404 if the id does not exist.
- **Concurrent hide then delete:** delete of an already hidden row is allowed and
  removes it.
- **CSRF:** state-changing requests must include a valid CSRF token (form field
  `csrf_token` or header `X-CSRF-Token`).

---

## Technical Design

### Stack

A small, runnable web application, appropriate for a self-contained demo of an
internal portal feature:

- Language: Python 3.13
- Web framework: Flask 3
- Database: SQLite 3, with foreign keys enabled
- Templates: Jinja2 (autoescape on)
- Tests: pytest and the Flask test client
- License: GNU Affero General Public License v3.0

No separate front-end build step. The UI is server-rendered HTML and CSS, with a
small amount of JavaScript for the character counter. A JSON API sits beside the
pages so the same rules can be tested and reused.

### Database Schema

#### Table `users`

| Column         | Type    | Notes                                              |
|----------------|---------|----------------------------------------------------|
| id             | INTEGER | Primary key, autoincrement                         |
| username       | TEXT    | Unique, required, compared case-insensitively      |
| display_name   | TEXT    | Required, shown on the feed and in the dropdown    |
| password_hash  | TEXT    | Required, Werkzeug password hash                   |
| role           | TEXT    | `employee` or `admin`, default `employee`          |
| created_at     | TEXT    | UTC timestamp, ISO 8601 with a `Z` suffix          |

#### Table `kudos`

| Column                 | Type    | Notes                                                        |
|------------------------|---------|--------------------------------------------------------------|
| id                     | INTEGER | Primary key, autoincrement                                   |
| from_user_id           | INTEGER | Required, foreign key to `users.id` (sender)                 |
| to_user_id             | INTEGER | Required, foreign key to `users.id` (recipient)              |
| message                | TEXT    | Required, 1–500 characters after trim                        |
| created_at             | TEXT    | UTC timestamp, ISO 8601 with a `Z` suffix                    |
| is_visible             | INTEGER | Boolean, `1` or `0`, default `1`                             |
| moderated_by           | INTEGER | Nullable foreign key to `users.id` (the admin)               |
| moderated_at           | TEXT    | Nullable UTC timestamp                                       |
| reason_for_moderation  | TEXT    | Nullable, required when hiding, 1–500 characters after trim  |

Constraints and indexes:

- `from_user_id != to_user_id`
- `length(message)` between 1 and 500
- `is_visible` in `(0, 1)`
- Index `idx_kudos_feed` on `(is_visible, created_at DESC)` for the public feed
- Index `idx_kudos_from_created` on `(from_user_id, created_at DESC)` for the
  duplicate window and the rate limit

`is_visible`, `moderated_by`, `moderated_at`, and `reason_for_moderation` were
added during specification review so administrators can hide a message without
deleting it, and so an audit trail exists for that decision.

### API Endpoints

All JSON endpoints return `Content-Type: application/json`. Error bodies use
`{"error": "<code>", "message": "<human-readable text>"}`. State-changing
requests require a CSRF token.

| Method | Path                      | Auth     | Purpose and response                                                                 |
|--------|---------------------------|----------|--------------------------------------------------------------------------------------|
| GET    | `/api/csrf`               | None     | `{ "csrf_token": "..." }`                                                            |
| POST   | `/api/login`              | None     | Body `{username, password}`. 200 with current user, or 401                           |
| POST   | `/api/logout`             | Session  | 204, session cleared                                                                 |
| GET    | `/api/me`                 | Session  | Current user `{id, username, display_name, role}`                                    |
| GET    | `/api/colleagues`         | Session  | Array of other users, sorted by `display_name`                                       |
| GET    | `/api/kudos`              | Session  | Visible kudos, paginated `{items, page, per_page, total, total_pages}`               |
| POST   | `/api/kudos`              | Session  | Body `{to_user_id, message}`. 201 with the created item                              |
| GET    | `/api/admin/kudos`        | Admin    | All kudos including hidden and moderation fields, same pagination                    |
| POST   | `/api/kudos/<id>/hide`    | Admin    | Body `{reason}`. 200 with the updated item                                           |
| POST   | `/api/kudos/<id>/unhide`  | Admin    | Optional body `{reason}`. 200 with the updated item                                  |
| DELETE | `/api/kudos/<id>`         | Admin    | 204 on success                                                                       |

A public-feed kudos item is:

```json
{
  "id": 1,
  "from_user": {"id": 2, "username": "jordan", "display_name": "Jordan Lee"},
  "to_user": {"id": 3, "username": "priya", "display_name": "Priya Shah"},
  "message": "Thanks for reviewing the release notes.",
  "created_at": "2026-11-20T12:00:00Z",
  "is_visible": true
}
```

Admin items add `"moderated_by"`, `"moderated_at"`, and `"reason_for_moderation"`.
`moderated_by` is a user object or `null`.

### Frontend Components

Server-rendered pages share a base layout with the product name, navigation, the
signed-in user's display name, a Sign out control, and an Admin link that is
shown only to administrators. The layout is usable at a phone width (single
column, comfortable tap targets) and at a desktop width (centered column, about
880px).

| Page / component       | Route                         | Role        |
|------------------------|-------------------------------|-------------|
| Login form             | `GET/POST /login`             | Public      |
| Dashboard feed         | `GET /`                       | Signed-in   |
| Give kudos form        | `GET/POST /give`              | Signed-in   |
| Admin moderation list  | `GET /admin`                  | Admin       |
| Hide / restore / delete| `POST /admin/kudos/<id>/...`  | Admin       |

Interactions:

- Login posts credentials, then redirects to `/`.
- The dashboard lists recent visible kudos and links to Give kudos. Pagination
  uses `?page=`.
- The give-kudos form has a colleague `<select>`, a `<textarea>` (max 500) with a
  live character count, and a Submit button. On success it redirects to `/`.
- The admin page lists every kudos. Hidden rows are marked. Each row has Hide
  (with a reason field), Restore (when hidden), and Delete (with a confirm step).

### Security Considerations

- Authentication is session-based. The session cookie is `HttpOnly` and
  `SameSite=Lax`.
- Authorization is checked on every admin route and every admin API call, not
  only in the UI.
- Passwords are hashed with Werkzeug (`scrypt` or the default hash). Demo
  accounts and their passwords are documented in the README and are for local
  use only.
- `SECRET_KEY` is read from the environment (`KUDOS_SECRET_KEY`). The built-in
  development default is not for production.
- SQL is parameterized. HTML output is auto-escaped.
- CSRF tokens are required for POST, PUT, PATCH, and DELETE.
- Usernames are looked up case-insensitively; generic login errors avoid account
  enumeration.

### Performance Considerations

- The public feed and admin list are paginated (default 20, max 50).
- The two indexes above keep feed and rate-limit queries off a full table scan.
- Caching is not required at demo scale. A later production deploy could add a
  short-lived cache in front of `GET /api/kudos` if traffic warrants it.
- SQLite is sufficient for a single-process demo. A production deployment with
  concurrent writers should move to PostgreSQL, keeping the same schema.

### Error Handling and Logging

- Domain errors use the HTTP statuses already listed (400, 401, 403, 404, 409,
  429). Unexpected errors return HTTP 500 and are logged without leaking a
  traceback to the client.
- The application log (Python `logging`, logger name `kudos`) records
  authentication failures, kudos creation, moderation actions, and unhandled
  exceptions. Logs include user id when a session exists, never raw passwords or
  session secrets.
- HTML forms surface the same domain errors with flash messages.

---

## Implementation Plan

Work proceeds only after this specification is approved. Tasks are listed in
order. A later task may start only when its dependencies are done.

| ID | Task | Depends on | Notes |
|----|------|------------|-------|
| T1 | Scaffold the project: package layout, dependencies, `.gitignore`, AGPL-3.0 license, README stub | — | No feature code yet |
| T2 | Create the SQLite schema, connection helpers, and seed demo users | T1 | Includes moderation columns |
| T3 | Implement CSRF, login, logout, and session-gated access | T2 | Pages and `/api/*` |
| T4 | Implement colleague listing, kudos creation, duplicate detection, and the rate limit | T3 | Shared validation used by HTML and JSON |
| T5 | Implement the paginated public feed | T4 | Dashboard and `GET /api/kudos` |
| T6 | Implement admin hide, restore, and delete, plus the admin list | T5 | UI hidden from non-admins |
| T7 | Finish the responsive templates and styles | T5, T6 | Character count, empty states, flash messages |
| T8 | Write automated tests for the acceptance criteria and edge cases | T6, T7 | See testing strategy |
| T9 | Complete the README (how to run, demo accounts, how to test) and record a real test run | T8 | |

### Testing Strategy

- Framework: pytest, with a fresh temporary SQLite database per test via the
  Flask app factory.
- Transport: the Flask test client, covering both the JSON API and the HTML
  forms.
- Minimum coverage, mapped to the stories and edge cases:
  - Login success, login failure, logout, and rejected unauthenticated access
  - Colleague list excludes the current user
  - Kudos creation succeeds and appears on the feed
  - Self-kudos, empty message, overlong message, and unknown recipient are
    rejected
  - Duplicate submission inside 24 hours returns 409; a different message, or
    the same message after the window, is accepted
  - An 11th kudos inside 60 minutes returns 429
  - Hidden kudos leave the public feed and remain on the admin list
  - Restored kudos return to the public feed
  - Deleted kudos appear on neither list
  - A non-admin cannot hide or delete (403)
  - Stored HTML in a message is escaped in the dashboard HTML
- Tests must be run, and the real command output kept for the write-up. The
  implementation is not done until the suite passes.

### Deployment Considerations

- Local run: a virtualenv, `pip install -r requirements.txt`, `flask --app app
  init-db`, then `flask --app app run`.
- The SQLite file lives under Flask's instance folder and is not committed.
- For a real internal deployment: serve with a WSGI server (for example
  gunicorn) behind HTTPS, set `KUDOS_SECRET_KEY`, disable the development secret,
  and back the database with a managed PostgreSQL instance if more than one
  process will write to it.
- Demo users are for local evaluation only and must be replaced with the
  organization's identity provider before any real use.
- The project is licensed under AGPL-3.0, so a network deployment must follow
  that license, including offering the corresponding source.

---

## Approval

This specification was reviewed against the task checklist (authentication,
colleague selection, submission, public feed, moderation, validation, responsive
layout, schema, API, frontend, security, performance, error handling, a stepped
plan, tests, and deployment).

It is approved as the blueprint for implementation. Application code should
follow this document rather than inventing additional product scope.
