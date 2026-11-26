# Task Management System - Backend

English | [Українська](README.uk.md)

A REST API for collaborative project and task management, built with Django
and Django REST Framework. The backend brings together work assignments,
deadlines, discussions, notifications, and project analytics.

This repository contains the backend and a Telegram bot. A separate web
client can integrate with the application through its API.

## Features

- **Projects:** creation, membership management, access control, and active or
  archived status.
- **Tasks:** assignees, priorities, deadlines, progress tracking, and change
  history.
- **Discussions:** task comments and threaded replies.
- **Accounts:** registration, JWT authentication, profiles, password changes,
  validated avatar uploads, and administrative roles.
- **Notifications:** email and Telegram updates about assignments, status,
  priority, deadlines, and approaching due dates.
- **Telegram:** one-time links to verify a private chat and bot commands to
  manage notification preferences.
- **Analytics:** task counts, status distribution, and average completion time
  through the API and administration dashboard.
- **API:** filtering, search, ordering, pagination, and an OpenAPI specification.

## Technology stack

| Component | Technologies |
| --- | --- |
| Language and web framework | Python 3.14.10, Django 5.2 LTS |
| REST API | Django REST Framework, django-filter |
| Authentication | SimpleJWT, Django authentication, django-axes |
| Database | PostgreSQL, Psycopg |
| Background jobs | Celery, gevent, django-celery-beat |
| Broker, task results, and cache | Redis |
| Telegram and HTTP integrations | Aiogram, HTTPX |
| Static assets and web server | WhiteNoise, Gunicorn |
| API documentation | drf-spectacular, OpenAPI, Swagger UI, ReDoc |

Direct and transitive dependency versions are pinned with SHA-256 hashes in
`requirements.txt` and `requirements-dev.txt`.

## Project structure

```text
task_management_system/  Django and Celery configuration, middleware, request protection
users/                   Accounts, JWT, profiles, and Telegram verification
projects/                Projects, membership, and access permissions
tasks/                   Tasks, assignees, history, and comments
notifications/           Notifications, transactional outbox, and Telegram bot
analytics/               Project statistics and administration charts
.github/workflows/       Automated tests and security checks
```

PostgreSQL stores domain data and the notification delivery queue. Celery
handles background operations; Redis serves as the broker, result backend,
and cache. Database beat schedules periodic jobs, and the Telegram bot uses
long polling.

Notifications are persisted in a transactional outbox alongside the related
data change, then queued for delivery. A broker outage does not discard the
stored delivery: a periodic job retries it. Delivery follows at-least-once
semantics, so an external failure can still lead to a duplicate.

## Access control

Project access depends on ownership and membership. Task access also takes
assignment into account. An assignee can change a task's status, but not its
content or membership. Project owners and system administrators can edit and
delete tasks.

Comments are available only within an accessible task. Users can see only
their own notifications and private profile fields. Administration and
analytics require an active system administrator role; `is_staff` alone does
not grant access.

## Local setup

### Requirements

- Python 3.14.10.
- PostgreSQL and Redis for normal application operation.
- An SMTP service and Telegram bot token for the corresponding notification
  channels.
- Linux/Heroku for production startup with Gunicorn and the existing
  `Procfile`.

### Windows environment

For a fresh clone, run in PowerShell:

```powershell
git clone https://github.com/neuropunk87/task-management-system-backend.git
cd task-management-system-backend

py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt

if (!(Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Set the environment-specific values in `.env`. Use unique secrets and never
commit working passwords or tokens. Production requires the runtime
dependencies in `requirements.txt`; the development lock file also includes
testing and audit tools.

### Main configuration

| Variables | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Unique application secret |
| `DJANGO_ENV`, `DEBUG`, `ALLOWED_HOSTS` | Environment and allowed domains |
| `DATABASE_URL` or `POSTGRES_*` | PostgreSQL connection |
| `REDIS_URL`, `REDIS_TLS_URL` | Redis broker, task results, and cache |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Allowed frontend origins |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | Email backend and delivery configuration |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` | Telegram bot configuration |

The full configuration template is available in `.env.example`. Its
development defaults must be adapted before use in production.

### Migrations and API startup

After configuring local PostgreSQL and Redis:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

The API runs at `http://127.0.0.1:8000/`. Sign in to the administration
dashboard at `/secretadmin/login/`. Local avatar serving can be enabled with
`DEBUG=True`, but only when `DJANGO_ENV=development`.

`runserver` is intended for API development and does not start background
components. Production uses the existing Gunicorn/Celery/beat/bot setup on
Linux/Heroku; Gunicorn does not support native Windows execution.

## API and documentation

Key routes:

| Route | Purpose |
| --- | --- |
| `POST /api/users/register/` | Registration |
| `POST /api/users/login/` | Obtain access and refresh tokens |
| `POST /api/users/token/refresh/` | Refresh tokens |
| `POST /api/users/logout` | Revoke the current user's refresh token |
| `/api/users/profile/` | Current user's profile |
| `POST/DELETE /api/users/profile/telegram-link/` | Verify or unlink Telegram |
| `/api/projects/` | Projects and membership |
| `/api/tasks/tasks/` | Tasks and additional lists |
| `/api/tasks/comments/` | Comments and replies |
| `/api/notifications/` | Current user's unread notifications |
| `/api/analytics/<project_id>/` | Project analytics for administrators |
| `/api/schema/` | OpenAPI schema |

Include this header in authenticated requests:

```http
Authorization: Bearer <access_token>
```

Development documentation is available at `/api/docs/swagger-ui/` and
`/api/docs/redoc/`. These interfaces are disabled by default in production,
and schema access is restricted to administrators. The checked-in API
specification is `schema.yml`.

## Heroku deployment

The existing setup uses **two process types**. Keep the `Procfile` commands
unchanged:

```procfile
web: gunicorn task_management_system.wsgi --log-file -
worker: celery -A task_management_system worker --loglevel=info -P gevent & celery -A task_management_system beat --scheduler django_celery_beat.schedulers.DatabaseScheduler --loglevel=info & exec python notifications/telegram_bot.py
```

The Celery worker, beat, and Telegram bot share one worker dyno. Do not split
them into additional process types or replace this setup with a new launcher.
Run a single worker replica for beat and long polling. Scaling and paid
resources are not changed automatically.

### Production configuration

- `DJANGO_ENV=production`, `DEBUG=False`, and a unique `DJANGO_SECRET_KEY`.
- Explicit `ALLOWED_HOSTS` without `*` and the required HTTPS frontend origins.
- Connection URLs for the existing PostgreSQL/Redis add-ons, SMTP, and Telegram
  configuration.
- PostgreSQL with TLS and Redis over `rediss://`.

The Heroku runtime variable `DYNO` enables production and proxy defaults.
Explicit Config Vars take precedence. Without separate Redis overrides, the
broker, result backend, and cache inherit the current add-on URL; do not pin
obsolete connection addresses.

Heroku KVS without a custom CA uses a compatibility mode: TLS remains enabled,
but verification of its self-signed certificate is disabled for Redis only.
This mode applies automatically when `DYNO` is present and
`REDIS_SSL_CA_CERTS` is not set. Certificate verification remains strict
outside Heroku. The connection is encrypted, but the server's identity is not
verified. This is an accepted trade-off following
[Heroku KVS guidance](https://devcenter.heroku.com/articles/connecting-heroku-redis).
Do not set `HEROKU_REDIS_COMPATIBILITY=False` without a trusted CA.

### Updating an existing deployment

Deployment and production migrations are managed manually by the repository
owner. Back up the database and apply migrations **using the new version's
code** during a planned maintenance window, before normal requests and
background jobs are processed:

```text
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Management commands can be run with `heroku run ... -a APP` once the new
version is available. One-off runs can consume subscription quota. No
`release` process type is added to the `Procfile`.

Heroku has an ephemeral filesystem: local `MEDIA_ROOT` does not guarantee
persistent avatars or access across dynos. Configure persistent media storage
separately; no new service or paid add-on is created automatically.

## Testing and security checks

Tests use temporary SQLite and a local-memory cache by default. They do not
send real SMTP or Telegram messages:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=task_management_system.settings_test
.\.venv\Scripts\python.exe -m pip check

.\.venv\Scripts\bandit.exe -r analytics notifications projects task_management_system tasks users -x "*/migrations/*,*/tests.py,*/tests_*.py"
.\.venv\Scripts\pip-audit.exe -r requirements.txt --no-deps
.\.venv\Scripts\pip-audit.exe -r requirements-dev.txt --no-deps
```

For concurrent transaction checks, set `AUDIT_TEST_DATABASE_URL` and
`AUDIT_TEST_REDIS_URL` **only for isolated test services**. The runner creates
and removes a test database, and tests clear the cache. Never use production
Redis. Without PostgreSQL, two concurrency tests are skipped.

The workflow in `.github/workflows/security.yml` defines PostgreSQL/Redis
tests, an 80% coverage threshold, migration and schema checks, production
settings checks, Bandit, and dependency audits, including a weekly run.
Execution on GitHub requires publishing the changes.

Verified on 2026-10-08: **106 tests** passed on Windows and Linux,
branch-aware coverage reached **84%**, and Bandit plus both dependency audits
reported no findings. Scanner results do not guarantee the absence of all
vulnerabilities.

## Updating dependencies

Edit `requirements.in` and `requirements-dev.in`, then regenerate the lock
files:

```powershell
.\.venv\Scripts\pip-compile.exe --generate-hashes --allow-unsafe --newline=lf -o requirements.txt requirements.in
.\.venv\Scripts\pip-compile.exe --generate-hashes --allow-unsafe --newline=lf -o requirements-dev.txt requirements-dev.in
```

After updates, rerun tests, `pip check`, and audits for both lock files. Do not
replace them with an arbitrary `pip freeze` from a shared environment.
