# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the bot
uv run python -m bot

# Add a dependency
uv add <package>

# Alembic migrations
uv run alembic revision --autogenerate -m "<description>"
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Architecture

Telegram bot for WordPress backup management. One bot instance = one WordPress site = one server. The bot runs **on the same server** as WordPress and executes all operations (`tar`, `mysqldump`, `mysql`, `df`, `chown`, `wp`) as local subprocess calls via `asyncio.create_subprocess_exec`.

**Stack:** Python 3.13, aiogram 3.x, SQLAlchemy 2.x async, SQLite + aiosqlite, Alembic, APScheduler, pydantic-settings.

### Layer structure (`bot/`)

| Layer | Path | Responsibility |
|---|---|---|
| Config | `core/config.py` | pydantic-settings with nested models; `env_nested_delimiter="__"` |
| Database | `core/database.py` | async engine, `async_sessionmaker`, `get_session()` |
| Models | `models/` | SQLAlchemy ORM: `users`, `backups`, `restores`, `schedules` |
| Repositories | `repositories/` | Raw CRUD against the DB |
| Services | `services/` | Business logic (backup, restore, disk, cache, scheduler, notifications) |
| Handlers | `handlers/` | aiogram message/callback handlers |
| Keyboards | `keyboards/` | Inline and reply keyboard builders |
| Middlewares | `middlewares/` | Auth middleware — resolves user/superadmin for every update |
| Filters | `filters/` | Role-based access filters (`admin`, `viewer`) |

### Auth model (§4 of TECH.md)

- **superadmin** is identified by `from_user.id == settings.tg.superadmin` (env var `TG__SUPERADMIN`), never stored with a real `telegram_id`. A virtual row `telegram_id=1, username='superadmin'` is upserted at startup so FKs remain valid.
- Regular users: `viewer` (read-only) or `admin` (can run backups, restores, delete, manage schedules). Blocked users (`is_active=false`) are rejected by middleware for all commands except `/start`.
- New users who send `/start` are auto-created with `role=viewer, is_active=false` and must be activated by superadmin.

### Backup/restore key details (§5 of TECH.md)

- Archives: `wp-<site.name>-backup_<YYYY-MM-DD_HH-mm-SS>.tar.zst` (zstd compression, single tar with `wordpress/` and `database/` folders inside).
- MySQL password is always passed via `MYSQL_PWD` env var to the subprocess — **never** via `-p<pass>`.
- Restore uses atomic `mv` (rename syscall) for file swap: `mv $WP_PATH $WP_PATH.old-<id>` then `mv $TMP_DIR/<basename> $WP_PATH`. Requires `BACKUP__TMP_DIR` on the same filesystem as `WP_PATH`.
- Concurrency: one global `asyncio.Lock` + DB-level check for `status='running'` records.
- Orphan recovery runs at startup before polling starts: failed `running` backups are marked `failed`; failed `running` restores are marked `failed` but their safety artifacts (`$SAFETY_DIR`, `$WP_PATH.old-<id>`) are **not deleted** — operators must clean up manually.

### Startup validation (§6 of TECH.md)

At startup the bot validates: `WP_PATH` exists and is readable, `BACKUP__DIR`/`BACKUP__TMP_DIR` exist and are writable, all required binaries are in `$PATH` (`mysql`, `mysqldump`, `tar`, `zstd`, `wp`, `sudo`, `chown`, `df`), same-filesystem check via `os.stat().st_dev`. Fails hard (stderr + exit) on critical failures.

## Environment

Copy `.env.example` to `.env` (rights `600`) before running. Key variables:

```
TG__BOT_TOKEN, TG__SUPERADMIN, TG__DATABASE_URL
SITE__NAME, SITE__WP_PATH, SITE__DB_NAME, SITE__DB_USER, SITE__DB_PASS
BACKUP__DIR, BACKUP__TMP_DIR, BACKUP__FREE_SPACE_MB
```

## Development phases

Tasks are tracked in `tasks/phase-{1..5}-*.md`:
1. Core (config, DB, models, migrations, auth)
2. Backups + disk + notifications + concurrency
3. Scheduler (APScheduler)
4. Restore with rollback
5. User management UI
