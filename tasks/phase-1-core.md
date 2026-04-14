# Фаза 1 — Ядро

> Конфигурация, БД, модели, миграции, авторизация, валидация на старте.

## Задачи

### 1.1 Структура проекта (§8)
- [ ] Создать директорию `bot/` со всеми подпакетами: `core/`, `models/`, `repositories/`, `services/`, `handlers/`, `keyboards/`, `middlewares/`, `filters/`
- [ ] Создать `bot/__init__.py` и `bot/__main__.py` (точка входа `python -m bot`)

### 1.2 Конфигурация (§6)
- [ ] `bot/core/config.py` — pydantic-settings с вложенными моделями:
  - `TelegramSettings` (`bot_token`, `superadmin`, `database_url`)
  - `SiteSettings` (`name`, `wp_path`, `db_name`, `db_user`, `db_pass`)
  - `BackupSettings` (`dir`, `tmp_dir`, `free_space_mb=40960`)
- [ ] `env_nested_delimiter="__"`, загрузка из `.env`
- [ ] Создать `.env.example` с шаблоном всех переменных

### 1.3 База данных (§3)
- [ ] `bot/core/database.py` — async engine (`create_async_engine`), `async_sessionmaker`, функция `get_session()`

### 1.4 SQLAlchemy модели (§3)
- [ ] `bot/models/user.py` — таблица `users` (id, telegram_id UNIQUE, username, fullname, role ENUM admin/viewer, is_active, created_at)
- [ ] `bot/models/backup.py` — таблица `backups` (id, status ENUM pending/running/success/failed, file_name, backup_path, size_bytes, has_warnings, error_message, triggered_by FK→users.telegram_id ON DELETE SET NULL, is_scheduled, created_at, completed_at)
- [ ] `bot/models/backup.py` — таблица `restores` (id, backup_id FK→backups ON DELETE SET NULL, status ENUM running/success/rolled_back/failed, triggered_by FK→users.telegram_id ON DELETE SET NULL, safety_dir, error_message, created_at, completed_at)
- [ ] `bot/models/schedule.py` — таблица `schedules` (id, name NOT NULL, description NULL, cron_expression, is_active, created_at)

### 1.5 Alembic миграции
- [ ] Инициализировать Alembic (`alembic init alembic`) с async-шаблоном
- [ ] Настроить `alembic.ini` и `alembic/env.py` для async SQLAlchemy + подключение через `settings.tg.database_url`
- [ ] Создать начальную миграцию со всеми 4 таблицами

### 1.6 Auth middleware (§4)
- [ ] `bot/middlewares/__init__.py` — middleware aiogram:
  - Проверка `from_user.id == settings.tg.superadmin` → пропустить как superadmin
  - Поиск пользователя в БД по `telegram_id`
  - Если не найден или `is_active = false` → блокировка (кроме `/start`)
  - Прокидывание `user` и `is_superadmin` в handler data

### 1.7 Фильтры ролей (§4)
- [ ] `bot/filters/__init__.py` — фильтры aiogram:
  - `RoleFilter` — проверка роли пользователя (admin/viewer)
  - Superadmin проходит все фильтры

### 1.8 Валидация на старте (§6)
- [ ] Проверка `SITE__WP_PATH` — существует и читаемая директория
- [ ] Проверка `BACKUP__DIR` и `BACKUP__TMP_DIR` — существуют (создать если нет), доступны на запись
- [ ] Проверка одной ФС: `os.stat().st_dev` для `TMP_DIR`, `WP_PATH`, `BACKUP_DIR` — warning если разные
- [ ] Проверка бинарей в `$PATH` через `shutil.which`: `mysql`, `mysqldump`, `tar`, `zstd`, `wp`, `sudo`, `chown`, `df`
- [ ] Проверка свободного места: `shutil.disk_usage(BACKUP__DIR).free` ≥ `FREE_SPACE_MB` — warning
- [ ] Если критические проверки (1, 2, 4) не пройдены — бот не стартует с ошибкой в stderr

### 1.9 Upsert superadmin (§4)
- [ ] При старте бота — upsert виртуальной строки в `users`: `telegram_id=1, username='superadmin', fullname='superadmin', role='admin', is_active=true`

### 1.10 Точка входа
- [ ] `bot/__main__.py` — последовательность запуска:
  1. Загрузка конфигурации
  2. Валидация на старте (§6)
  3. Инициализация БД (создание таблиц / проверка миграций)
  4. Upsert superadmin
  5. Orphan recovery (реализуется в фазе 2)
  6. Загрузка расписаний (реализуется в фазе 3)
  7. Запуск Telegram polling
