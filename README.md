# Telegram-бот для резервного копирования WordPress

Локальный Telegram-бот для управления резервным копированием одного WordPress-сайта. Устанавливается на тот же сервер, где работает WordPress, и выполняет все операции локально (`tar`, `mysqldump`, `mysql`, `df`). Поддерживает ручные и плановые бэкапы, восстановление с rollback, управление пользователями и очистку кэша WP.

## Технологии

| Компонент | Версия |
|---|---|
| Python | 3.13+ |
| Менеджер пакетов | uv |
| Telegram-фреймворк | aiogram 3.17+ |
| ORM | SQLAlchemy 2.x (async) |
| База данных | SQLite + aiosqlite |
| Миграции | Alembic 1.14+ |
| Планировщик | APScheduler 3.11+ |
| Конфигурация | pydantic-settings 2.7+ |

## Требования

**Серверные зависимости (должны быть в `$PATH`):**
- `mysql`, `mysqldump` — mysql-client
- `tar`, `chown`, `df` — стандартные coreutils
- `zstd` — сжатие архивов (`apt install zstd`)
- `wp` — WP-CLI (нужен для restore и очистки кэша)
- `sudo` — для запуска команд от `www-data`
- Python 3.13+ и `uv`

**Права запуска:** бот запускается от `root` (через systemd).

## Установка

1. Клонируйте репозиторий на сервер:
   ```bash
   git clone <repo-url> /opt/wp-backup-bot
   cd /opt/wp-backup-bot
   ```

2. Установите зависимости:
   ```bash
   uv sync
   ```

3. Создайте `.env` на основе шаблона:
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

4. Заполните `.env`:
   ```env
   TG__BOT_TOKEN=<токен вашего бота>
   TG__SUPERADMIN=<ваш telegram_id>

   SITE__NAME=steam
   SITE__WP_PATH=/var/www/steam
   SITE__DB_NAME=steam_wp
   SITE__DB_USER=steam_wp
   SITE__DB_PASS=<пароль MySQL>

   BACKUP__DIR=/backups
   BACKUP__TMP_DIR=/backups/.tmp
   BACKUP__FREE_SPACE_MB=40960
   ```
   > `BACKUP__TMP_DIR` обязательно должен быть на той же файловой системе, что `WP_PATH` и `BACKUP__DIR`.

5. Примените миграции БД:
   ```bash
   uv run alembic upgrade head
   ```

## Использование

**Запуск напрямую:**
```bash
uv run python -m bot
```

**Запуск через systemd** (рекомендуется):
```ini
[Unit]
Description=WordPress Backup Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/wp-backup-bot
ExecStart=/opt/wp-backup-bot/.venv/bin/python -m bot
EnvironmentFile=/opt/wp-backup-bot/.env
Restart=on-failure
ProtectSystem=strict
NoNewPrivileges=true
ReadWritePaths=/backups /opt/wp-backup-bot /var/www/steam

[Install]
WantedBy=multi-user.target
```

### Команды бота

| Команда | Роль | Описание |
|---|---|---|
| `/start` | все | Регистрация / приветствие |
| `/backup` | все | Меню бэкапов |
| `/backup_create` | admin+ | Создать бэкап |
| `/backup_list` | все | Список бэкапов |
| `/backup_count` | все | Количество бэкапов |
| `/restore` | admin+ | Восстановление из бэкапа |
| `/restore_history` | все | История восстановлений |
| `/schedule` | все | Список расписаний |
| `/schedule_add` | admin+ | Добавить расписание |
| `/disk` | все | Дисковое пространство (`df -h`) |
| `/cache` | admin+ | Очистить кэш WordPress |
| `/users` | superadmin | Управление пользователями |

### Роли

- **superadmin** — задаётся через `TG__SUPERADMIN`, полный доступ
- **admin** — создание бэкапов, восстановление, расписания, кэш
- **viewer** — только просмотр

Новые пользователи регистрируются с ролью `viewer` и `is_active=false`. Активирует их superadmin через `/users`.

## Структура проекта

```
telegram-bot-backups/
├── .env.example            # Шаблон переменных среды
├── .env                    # Конфигурация (не коммитится)
├── pyproject.toml          # Зависимости (uv)
├── alembic.ini             # Конфиг миграций
├── alembic/
│   └── versions/           # Файлы миграций
├── tasks/                  # Описание фаз разработки
└── bot/
    ├── __main__.py         # Точка входа, валидация, запуск
    ├── core/
    │   ├── config.py       # pydantic-settings конфигурация
    │   └── database.py     # Async engine и session maker
    ├── models/             # SQLAlchemy модели
    │   ├── user.py         # users
    │   ├── backup.py       # backups + restores
    │   └── schedule.py     # schedules
    ├── repositories/       # CRUD-слой
    │   ├── user_repo.py
    │   ├── backup_repo.py
    │   └── schedule_repo.py
    ├── services/           # Бизнес-логика
    │   ├── backup_service.py    # tar + mysqldump, конкурентность
    │   ├── restore_service.py   # mv-подмена, rollback
    │   ├── scheduler_service.py # APScheduler
    │   ├── disk_service.py      # df -h
    │   ├── cache_service.py     # wp cache flush
    │   └── notification_service.py # рассылка пользователям
    ├── handlers/           # aiogram handlers
    ├── keyboards/          # Inline-клавиатуры
    ├── middlewares/        # Auth middleware
    └── filters/            # Фильтры ролей
```

## Лицензия

Не указана.
