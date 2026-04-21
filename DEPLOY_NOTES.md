# Deploy notes — Asana removal + partners cleanup

Этот деплой содержит **критичные изменения**, которые нужно накатывать строго в указанном порядке. Иначе вернутся проблемы, ради которых это всё писалось:

- из CRM полностью выпилена интеграция с Asana (cron-задачи `asana_producers_sync` и `asana_comments_sync` удалены, management-команды `import_asana_producers` / `sync_asana_comments` удалены, env-переменные `ASANA_PAT` / `ASANA_PROJECT_GID` больше не нужны);
- удалена команда `seed_data` и автозапуск её через `RUN_SEED_DATA` в `entrypoint.sh` — она была источником левых "Isabelle Fontaine / +7…" партнёров с фейковыми продажами;
- добавлен partial unique constraint на `Partner.user_id` (миграция [`partners/0013_partner_user_id_unique`](backend/partners/migrations/0013_partner_user_id_unique.py)) и advisory lock на `run_crm_partners_sync` — дубли партнёров при гонке gunicorn-воркеров теперь невозможны на уровне БД;
- при импорте через `import_crm_contacts` стадия партнёра выставляется автоматически (`paid_orders_count > 0 → has_sale`, `medical_sets_count > 0 → set_created`, иначе `new`); существующая стадия апгрейдится только вверх и только если партнёр в auto-managed состоянии (`new / set_created / has_sale`).

---

## Порядок шагов на проде

**1. Снять текущий бэкап БД (на всякий случай):**

```bash
docker compose exec db pg_dump -U crm_user -F c ayurveda_crm > backup_before_deploy_$(date +%F).dump
```

**2. Задеплоить новый код (Asana уже выпилена в этом коммите):**

```bash
git pull
docker compose build backend
docker compose up -d backend frontend
```

После этого шага старый Asana-cron уже не запустится.

**3. Восстановить продюсеров из локального дампа `ayurveda-crm-FULL.dump` (на выбор один вариант):**

- **Вариант A — простой и безопасный (рекомендуется):**

  ```bash
  docker compose cp ayurveda-crm-FULL.dump db:/tmp/ayurveda-crm-FULL.dump
  docker compose exec db pg_restore --clean --if-exists -U crm_user -d ayurveda_crm /tmp/ayurveda-crm-FULL.dump
  ```

  `pg_restore --clean --if-exists` сам дропнет и пересоздаст таблицы перед заливкой данных. Подходит, если дамп — full.

- **Вариант B — точечный (если нужно тронуть только продюсеров):**

  ```bash
  docker compose exec db psql -U crm_user -d ayurveda_crm -c \
    "TRUNCATE producers_producer, producers_producercomment, producers_producertask CASCADE;"
  docker compose cp ayurveda-crm-FULL.dump db:/tmp/ayurveda-crm-FULL.dump
  docker compose exec db pg_restore --data-only -U crm_user -d ayurveda_crm \
    -t 'producers_*' /tmp/ayurveda-crm-FULL.dump
  ```

  Если есть сомнения — выбирай **A**.

**4. Накатить новую миграцию:**

```bash
docker compose exec backend python manage.py migrate
```

Это включит unique constraint `partners_partner_user_id_unique_when_set` на `partners_partner.user_id`.

> Если мигрейт упадёт с ошибкой "could not create unique index ... duplicate key value", значит в БД ещё остались дубли партнёров. Прогнать перед этим:
>
> ```bash
> docker compose exec backend python manage.py dedupe_partners --dry-run   # глянуть что схлопнется
> docker compose exec backend python manage.py dedupe_partners              # реально схлопнуть
> docker compose exec backend python manage.py migrate                     # повторить миграцию
> ```

**5. Снести текущих партнёров и заново вытянуть из API уже корректно:**

```bash
docker compose exec backend python manage.py import_crm_contacts --clear
```

Это:

- удалит ВСЕХ партнёров (включая Изабель и её русских коллег);
- заново вытянет всех из внешнего CRM API;
- сразу проставит правильную стадию: тех, у кого есть оплаченные заказы — в `Has Sale`; у кого есть medical sets — в `Set Created`; остальных — в `New`.

**6. Перезапустить backend на всякий случай (чтобы все 3 gunicorn-воркера подхватили новый код APScheduler):**

```bash
docker compose restart backend
```

---

## Sanity-checks после деплоя

```bash
# Проверить что дублей партнёров действительно нет
docker compose exec db psql -U crm_user -d ayurveda_crm -c \
  "SELECT user_id, COUNT(*) FROM partners_partner WHERE user_id <> '' GROUP BY user_id HAVING COUNT(*) > 1;"
# (должно быть 0 строк)

# Проверить что Asana-кронов больше нет
docker compose logs backend | grep -i 'Schedulers started'
# (в строке должно быть "CRM partners hourly :05 IST" и НЕ должно быть "Asana producers" / "Asana comments")

# Проверить распределение партнёров по стадиям
docker compose exec db psql -U crm_user -d ayurveda_crm -c \
  "SELECT stage, COUNT(*) FROM partners_partner GROUP BY stage ORDER BY 2 DESC;"
```

---

## Что осталось «легаси»

В моделях продюсеров остались поля `Producer.asana_task_gid` и `ProducerComment.asana_story_id` — это **намеренно**. В них хранится историческая привязка к Asana, которая нужна для корректного отображения данных из локального дампа. Запись в эти поля больше нигде не происходит, новые комментарии создаются только через UI.

Удалять эти поля **не нужно** — это сломает данные из дампа.
