# Фаза 3 — Расписание

> APScheduler + CRUD расписаний через бота.

## Зависимости
- Фаза 1 (конфиг, БД, модели)
- Фаза 2 (backup_service, notification_service)

## Задачи

### 3.1 Репозиторий расписаний
- [ ] `bot/repositories/schedule_repo.py` — CRUD:
  - `create(name, description, cron_expression, is_active=True)`
  - `get_by_id(id)`
  - `list_all()` — все расписания
  - `list_active()` — только `is_active = true`
  - `toggle(id, is_active)` — включить/выключить
  - `delete(id)`

### 3.2 Сервис планировщика (§5.6)
- [ ] `bot/services/scheduler_service.py`:
  - Инициализация `AsyncIOScheduler`
  - `load_schedules()` — при старте бота подгрузить все расписания с `is_active=true`, зарегистрировать в APScheduler через `CronTrigger.from_crontab(...)`
  - `add_schedule(name, description, cron_expression)` — добавить в БД + зарегистрировать job
  - `remove_schedule(id)` — удалить из БД + удалить job
  - `toggle_schedule(id, is_active)` — вкл/выкл job в APScheduler
  - Job callback: вызывает `backup_service.create_backup(triggered_by=None, is_scheduled=True)` + уведомление «Плановый бэкап запущен»

### 3.3 Хэндлеры расписаний
- [ ] `bot/handlers/schedules.py` (admin/superadmin):
  - Добавить расписание:
    - Пресеты: ежедневно 02:00 (`0 2 * * *`), еженедельно (`0 2 * * 0`), ежемесячно (`0 2 1 * *`)
    - Своё cron-выражение (ввод текстом)
    - Ввод имени и описания
  - Просмотр активных расписаний (все роли для просмотра, но управление — admin/superadmin)
  - Включить/выключить расписание
  - Удалить расписание

### 3.4 Клавиатуры
- [ ] Inline-клавиатуры:
  - Пресеты cron-выражений
  - Список расписаний с кнопками вкл/выкл/удалить

### 3.5 Интеграция с точкой входа
- [ ] В `bot/__main__.py` — вызов `scheduler_service.load_schedules()` после orphan recovery, до polling
