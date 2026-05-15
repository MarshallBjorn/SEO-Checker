# SEO Checker

> Aplikacja webowa do audytu SEO pojedynczych stron WWW — renderuje stronę w headless Chromium, mierzy Core Web Vitals, parsuje HTML i generuje raporty PDF.

**Projekt akademicki:** `Przetwarzanie Danych w Chmurze Obliczeniowej`.

---

## Spis treści

- [SEO Checker](#seo-checker)
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

> 📖 **Korzystasz z aplikacji?** Pełna instrukcja użytkownika: [`docs/INSTRUCTION.md`](docs/INSTRUCTION.md)

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
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── templating.py
│   ├── models/             # SQLAlchemy: audit, user, audit_log
│   ├── schemas/            # Pydantic: AuditSettings, AuditResponse, UserResponse...
│   ├── routers/            # auth, audits, admin, frontend
│   ├── auditor/            # silnik audytu
│   │   ├── runner.py
│   │   ├── scoring.py
│   │   └── collectors/     # meta, headings, images, links, performance, technicals, accessibility
│   ├── auth/               # passwords (argon2), sessions (Redis), csrf, dependencies
│   ├── reports/            # pdf (WeasyPrint), charts (matplotlib), templates/audit_report.html
│   ├── middleware/         # audit_log, csrf, ssrf, rate_limit
│   ├── tasks/              # Celery: run_audit
│   ├── templates/          # Jinja2 + HTMX (base, login, dashboard, audit_form, audit_result, admin_*)
│   │   └── partials/       # audit_row, audit_status (HTMX fragments)
│   └── static/style.css
├── alembic/versions/       # migracje (initial, users, audit_user_fk_and_settings, audit_log)
├── tests/                  # test_auth, test_audit_full, test_ssrf, test_health
├── docs/
│   └── INSTRUCTION.md      # instrukcja użytkownika
├── docker/{Dockerfile.app, Dockerfile.worker}
├── compose/docker-compose.dev.yml
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
# 3. Uruchom
make dev
make migrate

# 4. Zarejestruj pierwsze konto przez UI lub curl, potem nadaj rolę admin:
docker compose --env-file .env -f compose/docker-compose.dev.yml exec postgres \
  psql -U seoauditor -d seoauditor -c "UPDATE users SET role='admin' WHERE email='twoj@email';"
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
| Szkielet FastAPI + Postgres + Celery | ✅ Gotowe |
| Auditor — 7 kolektorów (meta, headings, images, links, performance, technicals, a11y) | ✅ Gotowe |
| Playwright runner + Web Vitals + screenshoty | ✅ Gotowe |
| Reports — PDF (WeasyPrint) + wykresy radar/bar (matplotlib) | ✅ Gotowe |
| Konta + sesje Redis + role user/admin (argon2) | ✅ Gotowe |
| Audit Log middleware | ✅ Gotowe |
| Frontend HTMX (suwaki, przełączniki, radio) | ✅ Gotowe |
| Panel admina (users, audit log, stats) | ✅ Gotowe |
| Bezpieczeństwo: CSRF, rate limit, SSRF | ✅ Gotowe |
| Smoke testy (auth, audit, SSRF) | ✅ Gotowe |
| CI (GitHub Actions) | 🟡 W trakcie |
| Backup (restic) + deployment OpenStack | ⬜ Wieczór 4 |

## Autorzy

`Oleksij Navrotskyi`

---

**Przedmiot:** `Oleksij Navrotskyi`
**Rok akademicki:** 2025/2026
