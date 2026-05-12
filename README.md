# SEO Checker

> Aplikacja webowa do audytu SEO pojedynczych stron WWW — renderuje stronę w headless Chromium, mierzy Core Web Vitals, parsuje HTML i generuje raporty PDF.

**Projekt akademicki:** `Przetwarzanie Danych w Chmurze Obliczeniowej`.

---

## Spis treści

- [SEO Auditor](#seo-auditor)
  - [Spis treści](#spis-treści)
  - [O projekcie](#o-projekcie)
  - [MVP](#mvp)
  - [Moduły](#moduły)
  - [Stack technologiczny](#stack-technologiczny)
  - [Struktura repozytorium](#struktura-repozytorium)
  - [Development workflow](#development-workflow)
    - [Pierwszy setup po klonowaniu repo](#pierwszy-setup-po-klonowaniu-repo)
    - [Codzienna praca](#codzienna-praca)
    - [CI](#ci)
  - [Status projektu](#status-projektu)
  - [Autorzy](#autorzy)

---

## O projekcie

SEO Auditor to aplikacja webowa do automatycznego audytu SEO stron internetowych. Użytkownik podaje URL, konfiguruje parametry przez interaktywne kontrolki (suwaki, przełączniki, wybór user-agenta), a aplikacja uruchamia headless browser (Playwright), zbiera metryki i generuje raport PDF.

Aplikacja jest skonteneryzowana (Docker Compose) — może działać lokalnie jako jeden compose lub jako wdrożenie wielomaszynowe (osobne compose'y per rola: app, db, backup).

Audyty trwają 20–60s (renderowanie strony w Chromium), więc uruchamiane są asynchronicznie przez Celery. Frontend (HTMX) pollluje status w tle.

## MVP

- **Audyt jednej strony WWW** — URL na wejściu, raport na wyjściu
- **Sprawdzane kategorie:** meta tagi, struktura nagłówków, obrazy (alt-y), Core Web Vitals (LCP, CLS), linki (broken 4xx/5xx), technicalia (robots.txt, sitemap, HTTPS), accessibility (lang, aria)
- **Kontrolki:** suwaki (timeout, wagi kategorii), przełączniki (włącz/wyłącz kategorie, mobile/desktop), radio (user-agent)
- **Raporty PDF** — pełny audyt z wykresami radarowymi i screenshotami (desktop + mobile)
- **Konta użytkowników** — rejestracja, login (sesje), role `user` / `admin`
- **Audit log** — middleware logujący znaczące akcje (login, audyt, generacja PDF)
- **Backupy** — nocny cron, restic, retention 7d/4w/3m
- **API + Swagger UI** — `/docs` z auto-generowaną dokumentacją

## Moduły

| Moduł | Odpowiedzialność |
|---|---|
| **Auditor** | Silnik audytu. Playwright runner, parsery HTML (BeautifulSoup), kolektory metryk (meta, headings, images, links, vitals, technicals, a11y), scoring. |
| **Reports** | Generacja PDF (WeasyPrint) i wykresów PNG (matplotlib). Historia audytów per user, porównanie dwóch audytów tej samej strony. |
| **Accounts** | Rejestracja, logowanie, sesje server-side, role, polityka haseł (argon2). |
| **Audit Log** | Middleware FastAPI logujące akcje do tabeli `audit_log`. Panel admina do przeglądania i filtrowania. |
| **Backup** | Cron (`backup.sh`) wywołuje `pg_dump` + restic push. Endpoint `/admin/backups` pokazuje stan snapshotów. |

## Stack technologiczny

- **Backend:** FastAPI + Uvicorn
- **ORM:** SQLAlchemy 2.0 (async) + Alembic
- **DB:** PostgreSQL 16
- **Auth:** sesje server-side (cookies)
- **Frontend:** Jinja2 + HTMX + Alpine.js + Tailwind (CDN)
- **Crawl:** Playwright (Chromium headless)
- **HTML parsing:** BeautifulSoup4 + lxml
- **PDF:** WeasyPrint
- **Wykresy:** matplotlib (Agg backend)
- **Task queue:** Celery + Redis
- **Reverse proxy:** nginx
- **Backupy:** restic + cron
- **Konteneryzacja:** Docker + Docker Compose

## Struktura repozytorium

```
seo-auditor/
├── app/                    # FastAPI
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models/             # SQLAlchemy
│   ├── schemas/            # Pydantic
│   ├── routers/            # auth, audits, reports, admin
│   ├── services/           # auditor, playwright_runner, pdf, charts, backup
│   ├── middleware/         # audit log
│   ├── tasks/              # Celery tasks
│   ├── templates/          # Jinja2 + HTMX
│   └── static/
├── alembic/                # Migracje
├── tests/                  # pytest
├── nginx/
│   └── nginx.conf
├── docker/
│   ├── Dockerfile.app
│   └── Dockerfile.worker   # z Playwright
├── compose/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.app.yml
│   ├── docker-compose.db.yml
│   └── docker-compose.backup.yml
├── scripts/
│   ├── backup.sh
│   ├── restore.sh
│   └── create_admin.py
├── .env.example
├── pyproject.toml
└── README.md
```

## Development workflow

### Pierwszy setup po klonowaniu repo

```bash
# 1. Skopiuj env
cp .env.example .env
# Wygeneruj SECRET_KEY i wklej
python -c "import secrets; print(secrets.token_urlsafe(50))"

# 2. Pre-commit hooks (lokalne, jednorazowo)
pip install pre-commit detect-secrets
pre-commit install
detect-secrets scan > .secrets.baseline

# 3. Uruchom
make dev
make migrate
make createsuperuser
```

### Codzienna praca

```bash
make dev              # Start środowiska
make logs             # Logi live
make shell            # Bash w kontenerze app
make test             # Testy
make lint             # ruff check + format
make format           # Auto-format
make migrate          # alembic upgrade head
make migration        # alembic revision --autogenerate
```

### CI

Każdy push i PR przechodzi przez GitHub Actions:
- **Lint** — ruff check + format
- **Tests** — pytest z coverage
- **Docker build** — sprawdzenie buildowania obrazu

PR nie zostanie zmergowany jeśli CI jest czerwony.

## Status projektu

| Moduł | Status |
|---|---|
| Szkielet FastAPI | 🟡 W trakcie |
| Auditor — core | ⬜ Zaplanowane |
| Auditor — Playwright runner | ⬜ Zaplanowane |
| Reports — PDF | ⬜ Zaplanowane |
| Reports — wykresy | ⬜ Zaplanowane |
| Accounts | ⬜ Zaplanowane |
| Audit Log | ⬜ Zaplanowane |
| Frontend (HTMX) | ⬜ Zaplanowane |
| Celery + tasks | ⬜ Zaplanowane |
| Backup (restic) | ⬜ Zaplanowane |
| CI | ⬜ Zaplanowane |

## Autorzy

`Oleksij Navrotskyi`

---

**Przedmiot:** `<NAZWA PRZEDMIOTU>`
**Prowadzący:** `<PROWADZĄCY>`
**Rok akademicki:** 2025/2026
