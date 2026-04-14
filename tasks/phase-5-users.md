# Фаза 5 — Управление пользователями

> Регистрация, управление ролями, очистка кэша WordPress.

## Зависимости
- Фаза 1 (конфиг, БД, модели, middleware)
- Фаза 2 (конкурентность — для cache flush)

## Задачи

### 5.1 Репозиторий пользователей
- [ ] `bot/repositories/user_repo.py` — CRUD:
  - `get_by_telegram_id(telegram_id)`
  - `create(telegram_id, username, fullname, role='viewer', is_active=False)`
  - `list_all()` — все пользователи
  - `list_active()` — только `is_active = true`
  - `activate(telegram_id)` — `is_active = true`
  - `deactivate(telegram_id)` — `is_active = false`
  - `set_role(telegram_id, role)` — изменить роль (admin/viewer)
  - `upsert_superadmin()` — виртуальная строка `telegram_id=1`

### 5.2 Хэндлер /start (§5.1)
- [ ] `bot/handlers/start.py`:
  - Если пользователь не в БД → создать с `role=viewer`, `is_active=false`
  - Ответ: «Доступ ожидает подтверждения от администратора»
  - Если `is_active = false` → «Доступ не разрешён»
  - Если `is_active = true` → приветствие с доступными командами (зависит от роли)

### 5.3 Хэндлеры управления пользователями (§5.1)
- [ ] `bot/handlers/users.py` (только superadmin):
  - Список всех пользователей (`telegram_id`, `username`, `fullname`, `role`, `is_active`)
  - Активировать пользователя (выбор из списка)
  - Деактивировать пользователя
  - Изменить роль (admin ↔ viewer)

### 5.4 Сервис очистки кэша (§5.5)
- [ ] `bot/services/cache_service.py`:
  - `flush_cache()` — `sudo -u www-data wp cache flush --path={site.wp_path}`
  - Через `asyncio.create_subprocess_exec`
  - Если код возврата ≠ 0 → ошибка из stderr
  - Проверка конкурентности: если идёт бэкап/восстановление → отказ

### 5.5 Хэндлер очистки кэша (§5.5)
- [ ] `bot/handlers/cache.py` (admin/superadmin):
  - Кнопка «Очистить кэш WordPress» → подтверждение → выполнение → результат в чат

### 5.6 Клавиатуры
- [ ] Inline-клавиатуры:
  - Список пользователей с кнопками управления
  - Подтверждение активации/деактивации
  - Выбор роли (admin/viewer)
  - Подтверждение очистки кэша
