# Фаза 2 — Бэкапы

> Создание бэкапов, дисковое пространство, уведомления, конкурентность.

## Зависимости
- Фаза 1 (конфиг, БД, модели, middleware)

## Задачи

### 2.1 Репозиторий бэкапов
- [ ] `bot/repositories/backup_repo.py` — CRUD:
  - `create(status, triggered_by, is_scheduled)` → запись со статусом `pending`
  - `update(id, **fields)` — обновление полей (status, file_name, backup_path, size_bytes, has_warnings, error_message, completed_at)
  - `get_by_id(id)`
  - `get_running()` — найти запись со `status = 'running'`
  - `list_all(limit, offset)` — список бэкапов с сортировкой по дате
  - `count()` — количество бэкапов
  - `delete(id)` — удалить запись

### 2.2 Сервис дискового пространства (§5.2)
- [ ] `bot/services/disk_service.py`:
  - `get_disk_usage()` — выполнить `df -h` через `asyncio.create_subprocess_exec`, вернуть человекочитаемый вывод
  - `check_free_space(path, min_mb)` — `shutil.disk_usage(path).free` ≥ `min_mb * 1024 * 1024`

### 2.3 Сервис уведомлений (§5.7)
- [ ] `bot/services/notification_service.py`:
  - `notify_all(bot, message)` — отправить сообщение всем активным пользователям (`is_active=true`) + superadmin
  - Форматирование событий: успешный бэкап (размер, время, путь), бэкап с warnings, ошибка бэкапа, плановый бэкап запущен, недостаточно места

### 2.4 Конкурентность (§5.8)
- [ ] Глобальный `asyncio.Lock` — in-memory блокировка
- [ ] Проверка БД: нет записей со `status = 'running'` в `backups` и `restores` перед стартом операции
- [ ] При отказе — сообщение: «Уже выполняется операция (запущена в {created_at} пользователем {username})»

### 2.5 Сервис бэкапов (§5.3)
- [ ] `bot/services/backup_service.py` — полный процесс:
  1. Проверка конкурентности (§5.8)
  2. Проверка свободного места (`disk_service.check_free_space`)
  3. Создать каталог `{backup.dir}/{site.name}/` если не существует
  4. `tempfile.mkdtemp(prefix="wp-backup-{site.name}-", dir=settings.backup.tmp_dir)`
  5. `mkdir database` внутри TMP_DIR
  6. `mysqldump --single-transaction --quick` с `MYSQL_PWD` через env (не `-p{pass}`!)
  7. `tar --zstd --ignore-failed-read -cf` с двумя `-C` (database + WP_PATH) — один проход без промежуточного `cp -a`
  8. Обработка кодов возврата tar: 0→success, 1→success+warnings, 2+→failed
  9. `shutil.rmtree(TMP_DIR, ignore_errors=True)` — только созданную подпапку
  10. Сохранить в БД: size_bytes, backup_path, file_name, status, has_warnings, completed_at, triggered_by
  11. Уведомление всем: размер, полный путь к архиву, пометка warnings если есть

### 2.6 Orphan recovery для бэкапов (§5.8.1, шаг 1)
- [ ] При старте бота (до polling):
  - `SELECT * FROM backups WHERE status = 'running'`
  - Для каждой: удалить tmp-папки `glob(wp-backup-{site.name}-*)`, удалить частичный архив если существует
  - `UPDATE status='failed', error_message='process crashed...', completed_at=NOW()`

### 2.7 Хэндлеры бэкапов
- [ ] `bot/handlers/backups.py`:
  - Создать бэкап (admin/superadmin) — запуск `backup_service`
  - Список бэкапов (все роли) — дата, размер, статус, кто создал
  - Количество бэкапов (все роли)
  - Удалить бэкап (admin/superadmin) — выбор из списка → подтверждение → удаление файла + записи в БД

### 2.8 Хэндлер дискового пространства (§5.2)
- [ ] `bot/handlers/disk.py`:
  - Просмотр `df -h` (все роли)

### 2.9 Клавиатуры
- [ ] `bot/keyboards/` — inline-клавиатуры:
  - Список бэкапов (пагинация)
  - Подтверждение удаления бэкапа
  - Подтверждение создания бэкапа
