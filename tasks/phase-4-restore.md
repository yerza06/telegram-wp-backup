# Фаза 4 — Восстановление

> Restore с mv-подменой, maintenance mode, rollback, orphan recovery.

## Зависимости
- Фаза 1 (конфиг, БД, модели)
- Фаза 2 (backup_repo, notification_service, конкурентность)

## Задачи

### 4.1 Репозиторий восстановлений
- [ ] В `bot/repositories/backup_repo.py` (или отдельный `restore_repo.py`):
  - `create_restore(backup_id, triggered_by)` → запись со `status = 'running'`
  - `update_restore(id, **fields)` — обновление (status, safety_dir, error_message, completed_at)
  - `get_running_restore()` — найти запись со `status = 'running'`
  - `list_restores(limit, offset)` — история восстановлений
  - `list_restores_by_backup(backup_id)` — все восстановления конкретного бэкапа

### 4.2 Сервис восстановления (§5.4)
- [ ] `bot/services/restore_service.py` — полный процесс:
  1. Проверка конкурентности (§5.8)
  2. Создать запись в `restores` со `status = 'running'`
  3. **Snapshot БД:** `tempfile.mkdtemp(prefix="wp-rollback-{site.name}-")` → `mysqldump > $SAFETY_DIR/db_current.sql`
  4. **Распаковка:** `tempfile.mkdtemp(prefix="wp-restore-{site.name}-")` → `tar --zstd -xf <backup>.tar.zst -C $TMP_DIR`
  5. Если распаковка упала → cleanup TMP_DIR + SAFETY_DIR, `status = failed`. WP_PATH не тронут
  6. **Maintenance mode ON:** `sudo -u www-data wp maintenance-mode activate --path={wp_path}`. Если WP-CLI не установлен → ошибка с инструкцией
  7. **Атомарная подмена:**
     - `mv $WP_PATH ${WP_PATH}.old-<restore_id>`
     - `mv $TMP_DIR/<basename(WP_PATH)> $WP_PATH`
  8. **Chown:** `chown -R www-data:www-data {wp_path}` — без chmod (tar сохраняет оригинальные права)
  9. **Восстановление БД:** `mysql {db_name} < $TMP_DIR/database/db.sql` с `MYSQL_PWD` через env
  10. **Maintenance mode OFF:** `sudo -u www-data wp maintenance-mode deactivate`

### 4.3 Rollback при ошибке (§5.4, шаги 12-14)
- [ ] Если шаги 7–10 упали:
  - `rm -rf $WP_PATH` (новые файлы)
  - `mv ${WP_PATH}.old-<restore_id> $WP_PATH` (вернуть старые)
  - Восстановить БД из `$SAFETY_DIR/db_current.sql`
  - `wp maintenance-mode deactivate`
  - Удалить SAFETY_DIR и TMP_DIR
  - `status = rolled_back`, уведомление
- [ ] Если откат тоже упал:
  - **Не удалять** SAFETY_DIR и `${WP_PATH}.old-<id>`
  - `status = failed`, `error_message` с причиной
  - Уведомление с полными путями для ручного восстановления

### 4.4 Orphan recovery для restores (§5.8.1, шаг 2)
- [ ] При старте бота:
  - `SELECT * FROM restores WHERE status = 'running'`
  - Удалить только `wp-restore-{site.name}-*` подкаталог в TMP_DIR
  - **НЕ трогать** `${WP_PATH}.old-<id>` и `safety_dir`
  - `status = failed`, `error_message = 'process crashed... Manual inspection required.'`
  - Критическое уведомление (🚨) всем: состояние непредсказуемо, пути к артефактам

### 4.5 Хэндлеры восстановления
- [ ] `bot/handlers/restore.py` (admin/superadmin):
  - Выбрать бэкап из списка (только `status = success`)
  - Подтверждение (⚠️ перезапишет файлы и БД)
  - Запуск `restore_service`
  - История восстановлений (все роли): дата, из какого бэкапа, кто запустил, статус
  - Карточка бэкапа — показать все восстановления из этого бэкапа

### 4.6 Клавиатуры
- [ ] Inline-клавиатуры:
  - Выбор бэкапа для восстановления
  - Подтверждение восстановления (⚠️)
  - Список истории восстановлений (пагинация)
