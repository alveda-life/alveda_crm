# Ayurveda CRM

CRM-система для бренда **Ask Ayurveda**: ведение партнёров и продюсеров, обработка звонков с автоматической транскрипцией и AI-саммари, оценка работы операторов, генерация регулярных и ad-hoc AI-отчётов.

Стек полностью контейнеризован и поднимается одной командой.

---

## Содержание

- [Технологический стек](#технологический-стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Переменные окружения](#переменные-окружения)
- [Структура репозитория](#структура-репозитория)
- [Основные модули](#основные-модули)
- [API](#api)
- [Учётные записи по умолчанию](#учётные-записи-по-умолчанию)
- [Полезные команды](#полезные-команды)
- [Подготовка к продакшену](#подготовка-к-продакшену)
- [Безопасность](#безопасность)
- [Решение типовых проблем](#решение-типовых-проблем)

---

## Технологический стек

**Backend**
- Python 3.11
- Django 4.2 + Django REST Framework
- SimpleJWT (JWT-аутентификация)
- django-cors-headers, django-filter
- APScheduler (фоновые задачи и регулярные отчёты)
- OpenAI Python SDK (транскрипция, саммари, фидбек, отчёты)
- Gunicorn (production-сервер)
- PostgreSQL 15

**Frontend**
- Vue 3 + Quasar Framework 2
- Pinia (state management)
- Vue Router
- Axios
- Vite (сборка)
- Marked (рендер markdown в AI-отчётах)
- Nginx (раздача SPA + reverse-proxy на backend)

**Инфраструктура**
- Docker + Docker Compose
- Healthcheck для PostgreSQL, restart policies для всех сервисов

---

## Архитектура

```
┌─────────────────────┐      ┌─────────────────────┐      ┌──────────────┐
│  Browser (SPA)      │ ───▶ │  frontend (nginx)   │ ───▶ │  backend     │
│  http://host:9000   │      │  :80 → SPA + /api   │ /api │  Django+DRF  │
└─────────────────────┘      │  proxy_pass         │ ───▶ │  :8000       │
                             └─────────────────────┘      └──────┬───────┘
                                                                 │
                                                                 ▼
                                                          ┌──────────────┐
                                                          │ PostgreSQL15 │
                                                          │   :5432      │
                                                          └──────────────┘
                                                                 ▲
                                                                 │
                                                          ┌──────┴───────┐
                                                          │ OpenAI API   │
                                                          │ (внешний)    │
                                                          └──────────────┘
```

- Frontend (`nginx:alpine`) отдаёт собранный SPA из `/usr/share/nginx/html` и проксирует `/api/` и `/media/` на сервис `backend:8000` внутри docker-сети.
- Backend (`python:3.11-slim`) запускает Django (через `runserver` в dev или `gunicorn` в проде), хранит данные в PostgreSQL, ходит во внешний OpenAI API.
- APScheduler-воркер крутится внутри backend-процесса и запускает регулярные задачи (см. [Регулярные задачи](#регулярные-задачи)).

---

## Быстрый старт

### Требования

- Docker Desktop (или Docker Engine 24+) с Compose v2
- ~2 ГБ свободной оперативной памяти
- Доступ к OpenAI API (ключ начинается с `sk-...`)

### 1. Клонирование

```bash
git clone https://github.com/alveda-life/alveda_crm.git
cd alveda_crm
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
# затем открыть .env и подставить реальные значения
```

Минимально достаточно заполнить:

- `OPENAI_API_KEY` — без него не будут работать транскрипция, саммари и AI-отчёты;
- `SECRET_KEY` — длинная случайная строка (≥50 символов).

### 3. Запуск

```bash
docker compose up -d --build
```

Первая сборка занимает 2–4 минуты (npm install + quasar build для фронта, pip install для backend).

### 4. Проверка

- Frontend: <http://localhost:9000>
- Backend API: <http://localhost:8000/api/>
- Django admin: <http://localhost:8000/admin/>

При первом запуске `entrypoint.sh` автоматически:

1. Дожидается готовности PostgreSQL.
2. Применяет миграции.
3. Собирает статику.
4. Создаёт суперпользователя `admin / admin123` и оператора `operator1 / operator123` (если их ещё нет).
5. Заполняет демо-данные через `manage.py seed_data` (если БД пустая).

---

## Переменные окружения

Все секреты лежат в `.env` (этот файл в `.gitignore`). Шаблон — в `.env.example`.

| Переменная | Назначение | Пример |
|---|---|---|
| `SECRET_KEY` | Django secret key | `<длинная случайная строка>` |
| `DEBUG` | Режим Django | `True` для dev, `False` для прода |
| `ALLOWED_HOSTS` | Разрешённые хосты | `localhost,127.0.0.1,backend,crm.example.com` |
| `CORS_ALLOWED_ORIGINS` | CORS-источники | `http://localhost:9000,https://crm.example.com` |
| `POSTGRES_DB` | Имя БД | `ayurveda_crm` |
| `POSTGRES_USER` | Пользователь БД | `crm_user` |
| `POSTGRES_PASSWORD` | Пароль БД | `<сильный пароль>` |
| `POSTGRES_HOST` | Хост БД | `db` (имя сервиса в compose) |
| `POSTGRES_PORT` | Порт БД | `5432` |
| `OPENAI_API_KEY` | Ключ OpenAI | `sk-proj-...` |
| `ASANA_PAT` | PAT для импорта продюсеров из Asana | `2/...` |
| `ASANA_PROJECT_GID` | GID проекта Asana | `1211963738224127` |
| `PARTNERS_CRM_API_KEY` | Ключ внешней CRM (импорт партнёров) | `<api-key>` |
| `PARTNERS_CRM_API_BASE` | URL внешней CRM | `https://example.com/api` |

---

## Структура репозитория

```
ayurveda-crm/
├── backend/                       Django-приложение
│   ├── crm/                       Настройки проекта (settings, urls, wsgi)
│   ├── accounts/                  Пользователи, роли, разрешения
│   ├── partners/                  Партнёры (CRM-воронка продаж)
│   ├── producers/                 Продюсеры (отдельная воронка onboarding)
│   ├── contacts/                  Звонки: транскрипция, саммари, фидбек
│   ├── tasks/                     Задачи и комментарии к ним
│   ├── reports/                   AI-отчёты + регулярные генераторы
│   ├── requirements.txt
│   ├── Dockerfile
│   └── entrypoint.sh
├── frontend/                      Quasar SPA
│   ├── src/
│   │   ├── pages/                 Страницы (≥30)
│   │   ├── components/            Переиспользуемые компоненты
│   │   ├── stores/                Pinia stores
│   │   ├── router/                Vue Router
│   │   └── boot/axios.js          HTTP-клиент с JWT-интерсептором
│   ├── quasar.config.js
│   ├── package.json
│   ├── nginx.conf                 Конфиг nginx для прод-образа
│   └── Dockerfile                 Multi-stage: build (node) → serve (nginx)
├── docker-compose.yml             Оркестрация: db + backend + frontend
├── rebuild-frontend.sh            Утилита: пересобрать только frontend-образ
├── .env.example                   Шаблон переменных окружения
├── .gitignore
└── README.md
```

---

## Основные модули

### `accounts` — пользователи и роли

- Кастомная модель `User` с полем `role` (`admin`, `manager`, `operator`, `producer_manager`).
- Гибкая модель `RolePermission` — администратор может на лету менять, какие разделы и кнопки доступны каждой роли.
- JWT-аутентификация: `POST /api/auth/login/` → `{ access, refresh }`.

### `partners` — партнёры (B2B-воронка)

- Категории, статусы, стадии воронки, контрольные даты.
- Аналитика по операторам, утилизации, конверсии.
- Импорт из внешней CRM: `python manage.py import_crm_contacts`.

### `producers` — продюсеры

- Отдельная воронка onboarding/support с расширенными полями (категория, потенциал сотрудничества, фарма-сертификаты).
- Канбан-доска, задачи, комментарии (с импортом исторических комментариев из Asana).
- AI-аналитика по «пассивным» формулировкам в комментариях.

### `contacts` — звонки и AI-обработка

- Загрузка аудио → асинхронная транскрипция через OpenAI Whisper.
- Саммаризация и оценка качества звонка через GPT.
- Ежедневный/еженедельный фидбек оператору с конкретными цитатами.
- Все долгие OpenAI-вызовы выполняются в `threading.Thread`, чтобы HTTP-запрос возвращался мгновенно (`{ queued: true }`).
- Авто-ретраи зависших операций (`auto_retry.py`).

### `reports` — AI-отчёты

Три типа отчётов:

1. **AI Reports** (`AiReport`) — ad-hoc отчёты по запросу пользователя.
2. **Producer Updates** (`ProducerUpdateReport`) — ежедневные/еженедельные сводки по продюсерам.
3. **Brand Situation** (`BrandSituationReport`) — анализ ситуации по бренду партнёра.

Регулярные отчёты планируются через APScheduler (`reports/scheduler.py`).

### `tasks` — задачи

CRUD задач с приоритетами, сроками, комментариями. Используется и в воронке партнёров, и в воронке продюсеров.

---

## API

Все защищённые endpoint'ы требуют заголовок `Authorization: Bearer <access_token>`.

### Аутентификация

```
POST /api/auth/login/      { username, password } → { access, refresh }
POST /api/auth/refresh/    { refresh } → { access }
GET  /api/auth/me/         → текущий пользователь
```

### Основные ресурсы

| Метод | Путь | Описание |
|---|---|---|
| `GET/POST` | `/api/contacts/` | Звонки |
| `GET/POST` | `/api/partners/` | Партнёры |
| `GET/POST` | `/api/producers/` | Продюсеры |
| `GET/POST` | `/api/tasks/` | Задачи |
| `GET/POST` | `/api/ai-reports/` | Ad-hoc AI-отчёты |
| `GET` | `/api/operator-feedback/` | AI-фидбек операторам |
| `GET` | `/api/producer-updates/` | Регулярные апдейты по продюсерам |
| `GET` | `/api/brand-situation/` | Отчёты по бренду |
| `GET` | `/api/analytics/operator-utilization/` | Утилизация операторов |
| `GET` | `/api/ai-operations/` | Статус и история фоновых AI-операций |
| `GET` | `/api/users/` | Пользователи |
| `*` | `/api/role-permissions/...` | Управление правами ролей |

Все list-endpoint'ы поддерживают `?search=`, `?ordering=`, фильтры через `django-filter` и пагинацию (по 100 на страницу).

---

## Учётные записи по умолчанию

После первого запуска (создаются автоматически в `entrypoint.sh`):

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin123` | Администратор |
| `operator1` | `operator123` | Оператор |

**Обязательно смените пароли** перед выкладкой на сервер.

---

## Полезные команды

### Логи

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

### Пересборка

```bash
docker compose build backend
docker compose build frontend            # или ./rebuild-frontend.sh
docker compose up -d --build              # пересобрать всё и перезапустить
```

### Django management

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py seed_data
docker compose exec backend python manage.py import_asana_producers
docker compose exec backend python manage.py sync_asana_comments
docker compose exec backend python manage.py rediarize_contacts
docker compose exec backend python manage.py resummarize_contacts
docker compose exec backend python manage.py import_crm_contacts
```

### Доступ к БД

```bash
docker compose exec db psql -U crm_user -d ayurveda_crm
```

### Полная перезагрузка с чистой БД

```bash
docker compose down -v        # ВНИМАНИЕ: удалит volume postgres_data
docker compose up -d --build
```

---

## Регулярные задачи

Запускаются APScheduler'ом внутри backend-процесса (см. `contacts/feedback_scheduler.py`, `reports/scheduler.py`):

- Ежедневный фидбек операторам (по итогам звонков за день).
- Еженедельный фидбек операторам.
- Ежедневный апдейт по продюсерам.
- Еженедельный апдейт по продюсерам.
- Авто-ретраи зависших AI-операций.

Для горизонтального масштабирования (несколько backend-инстансов) необходимо вынести scheduler в отдельный процесс или использовать механизм блокировок в БД.

---

## Подготовка к продакшену

Текущая конфигурация по умолчанию рассчитана на локальную разработку. Перед выкладкой на сервер:

1. **Установить `DEBUG=False`** в `.env`.
2. **Сгенерировать сильный `SECRET_KEY`** (≥50 случайных символов).
3. **Сменить пароль `admin`** и удалить/сменить `operator1`.
4. **Задать `ALLOWED_HOSTS`** под реальный домен.
5. **Задать `CORS_ALLOWED_ORIGINS`** под реальный фронтовый URL (https).
6. **Заменить `runserver` на `gunicorn`** в `backend/entrypoint.sh`:
   ```bash
   exec gunicorn crm.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
   ```
7. **Убрать bind-mount исходников** в продовом `docker-compose` — должны жить только артефакты image. Рекомендуется отдельный `docker-compose.prod.yml` без `./backend:/app`.
8. **Поставить reverse-proxy с TLS** (Traefik / Caddy / nginx) перед фронтом, включить HTTPS.
9. **Включить security-флаги** Django (при `DEBUG=False`):
   - `SECURE_SSL_REDIRECT = True`
   - `SECURE_HSTS_SECONDS = 31536000`
   - `SESSION_COOKIE_SECURE = True`
   - `CSRF_COOKIE_SECURE = True`
10. **Настроить бэкапы** PostgreSQL-volume и `media_data`.

---

## Безопасность

- `.env` находится в `.gitignore` и **не должен попадать в git**.
- Все ключи (`OPENAI_API_KEY`, `ASANA_PAT`, `PARTNERS_CRM_API_KEY`, `SECRET_KEY`) загружаются исключительно из переменных окружения.
- GitHub Push Protection включён в репозитории — секреты в коммитах будут отклонены автоматически.
- При смене сотрудников или подозрении на утечку — обязательно ротировать ключи: OpenAI, Asana, внешний CRM API.

---

## Решение типовых проблем

**Backend перезапускается в цикле**
Проверь логи: `docker compose logs backend`. Чаще всего — недоступен PostgreSQL или нет нужной переменной в `.env`.

**Frontend показывает белый экран / 404 на /api**
Перезапусти фронт: `./rebuild-frontend.sh`. Убедись, что nginx проксирует на `backend:8000` (см. `frontend/nginx.conf`).

**OpenAI-операции зависают в статусе `queued`**
Проверь, что `OPENAI_API_KEY` валиден и в `backend`-логах нет ошибок 401/429. Запусти ручной ретрай: `docker compose exec backend python manage.py shell` и вызови соответствующий runner.

**Изменения в коде Vue не подхватываются**
Контейнер `frontend` собирает SPA на этапе build. Для применения изменений нужна пересборка: `./rebuild-frontend.sh`.

**Ошибка миграций после `git pull`**
```bash
docker compose exec backend python manage.py migrate
```

**Нужно полностью пересоздать БД**
```bash
docker compose down -v && docker compose up -d --build
```

---

## Лицензия

Внутренний проект Ask Ayurveda. Все права защищены.
