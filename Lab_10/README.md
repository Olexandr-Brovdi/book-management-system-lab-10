# Book Catalog 1.0.0

Лабораторна робота №10 «Production Python: Docker, CI/CD та захист проєкту».  
**Варіант №2 — «Система обліку книг» · Бровді Олександр · ФеП-32**  
Львівський національний університет імені Івана Франка. Курс «Професійний Python».  
Перевірив: Свелеба Сергій Андрійович. Дата: 09.11.2026.

## Призначення та стан підготовки

Продовження власного проєкту Lab_01–Lab_09: книги й автори, пошук за автором,
фільтрація за роком, найбільша книга, середня кількість сторінок. Збережено
CSV/JSON/YAML, immutable Book, Service/Repository/Unit of Work, SQLite/Alembic,
FastAPI REST API, async HTTPX batch, NumPy та кеш зі скиданням після зміни даних.
Distribution `book-catalog`, import module `book_catalog`, версія `1.0.0`, MIT.

Додано environment settings, logging, DB-aware `/health`, installable CLI,
packaged migration assets, Docker/Compose та GitHub Actions matrix.
Локальні результати й логи збережено в `docs/results`.

**Публікацію та CI відкладено за рішенням користувача.** GitHub створив репозиторій,
але відхилив push workflow через відсутній OAuth scope `workflow`; нового входу
не виконували. Наявність ci.yml не означає green CI. Docker CLI встановлено,
проте Engine недоступний, а керування Docker Desktop не дозволене системою
доступу. Docker image/container поки не підтверджено фактичним запуском.
Ці обмеження відкрито зазначені у звіті та checklist, без підміни результатів.

## Структура

```text
.github/workflows/ci.yml      # Python 3.11/3.12; quality → package → Docker
src/book_catalog/
  api.py, config.py, runtime.py
  database.py, persistence/  # SQLAlchemy, Service/Repository/UoW
  migration_assets/          # installed wheel can migrate without checkout
  swagger_assets/            # local Swagger UI and third-party license
  analytics.py, parallel.py, profiling.py
  ...                       # domain and CSV/JSON/YAML
tests/unit/, tests/integration/
migrations/, data/, benchmarks/
Dockerfile, .dockerignore, compose.yaml, .env.example
pyproject.toml, README.md, LICENSE
dist/                       # wheel + sdist, included in submission
tools/wheel_smoke.py         # clean installed-wheel check
tools/docker_smoke.py        # real health/env/CRUD/volume restart check
tools/validate_submission.py
docs/results/, docs/screenshots/, docs/control_answers.json
docs/Lab_10_Report_Variant_2.docx
Lab_10/                     # autonomous copy
  report/report.docx         # canonical report, identical to docs copy
```

## Встановлення та запуск

Python 3.11+. Команди PowerShell із кореня проєкту або автономної папки `Lab_10`:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,report]"
.venv/Scripts/book-catalog --host 127.0.0.1 --port 8000
```

Альтернатива: `python -m book_catalog.runtime` або
`uvicorn book_catalog.api:app --host 127.0.0.1 --port 8000`.
Production entry point не вмикає reload. Попередній export CLI збережено як
`book-export --config config.yaml --author Франко`, а SQLite demo — `book-library`.
Demo може змінювати демонстраційну БД; це окрема команда, не startup production API.

## Configuration та secrets

`.env` необов’язковий. Скопіюйте `.env.example` для власної локальної конфігурації;
process environment має пріоритет. Не додавайте реальних credentials у Git.
Цей SQLite-сервіс не потребує вигаданих API keys/passwords.

| Змінна | Default | Правило |
|---|---|---|
| APP_NAME | Book Catalog API | заголовок OpenAPI |
| APP_ENV / ENVIRONMENT | development | development / test / production |
| DATABASE_URL | sqlite:///data/library.db | persistent SQLite file URL |
| LOG_LEVEL | INFO | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| BOOK_UPSTREAM_URL | http://127.0.0.1:8000 | trusted server configuration for async batch |
| BOOK_HTTP_TIMEOUT | 2 | positive finite seconds per HTTP request |
| BOOK_BATCH_TIMEOUT | 10 | positive finite seconds per batch |
| BOOK_HTTP_ATTEMPTS | 3 | 1..5, includes first attempt |
| BOOK_HTTP_CONCURRENCY | 3 | 1..20 per app/process |
| BOOK_HTTP_BACKOFF | 0.05 | finite ≥0; exponential backoff |

Explicit `create_app(database=...)` має пріоритет. Старий `BOOK_DATABASE`, якщо
заданий, підтримано для сумісності й він переважає DATABASE_URL. Для нового
запуску використовуйте DATABASE_URL. APP_ENV має пріоритет над ENVIRONMENT.
Відхиляються in-memory SQLite URL, інший backend, credentials, host/query у URL.
Migrations застосовуються при startup. SQLAlchemy sessions належать окремим
операціям; blocking DB calls виконуються в threadpool.

```powershell
$env:APP_ENV="production"
$env:LOG_LEVEL="DEBUG"
$env:DATABASE_URL="sqlite:///data/library.db"
.venv/Scripts/book-catalog
```

У logging є timestamp, level і logger name. Startup повідомляє environment/version,
не database credentials. `.env`, `.env.*`, virtual environments і робочі БД
ігноруються Git; `.env.example` дозволено. Docker context також виключає `.env`.

## REST API та демонстрація варіанта 2

Swagger: `/docs`; ReDoc: `/redoc`; машинний контракт: `/openapi.json`.
Swagger JS/CSS включено в wheel, CDN не потрібний.

| Method | Path | Призначення |
|---|---|---|
| GET | /health | 200 status/environment/version; 503 при недоступній БД |
| GET | / | ідентифікація Lab_10, variant2 |
| GET / POST | /authors | список / створення автора |
| GET / PATCH / DELETE | /authors/{id} | CRUD автора; delete cascade |
| GET | /authors/{id}/books | книги автора |
| POST | /authors/batch | async HTTPX, Task/gather, timeout/retry/Semaphore |
| GET / POST | /books | список / створення книги |
| GET / PATCH / DELETE | /books/{id} | CRUD книги |
| GET | /books/statistics | count, average_pages, largest |

Почніть із POST /authors `{"name":"Іван Франко"}`. Отриманий ID передайте в
POST /books `{"title":"Захар Беркут","author_id":1,"year":1883,"pages":192}`.
Далі GET `/books?author=Іван%20Франко&year=1883`, GET `/books/statistics`,
PATCH `/books/1` `{"pages":200}`, DELETE `/books/1`.
201 — створення; 204 — видалення без body; 404 — missing; 409 — conflict;
422 — validation; 503/504 — upstream failure/timeout. PATCH змінює лише
передані поля, null дозволено тільки для isbn. `/health` виконує SELECT1 і
не повертає шлях БД або конфіденційні параметри.

## Packaging

```powershell
.venv/Scripts/python -m build
.venv/Scripts/python -m twine check dist/*
python -m venv .wheel-check
.wheel-check/Scripts/pip install dist/book_catalog-1.0.0-py3-none-any.whl
.wheel-check/Scripts/book-catalog --help
```

Запустіть `tools/wheel_smoke.py` саме інтерпретатором чистого wheel environment
з іншої робочої папки: script перевіряє health, міграції, CRUD, filter/statistics,
Swagger assets і збереження SQLite після restart. Встановлення не editable.
Runtime не шукає `alembic.ini` у checkout: migration resources включено в wheel.
sdist та wheel перебувають у `dist`; їхні розміри й SHA-256 — у build evidence.

## Docker та Compose

Ці команди підготовлено; для їх виконання потрібний працюючий Docker Engine:

```powershell
docker build -t book-catalog:ci .
docker run --rm -p 127.0.0.1:8000:8000 -e APP_ENV=production -e LOG_LEVEL=INFO -e DATABASE_URL=sqlite:////app/data/library.db -v book_data:/app/data book-catalog:ci
docker compose up --build -d
docker compose ps
```

Multi-stage build готує wheelhouse в builder, а runtime встановлює готовий wheel.
API запускається як non-root UID10001; `/app/data` доступний цьому користувачу.
Named volume зберігає SQLite після видалення контейнера. HEALTHCHECK читає
`/health`. EXPOSE документує8000, а публікацію порту задає `-p`.
`--env-file .env` також підтримується Docker; приватний файл не копіюється в image.

`python tools/docker_smoke.py` після build tag `book-catalog:ci` перевіряє actual
image, UID, environment, running/healthy state, API, створення книги й повторний
запуск на тому самому volume. Script видаляє лише власні UUID test containers/volume.
При успіху він створить `docs/results/docker.json` і `docker.log`. Відсутність
цих успішних доказів у поточній підготовці не підмінюється прикладними даними.

## Quality та CI/CD

```powershell
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
.venv/Scripts/mypy src
.venv/Scripts/python -m pytest -v
```

Mypy перевіряє application source з `check_untyped_defs=true`; deployment copies
Alembic scripts виключені з обходу, а помилки застосунку не приховано широкими
ignore_errors. Ruff виключає дубльовану автономну папку Lab_10 та build artifacts.
Тести перевіряють старий domain/SQL/API/analytics контракт та нову configuration,
health200/503, restart persistence і відповідність packaged migrations.
Coverage threshold85% застосовується й у CI.

Workflow: push main / pull_request / manual dispatch → Python3.11/3.12 quality
matrix → Ruff lint/format → mypy → pytest/coverage → wheel/sdist/twine → clean
wheel install/smoke → Docker build/run/health/volume restart → artifact upload.
Actions закріплено за commit SHA перевірених офіційних releases. Workflow має
contents:read і не потребує власних secrets. Delivery тут — підготовка artifacts;
автоматичного deployment у сторонні сервіси або публікації в PyPI/Docker Hub немає.

Після надання дозволу GitHub `workflow` можна завантажити всі локальні commits
і фактично перевірити CI. До цього його статус — **NOT RUN**, а не green.
Повний звіт містить усі70 контрольних запитань і відповідей та чесний checklist
виконаних/непідтверджених перевірок. Номер варіанта й предметна область збережені.
