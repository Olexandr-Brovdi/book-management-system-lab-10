"""Build both identical Lab_10 reports from actual code, logs and coverage."""

from pathlib import Path
import ast
import json
import re
import shutil
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]


def build() -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin, section.right_margin = Cm(2.5), Cm(1.5)
    for name in ["Normal", "Title", "Heading 1", "Heading 2"]:
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12 if name == "Normal" else 14)
        style.font.color.rgb = RGBColor(0, 0, 0)
    for border in doc.styles.element.xpath(".//w:pBdr"):
        border.getparent().remove(border)
    normal = doc.styles["Normal"].paragraph_format
    normal.line_spacing = 1.05
    normal.space_after = Pt(5)

    def clean_text(text):
        return re.sub(
            r"(?<=[А-Яа-яІіЇїЄєҐґ])(?=\d)|(?<=\d)(?=[А-Яа-яІіЇїЄєҐґ])", " ", str(text)
        )

    def p(text):
        return doc.add_paragraph(clean_text(text))

    def h(text):
        doc.add_heading(text, level=1)

    def page(title):
        doc.add_page_break()
        h(title)

    def code(text, size=8.5):
        para = p("")
        para.paragraph_format.line_spacing = 1
        run = para.add_run(text.strip())
        run.font.name, run.font.size = "Consolas", Pt(size)

    def read(path):
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def function(path, name):
        text = read(path)
        for item in ast.walk(ast.parse(text)):
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == name
            ):
                start = min([item.lineno, *[d.lineno for d in item.decorator_list]])
                return "\n".join(text.splitlines()[start - 1 : item.end_lineno])
        raise ValueError(name)

    def picture(name, caption):
        doc.add_picture(
            str(ROOT / "docs/screenshots" / (name + ".png")), width=Cm(16.6)
        )
        p(caption)

    def table(headers, rows, widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.autofit = False
        for i, value in enumerate(headers):
            t.rows[0].cells[i].text = str(value)
        for row in rows:
            for cell, value in zip(t.add_row().cells, row):
                cell.text = clean_text(value)
        for rownum, row in enumerate(t.rows):
            for i, cell in enumerate(row.cells):
                if widths:
                    cell.width = Cm(widths[i])
                properties = cell._tc.get_or_add_tcPr()
                borders = OxmlElement("w:tcBorders")
                for edge in ["top", "left", "bottom", "right"]:
                    border = OxmlElement("w:" + edge)
                    for key, value in [
                        ("val", "single"),
                        ("sz", "4"),
                        ("color", "D9D9D9"),
                    ]:
                        border.set(qn("w:" + key), value)
                    borders.append(border)
                properties.append(borders)
                margins = OxmlElement("w:tcMar")
                for edge in ["top", "left", "bottom", "right"]:
                    margin = OxmlElement("w:" + edge)
                    margin.set(qn("w:w"), "75")
                    margin.set(qn("w:type"), "dxa")
                    margins.append(margin)
                properties.append(margins)
                if rownum == 0:
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:fill"), "D9E2F3")
                    properties.append(shading)
                    for run in cell.paragraphs[0].runs:
                        run.bold = True
                for para in cell.paragraphs:
                    para.paragraph_format.space_after = Pt(3)
                    for run in para.runs:
                        run.font.size = Pt(10)
        p("")

    summary = json.loads(read("docs/results/summary.json"))
    wheel = json.loads(read("docs/results/wheel.json"))
    cover = [
        ("ЛЬВІВСЬКИЙ НАЦІОНАЛЬНИЙ УНІВЕРСИТЕТ\nІМЕНІ ІВАНА ФРАНКА", 14, 65),
        ("ЗВІТ ДО ЛАБОРАТОРНОЇ РОБОТИ №10", 16, 20),
        ("«Production Python: Docker, CI/CD та захист проєкту»", 14, 18),
        ("з курсу «Професійний Python»\nВаріант №2 — «Система обліку книг»", 14, 45),
        (
            "Виконав: Бровді Олександр\nГрупа: ФеП-32\nПеревірив(ла): Свелеба Сергій Андрійович\nДата: 09.11.2026",
            12,
            70,
        ),
        ("Львів — 2026", 14, 0),
    ]
    for i, (text, size, after) in enumerate(cover):
        para = doc.add_paragraph(text, "Title" if i == 1 else None)
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after = Pt(after)
        for run in para.runs:
            run.font.size = Pt(size)

    page("1. Мета та фактичний стан роботи")
    p(
        "Мета — підготувати власний Python-проєкт до production-oriented використання: installable package, wheel/sdist, environment configuration, logging, secrets management, Docker, CI/CD та документація фінального захисту."
    )
    p(
        "Варіант №2 — «Система обліку книг». Книга має назву, автора, рік і кількість сторінок. Збережено додавання книг, пошук за автором, фільтр за роком, найбільшу книгу та середню кількість сторінок. Продовжено domain/CSV/JSON/YAML, Service/Repository/Unit of Work, SQLite/Alembic, REST API Lab_08 і NumPy/caching Lab_09."
    )
    p(
        f"Фактично виконано локально: {summary['tests']} passed, {summary['failed']} failed; Ruff lint і format, mypy, wheel/sdist build, twine metadata check та встановлення wheel у чисте virtual environment. Перевірено /health, API, packaged migrations, Swagger assets і restart persistence. Distribution: book-catalog 1.0.0, import module: book_catalog."
    )
    p(
        "Docker image зібрано й запущено на GitHub-hosted Ubuntu runner. GitHub Actions завершився зі статусом Success: quality на Python 3.11 і 3.12 та Docker job. Підтверджено health, non-root UID 10001, environment, CRUD, Swagger і persistence після повторного створення контейнера."
    )
    p(
        "Фактичні докази збережено в docs/results/ci.json і docker.json; наведено скріншот зеленого pipeline та результати docker images/ps. Перевірений commit 015b773 і run 42627788856 доступні в публічному репозиторії Olexandr-Brovdi/book-management-system-lab-10. Локальні та CI результати позначені за місцем виконання."
    )

    page("2. Структура фінального проєкту")
    code(
        """book-management-system-lab-10/
  .github/workflows/ci.yml
  pyproject.toml, README.md, LICENSE
  Dockerfile, .dockerignore, compose.yaml, .env.example
  src/book_catalog/
    config.py, runtime.py, api.py
    database.py, persistence/      # Service/Repository/UoW/ORM
    migration_assets/             # installed migrations
    swagger_assets/               # installed Swagger JS/CSS
    analytics.py, parallel.py, profiling.py
    models.py, catalog.py, importers.py, exporters.py, ...
  migrations/, data/, benchmarks/, config.yaml, alembic.ini
  tests/unit/, tests/integration/
  tools/wheel_smoke.py, docker_smoke.py, capture_results.py
  tools/build_report.py, validate_submission.py
  dist/book_catalog-1.0.0-py3-none-any.whl
  dist/book_catalog-1.0.0.tar.gz
  docs/results/, docs/screenshots/, docs/control_answers.json
  docs/Lab_10_Report_Variant_2.docx
  Lab_10/                         # автономна копія
    report/report.docx""",
        9,
    )
    p(
        "Збережено src-layout та звичну ієрархію з наданого зразка: src, tests, tools, docs та автономна Lab_10/report. Нові production files розташовано в корені. Virtual environments, caches, робочі БД та .env не включаються до submission. Wheel і sdist включено як готові результати пакування."
    )
    p(
        "Окремий публічний GitHub repository: https://github.com/Olexandr-Brovdi/book-management-system-lab-10. Код та звіт опубліковано; quality matrix і Docker job завершилися успішно. Корінь проєкту та автономна папка Lab_10 містять однакові source, tests, configuration та artifacts."
    )

    page("3. Package metadata та pyproject.toml")
    pyproject = read("pyproject.toml")
    code(pyproject[: pyproject.index("[tool.setuptools.packages.find]")], 8.5)
    p(
        "Name book-catalog відповідає варіанту2, а Python package book_catalog використовує underscore для import. Версія1.0.0 оформлена як MAJOR.MINOR.PATCH. README описує систему та стан перевірок; MIT license включено в distribution. Runtime dependencies відокремлено від dev/report extras."
    )
    p(
        "Entry point book-catalog запускає production API, book-export зберігає попередню CSV→JSON demonstration, book-library — SQLite demo. Build backend setuptools>=77 підтримує metadata license у поточному форматі. Залежності встановлюються менеджером пакетів, а не копіюються з локального .venv."
    )

    page("4. Environment configuration у config.py")
    config = read("src/book_catalog/config.py")
    code(config[config.index("class Settings") : config.index("@dataclass")], 9)
    p(
        "Pydantic-settings читає environment і необов’язковий .env. Process environment переважає .env. APP_ENV має пріоритет над ENVIRONMENT; дозволені development/test/production. LOG_LEVEL перевіряється за визначеним набором. DATABASE_URL має посилатися на persistent SQLite file; in-memory, інший backend, credentials, host і query відхиляються."
    )
    p(
        "У create_app explicit database argument має найвищий пріоритет, потім legacy BOOK_DATABASE, потім Settings.database_path із DATABASE_URL. Старий YAML loader для export CLI збережено. Production API не залежить від локального config.yaml або абсолютного шляху автора."
    )

    page("5. .env.example та робота із secrets")
    code(read(".env.example"), 10)
    p(
        "У .env.example наведено тільки безпечні defaults. Реальних passwords, tokens, private keys або credentials у source, README, Dockerfile та workflow немає. Для SQLite не вигадуються непотрібні secrets. GitHub authentication використовувалася поза repository; її дані не включено до архіву."
    )
    code(read(".gitignore"), 9)
    p(
        "У Git дозволено .env.example, а .env та .env.* ігноруються. Ті самі приватні файли виключено з Docker context. GitHub Secrets можуть бути використані пізніше через secrets.NAME, але цей quality/build workflow не потребує власних secrets або токенів registry."
    )
    code(
        """$env:APP_ENV="production"
$env:LOG_LEVEL="DEBUG"
$env:DATABASE_URL="sqlite:///data/library.db"
.venv/Scripts/book-catalog --host 127.0.0.1 --port 8000""",
        10,
    )

    page("6. Production entry point та logging")
    code(read("src/book_catalog/runtime.py"), 9)
    p(
        "Команда book-catalog доступна після встановлення wheel. Вона запускає Uvicorn без development reload, читає Settings і використовує environment log level. Logger містить час, рівень і назву; повторний startup не додає дубльовані handlers. Повідомлення startup/shutdown не містять database credentials."
    )
    p(
        "Logging використовується для сервісних подій, а print у CLI/tools показує результат команд і доказів. Production та development відрізняються configuration, а не окремою копією source code. Host default127.0.0.1; у контейнері явно задано0.0.0.0."
    )

    page("7. Portable migrations усередині wheel")
    code(function("src/book_catalog/database.py", "upgrade_database"), 10)
    code(
        """[tool.setuptools.package-data]
book_catalog = [
  "swagger_assets/*",
  "migration_assets/*",
  "migration_assets/versions/*",
]""",
        10,
    )
    p(
        "Виправлено залежність startup від checkout: upgrade_database використовує importlib.resources, а не parents[2]/alembic.ini. Migration env і versions0001/0002 включено в installed package. Тест звіряє їх зі збереженими development migrations. Swagger JS/CSS також поставляється локально разом із ліцензією."
    )
    p(
        "Це важлива різниця між успішним editable install і придатним до встановлення wheel. Чисте wheel environment не має src-layout checkout у import path, однак створює schema та працює з API. Транзакції, FK enforcement і Unit of Work попереднього проєкту збережено."
    )

    page("8. Wheel та sdist build")
    code(
        """python -m build
python -m twine check dist/*""",
        11,
    )
    table(
        ["Artifact", "Bytes"],
        [(r["name"], r["bytes"]) for r in summary["artifacts"]],
        [12, 4.6],
    )
    for artifact in summary["artifacts"]:
        p(artifact["name"])
        code("SHA-256: " + artifact["sha256"], 8.5)
    picture(
        "dist",
        "Знімок локальної сторінки з фактичним вмістом папки dist та її розмірами. Джерело — створені distribution files.",
    )
    p(
        "Повний build output збережено в docs/results/build.txt. Обидва formats пройшли twine check; wheel перевірено на наявність migration і Swagger resources та відсутність .env/.pyc/__pycache__. sdist дозволяє повторно побудувати package з вихідних файлів."
    )

    page("9. Чисте встановлення wheel та smoke test")
    code(
        """python -m venv .wheel-check
.wheel-check/Scripts/pip install dist/book_catalog-1.0.0-py3-none-any.whl
$labRoot = (Get-Location).Path
Set-Location $env:TEMP
& "$labRoot/.wheel-check/Scripts/book-catalog" --help
& "$labRoot/.wheel-check/Scripts/python" (Join-Path $labRoot "tools/wheel_smoke.py")""",
        9,
    )
    p(
        "Середовище створено без system-site-packages і без editable install. Перевірку виконано з окремої робочої папки. Імпортована копія book_catalog розташована у site-packages clean environment, а не у src repository. Інстальовано саме зібраний wheel і його runtime dependencies."
    )
    code(json.dumps(wheel, ensure_ascii=False, indent=2), 9)
    p(
        "Smoke test створює свіжу SQLite БД, запускає lifespan та packaged migrations, читає /health, створює автора й книгу, перевіряє year filter, average/largest statistics і Swagger assets. Після restart на тій самій БД книга зберігається. Це фактична перевірка встановленого distribution; вона не є перевіркою Docker container."
    )

    page("10. REST API та /health")
    code(function("src/book_catalog/api.py", "health"), 9.5)
    p(
        "GET /health перевіряє SELECT1 у worker thread. Успішна відповідь200 містить status, environment і version; SQLAlchemyError перетворюється на503 із безпечним code. Шлях БД та credentials не повертаються. Тести перевіряють обидва стани та environment override."
    )
    table(
        ["Method", "Endpoint", "Призначення"],
        [
            ("GET", "/health", "ready200 або unavailable503"),
            ("GET / POST", "/books", "список/створення"),
            ("GET / PATCH / DELETE", "/books/{id}", "отримання/зміна/видалення"),
            ("GET / POST", "/authors", "автори"),
            ("GET / PATCH / DELETE", "/authors/{id}", "CRUD автора"),
            ("GET", "/authors/{id}/books", "книги автора"),
            ("GET", "/books/statistics", "count, average_pages, largest"),
            ("POST", "/authors/batch", "async HTTPX + Task/gather"),
        ],
        [4.3, 6, 6.3],
    )
    p(
        "API Lab_08 збережено: author/year filters, pagination/sort, schema validation, PATCH exclude_unset, status codes201/204/404/409/422, upstream503/504. Новий health не змінює поведінку domain CRUD. OpenAPI, Swagger /docs і ReDoc /redoc документують routes."
    )

    page("11. Screenshot Swagger установленого пакета")
    picture(
        "swagger",
        "Справжній Swagger UI локального API, запущеного з wheel у чистому virtual environment. Версія1.0.0, Lab_10, variant2.",
    )
    p(
        "Swagger assets завантажуються з установленого book_catalog, без CDN і без checkout/src. Цей знімок підтверджує локальний запуск installed package. Він не подається як знімок контейнера, який у поточному середовищі запустити не вдалося."
    )

    page("12. Dockerfile та .dockerignore")
    code(read("Dockerfile"), 8.5)
    p(
        "Builder створює wheel і dependency wheelhouse. Runtime stage установлює їх без доступу до package index, видаляє build wheels і запускає API як appuser, UID10001. У image немає development tools, source checkout, .env або звіту. EXPOSE документує порт8000, CMD запускає production entry point."
    )
    code(read(".dockerignore"), 8.5)

    page("13. Контейнер, healthcheck та persistent volume")
    code(
        """docker build -t book-catalog:ci .
docker run --rm -p 127.0.0.1:8000:8000 \
  -e APP_ENV=production -e LOG_LEVEL=INFO \
  -e DATABASE_URL=sqlite:////app/data/library.db \
  -v book_data:/app/data book-catalog:ci
docker compose up --build -d
docker compose ps""",
        9,
    )
    code(read("compose.yaml"), 10)
    p(
        "Named volume відокремлює SQLite від lifecycle контейнера. /app/data створено з правами appuser; HEALTHCHECK використовує urllib і /health із timeout. Compose публікує порт лише на127.0.0.1. docker compose config --quiet пройшов локальну перевірку configuration."
    )
    p(
        "Docker build/run фактично виконано у GitHub Actions. Локально Docker Engine недоступний, тому використано GitHub-hosted Ubuntu runner. Named volume пережив видалення та повторне створення контейнера, і книга «Захар Беркут» залишилася доступною. Джерело — artifact docker-evidence цього CI run."
    )

    page("14. Результати запуску Docker")
    p(
        "tools/docker_smoke.py успішно виконав Docker commands на Ubuntu runner після build image book-catalog:ci. Використано UUID names для тестового контейнера й volume; після збереження evidence видалено лише власні тестові ресурси."
    )
    p(
        "Статус сценарію PASS. Image sha256:0e9e47673361…; configured user appuser, фактичний UID 10001; state running/healthy; APP_ENV=production, LOG_LEVEL=DEBUG. Перезапуск із тим самим volume підтвердив збереження даних. Нижче наведено фактичний вивід команд, отриманий із CI artifact."
    )
    picture(
        "docker",
        "Фактичні docker images/ps, health, environment та volume proof із GitHub runner; джерело docs/results/docker.json.",
    )

    workflow = read(".github/workflows/ci.yml")
    page("15. GitHub Actions quality matrix")
    code(workflow.split("  docker:")[0], 8.5)
    p(
        "Workflow запускається на push main, pull_request та workflow_dispatch. Matrix перевіряє Python3.11 і3.12 на ubuntu-latest. Quality виконує lint, format, mypy, pytest/coverage, build, metadata check, clean wheel install/smoke та upload artifacts. Actions закріплено за SHA перевірених офіційних releases; permissions обмежено contents:read."
    )

    page("16. Docker job та фактичний статус CI")
    code("  docker:" + workflow.split("  docker:")[1], 9)
    p(
        "Docker job залежить від успіху quality matrix. Він будує image, запускає підготовлений Docker smoke scenario і зберігає evidence artifact. Pipeline не публікує image у сторонній registry і не виконує автоматичний deployment. Тут Continuous Delivery означає підготовку перевірених package artifacts."
    )
    p(
        "Фактичний CI run 42627788856 завершився зі статусом Success. Коміт 015b773006968d61624b592b81d0cce1ff19cb2e перевірено на Python 3.11 і 3.12; Docker job успішно зібрав і запустив image. Усі три jobs зелені; збережено три artifacts: два package-and-tests та docker-evidence."
    )
    code(
        "https://github.com/Olexandr-Brovdi/\nbook-management-system-lab-10/actions/runs/42627788856\nquality (3.11): success\nquality (3.12): success\ndocker: success",
        9,
    )
    p(
        "CI підтвердив lint, formatting, mypy, 222 тести, coverage threshold, wheel/sdist, metadata check і clean installed wheel. Docker підтвердив production environment, HTTP health та volume persistence. Успішний запуск тривав 1 хв 48 с. Скриншот наведено на наступній сторінці."
    )

    page("16.1 Підтверджений green CI")
    picture(
        "ci",
        "GitHub Actions run 42627788856 — Success; quality Python 3.11/3.12 та Docker, три artifacts.",
    )
    p(
        "Скріншот реального публічного run; повний URL і metadata збережено в docs/results/ci.json."
    )

    page("17. Lint, formatting та type checking")
    picture(
        "quality",
        "Фрагменти фактичних локальних Ruff і mypy logs; зображення сформовано з docs/results/*.txt.",
    )
    p(
        "Ruff check і ruff format --check завершилися успішно. Виключено дубльовану папку Lab_10 та build/virtual-environment artifacts. Перевіряються application source, tests, tools і benchmarks. Mypy перевірив25 source files з check_untyped_defs=true, без широкого ignore_errors."
    )
    p(
        "Виправлено typing boundary atomic_output: повертається underlying IO[str] temporary file. Для pstats runtime attributes, яких немає в установлених stubs, додано вузький Protocol і TypedDict ProfileRow; повна точність profiling data збережена. Ці зміни не приховують помилки глобальним вимкненням перевірки."
    )

    page("18. Pytest та coverage")
    picture(
        "tests",
        "Фрагмент справжнього pytest -v; повний журнал та JUnit включено до docs/results.",
    )
    cov = summary["coverage"]
    table(
        ["Показник", "Результат"],
        [
            ("Tests / failures", f"{summary['tests']} / {summary['failed']}"),
            (
                "Statement coverage",
                f"{cov['covered_lines']}/{cov['num_statements']} = {cov['percent_statements_covered']:.2f}%",
            ),
            (
                "Branch coverage",
                f"{cov['covered_branches']}/{cov['num_branches']} = {cov['percent_branches_covered']:.2f}%",
            ),
            ("Combined coverage", f"{cov['percent_covered']:.2f}%; поріг85% виконано"),
        ],
        [7.5, 9.1],
    )
    p(
        "Збережено попередні213 cases; production tests перевіряють environment/.env precedence, invalid DB URL, log level, /health200/503, API persistence після restart і відповідність migration copies. У журналі є одне DeprecationWarning залежності Starlette/AnyIO щодо BlockingPortal; його не приховано. Покриття не доводить всіх можливих production scenarios."
    )

    page("19. README та сценарій демонстрації")
    p(
        "README описує предметну систему, distribution/module names, installation, environment variables і пріоритети, local run, API CRUD, Docker/Compose, tests, CI/CD, source structure та наявні обмеження. LICENSE й third-party Swagger license включено. Docstrings пояснюють boundary responsibilities біля коду."
    )
    code(
        """# Локальна частина захисту
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest -v
python -m build
python -m twine check dist/*
book-catalog --host 127.0.0.1 --port 8000
# Показати /health, /docs, створити автора та книгу

# Відтворення перевіреного Docker сценарію
docker build -t book-catalog:ci .
python tools/docker_smoke.py
git push -u origin main
# Перевірити фактичний run у GitHub Actions""",
        10,
    )
    p(
        "Основна архітектура: Client → FastAPI → Pydantic → Service → Repository/Unit of Work → SQLite. Packaging не замінює domain validation або транзакції. NumPy, bounded author cache і async HTTPX залишаються доступними компонентами попередніх робіт."
    )
    p(
        "Демонстрація підтверджена фактичними даними: /health повертає environment/version, Swagger описує API, CRUD створює автора й книгу, statistics обчислює 192.0 сторінки, а Docker volume зберігає книгу після recreate. Результати runner відокремлено від локальних перевірок."
    )

    page("20. Git commits та production checklist")
    code(read("docs/results/git.txt"), 9)
    p(
        "Наведено знімок історії Git перед остаточним оновленням звіту. Коміти опубліковано в новому публічному репозиторії для Lab_10. Authentication files, tokens і приватний .env зберігаються поза repository. Фінальне оформлення доказів додається окремим commit."
    )
    table(
        ["Перевірка", "Стан"],
        [
            ("src-layout, metadata, version, LICENSE", "PASS"),
            ("Ruff lint / format / mypy", "PASS"),
            ("Pytest / coverage threshold", "PASS"),
            ("wheel / sdist / twine", "PASS"),
            ("clean wheel install / API / migrations", "PASS"),
            ("/health200/503, DB restart persistence", "PASS"),
            (".env ignored / .env.example / no embedded credentials", "PASS"),
            ("README / workflow / Dockerfile / Compose", "PASS"),
            ("docker compose config", "PASS"),
            ("Docker image build / container / volume test", "PASS: GitHub runner"),
            ("GitHub push / green CI / CI artifacts", "PASS: Success, 3 jobs"),
            ("External Laboratory Checker", "Після публікації звіту"),
        ],
        [11, 5.6],
    )

    answers = json.loads(read("docs/control_answers.json"))
    for start in range(0, 70, 10):
        page(f"21. Контрольні запитання {start + 1}–{start + 10}")
        for n, (question, answer) in enumerate(answers[start : start + 10], start + 1):
            para = p(f"{n}. {question}")
            para.paragraph_format.space_after = Pt(2)
            for run in para.runs:
                run.bold = True
                run.font.size = Pt(11)
            para = p(answer)
            para.paragraph_format.space_after = Pt(7)
            for run in para.runs:
                run.font.size = Pt(10.5)

    page("22. Висновок")
    p(
        "Локально підготовлено production-oriented версію системи обліку книг: конфігурація через environment, logging, DB-aware health endpoint, installable entry point, wheel/sdist, portable migration і Swagger resources. Збережено domain, persistence, REST API, async і analytics частини. Усі222 тести та локальні quality/build checks успішні, clean installed wheel підтвердив працездатність без checkout."
    )
    p(
        "Docker multi-stage build, non-root runtime, HEALTHCHECK і persistent volume перевірено на GitHub-hosted runner. GitHub Actions на Python 3.11 і 3.12 та Docker job завершилися успішно. Pipeline створює wheel/sdist і тестові artifacts. Повторний запуск контейнера зберіг книгу на volume."
    )
    p(
        "Код, документацію та звіт опубліковано в окремому public repository book-management-system-lab-10. Структура містить автономну папку Lab_10 та канонічний звіт Lab_10/report/report.docx. До звіту додано реальні Docker/CI докази та всі 70 контрольних відповідей для варіанта №2."
    )
    p(
        "Результат роботи — відтворюваний production-oriented сервіс обліку книг із перевіреним installed wheel, Docker runtime та автоматичним quality pipeline. Перевірка Laboratory Checker виконується окремо після публікації остаточної версії; її оцінку не підмінено результатами pytest або CI."
    )
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    target = ROOT / (
        "report/report.docx" if ROOT.name == "Lab_10" else "Lab_10/report/report.docx"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target)
    if ROOT.name != "Lab_10":
        shutil.copy2(target, ROOT / "docs/Lab_10_Report_Variant_2.docx")
    print(
        "Lab_10 report completed;70 answers; actual Docker runtime and green CI evidence"
    )


if __name__ == "__main__":
    build()
