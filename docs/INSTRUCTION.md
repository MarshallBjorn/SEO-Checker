# SEO Auditor — Instrukcja użytkowania

Dokument opisuje jak uruchomić aplikację lokalnie, zarejestrować się, wygenerować audyt i odebrać raport. Zakłada że masz zainstalowane: **Docker Desktop / Docker Engine + Compose**, **make**, oraz `git`.

---

## Spis treści

- [SEO Auditor — Instrukcja użytkowania](#seo-auditor--instrukcja-użytkowania)
  - [Spis treści](#spis-treści)
  - [1. Pierwsze uruchomienie](#1-pierwsze-uruchomienie)
  - [2. Konto i logowanie](#2-konto-i-logowanie)
  - [3. Tworzenie audytu z UI](#3-tworzenie-audytu-z-ui)
  - [4. Co audytujemy — kategorie i punktacja](#4-co-audytujemy--kategorie-i-punktacja)
  - [5. Konfiguracja audytu (suwaki, przełączniki)](#5-konfiguracja-audytu-suwaki-przełączniki)
  - [6. Historia i porównanie audytów](#6-historia-i-porównanie-audytów)
  - [7. Raporty PDF i wykresy PNG](#7-raporty-pdf-i-wykresy-png)
  - [8. Panel administratora](#8-panel-administratora)
  - [9. API (alternatywa do UI)](#9-api-alternatywa-do-ui)
  - [10. Bezpieczeństwo — co aplikacja egzekwuje](#10-bezpieczeństwo--co-aplikacja-egzekwuje)
  - [11. Troubleshooting](#11-troubleshooting)

---

## 1. Pierwsze uruchomienie

```bash
git clone <repo>
cd SEO-Checker
cp .env.example .env

# wygeneruj SECRET_KEY i wklej do .env w miejsce "change-me..."
python -c "import secrets; print(secrets.token_urlsafe(50))"

make dev       # build + start: postgres, redis, app, worker
make migrate   # alembic upgrade head
```

Po chwili (build Playwrighta + Chromium może trwać kilka minut przy pierwszym razie) aplikacja jest dostępna na:

- **UI:** http://localhost:8000
- **Swagger API:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

Zatrzymanie: `make down`. Logi na żywo: `make logs`.

---

## 2. Konto i logowanie

1. Wejdź na http://localhost:8000 — przekieruje na `/login`.
2. Kliknij **Zarejestruj się**, podaj email + hasło (min. 8 znaków). Po rejestracji jesteś od razu zalogowany.
3. Sesja trzymana jest w Redis (TTL 7 dni). Cookie `session_id` jest HttpOnly + SameSite=Lax.
4. Wylogowanie: przycisk **Wyloguj** w prawym górnym rogu — kasuje sesję serwerową i ciastko.

Hasła hashowane Argon2id. Aplikacja nie zna twojego hasła w plaintext po żadnym kroku.

---

## 3. Tworzenie audytu z UI

1. Po zalogowaniu → **Nowy audyt** (lub `/audit/new`).
2. Wpisz pełny URL (`https://example.com`). Adresy prywatne i lokalne są blokowane (zobacz §10).
3. Skonfiguruj parametry suwakami/przełącznikami (opcjonalnie — domyślne wartości są sensowne).
4. **Uruchom audyt**.

Audyt trwa zwykle **20–60 sekund** — strona renderuje się w headless Chromium, mierzymy Web Vitals, robimy screenshoty desktop + mobile. Status odświeża się automatycznie co 2s (HTMX polling).

Po zakończeniu dostajesz:
- **Score 0–100** (średnia ważona kategorii)
- Pojedyncze score'y per kategoria
- Przyciski: **Pobierz PDF**, **Wykres radar**, **Wykres bar**, **Pełny widok**

---

## 4. Co audytujemy — kategorie i punktacja

Każda kategoria zwraca listę `issues` z severity `info` / `warn` / `error` oraz lokalny score 0–100 (kara: info=-3, warn=-10, error=-20).

| Kategoria | Co sprawdzamy |
|---|---|
| **meta** | tag tytułu (długość 30–60), meta description (120–160), canonical, og:title/og:description/og:image, viewport |
| **headings** | dokładnie jeden H1, brak skoków poziomów (np. H1→H3 = warn), pełna hierarchia |
| **images** | obrazy bez alt, obrazy >100KB (jpeg/png), brak loading="lazy" |
| **links** | broken (4xx/5xx — HEAD/GET), ratio internal/external, rel="nofollow" na zewnętrznych |
| **performance** | LCP (cel <2500ms), CLS (cel <0.1), load_time, rozmiar HTML |
| **technicals** | HTTPS, robots.txt, sitemap.xml, redirect chain |
| **accessibility** | atrybut lang na html, pokrycie alt %, interaktywne elementy bez etykiety/aria |

**Score końcowy** = średnia ważona kategorii. Wagi są konfigurowalne (suwaki w formularzu) — domyślne: meta=20, headings=10, images=15, links=10, performance=25, technicals=10, accessibility=10.

---

## 5. Konfiguracja audytu (suwaki, przełączniki)

W formularzu masz:

- **User Agent** (radio): Googlebot / Chrome Desktop / Mobile Safari — wpływa na to jak strona się prezentuje (np. SSR vs JS-rendered).
- **Timeout** (suwak 5000–60000 ms): max czas oczekiwania na załadowanie strony.
- **Wagi kategorii** (7 suwaków 0–100): zmieniasz priorytet każdej kategorii w score końcowym. Wartość 0 = kategoria pomijana w średniej.
- **Aktywne kategorie** (7 checkboxów): wyłączasz kategorię całkowicie — nie liczy się ani w score, ani nie pokazuje issues.
- **Mobile viewport** (checkbox): renderowanie z viewportem 390×844 zamiast 1366×768.

Wszystkie te wartości lecą w body POST `/ui/audit` jako form-data, parsują się do `AuditSettings` (pydantic) i lądują w kolumnie `audits.settings` (JSON). Możesz powtórzyć audyt z dokładnie tą samą konfiguracją z historii.

---

## 6. Historia i porównanie audytów

- **`/history`** — lista wszystkich Twoich audytów (najnowsze na górze).
- **Porównaj dwa audyty** — formularz w `/history`, wybierz dwa, dostajesz widok obok siebie ze score'ami per kategoria i wykresami radarowymi.

Audyty są prywatne — widzisz tylko swoje. Wyjątek: admin widzi wszystkie.

---

## 7. Raporty PDF i wykresy PNG

W widoku wyniku audytu (status `done`):

- **Pobierz PDF** — `GET /audits/{id}/pdf`. Plik nazwany `audit-<domena>.pdf` (bez TLD), np. `audit-example.pdf`. Zawiera: score, wykres radarowy, tabela kategorii, wykres słupkowy problemów, pełna lista issues, screenshoty desktop + mobile.
- **Wykres radar** — `GET /audits/{id}/chart.png?type=radar`. PNG 800×800.
- **Wykres bar** — `GET /audits/{id}/chart.png?type=bar`. PNG ~800×500.

PDF generowany przez WeasyPrint (HTML → PDF), wykresy przez matplotlib (backend Agg, bez GUI). Generacja synchroniczna w request — przy bardzo dużych audytach może trwać 1–2 sek.

---

## 8. Panel administratora

Dostępny pod `/admin` dla użytkowników z rolą `admin`. Domyślnie po rejestracji każdy ma rolę `user` — pierwszego admina zrobisz ręcznie z poziomu Postgresa:

```bash
docker compose --env-file .env -f compose/docker-compose.dev.yml exec postgres \
  psql -U seoauditor -d seoauditor \
  -c "UPDATE users SET role='admin' WHERE email='twoj@email';"
```

W panelu:
- **`/admin`** — statystyki: liczba użytkowników, audytów, wpisów w logu.
- **`/admin/users`** — lista użytkowników (email, rola, status, data utworzenia).
- **`/admin/audit-log`** — ostatnie 200 wpisów z `audit_log` (login, register, audit.create, audit.pdf, audit.chart, success/fail, IP, user-agent).

---

## 9. API (alternatywa do UI)

Cała aplikacja ma symetryczne API JSON. Swagger UI: http://localhost:8000/docs.

Typowy flow z curl:

```bash
# rejestracja (form-encoded)
curl -X POST localhost:8000/auth/register \
  -d "email=test@example.com&password=Test1234!" -c c.txt

# audyt (JSON) — wymaga ciastka sesji
curl -X POST localhost:8000/audits \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","settings":{"weight_meta":30,"enable_headings":false}}' \
  -b c.txt

# polling statusu
curl localhost:8000/audits/<id> -b c.txt

# PDF
curl localhost:8000/audits/<id>/pdf -b c.txt -o report.pdf
```

> **CSRF:** JSON requesty są zwolnione z CSRF (SameSite=lax na ciastku wystarcza). Form-encoded POST-y od zalogowanego usera muszą mieć nagłówek `X-CSRF-Token` (frontend HTMX robi to automatycznie z meta tagu w `base.html`).

---

## 10. Bezpieczeństwo — co aplikacja egzekwuje

- **SSRF** — `is_safe_url` blokuje audyt URL-i prywatnych/lokalnych: RFC1918 (10/8, 172.16/12, 192.168/16), loopback (127/8), link-local (169.254/16 — w tym cloud metadata), reserved, multicast oraz IPv6 odpowiedniki. Tylko `http://` i `https://` — żadne `file://`, `ftp://`, `gopher://`.
- **Rate limit (slowapi):** POST /audits 10/min/IP, POST /auth/login 5/min/IP, POST /auth/register 3/min/IP.
- **CSRF:** token w sesji Redis, weryfikowany dla form-encoded POST od zalogowanych userów. Login/register zwolnione (nie ma jeszcze sesji w tym momencie).
- **Hasła:** Argon2id, min. 8 znaków.
- **Sesje:** server-side w Redis (db=2, osobno od broker/result), TTL 7 dni, cookie HttpOnly + SameSite=Lax (Secure automatycznie w APP_ENV=prod).
- **Izolacja audytów:** zwykły user widzi tylko swoje. Admin widzi wszystkie.
- **Audit log:** każda znacząca akcja (login, register, audit.create, audit.pdf, audit.chart, admin.action) loguje się do `audit_log` z IP i user-agentem.

---

## 11. Troubleshooting

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| `make migrate` — `column "user_id" contains null values` | Stare audyty bez user_id z wcześniejszego stanu | `docker compose exec postgres psql -U seoauditor -c "TRUNCATE audits;"` i `make migrate` ponownie |
| Audyt status `failed`, error: `'type' object does not support item assignment` | Literówka w kolektorze: `issues = list[Issue] = []` zamiast `:` | Popraw `=` na `:` w odpowiednim pliku w `app/auditor/collectors/` |
| `make test` — `RuntimeError: Event loop is closed` | Module-level async client (Redis/asyncpg) trzyma stary loop | Używaj TestClient jako context manager: `with TestClient(app) as c:` (patrz `tests/conftest.py`) |
| 500 na `/login`, `TypeError: unhashable type: 'dict'` | Stara sygnatura `templates.TemplateResponse(name, ctx)` | Nowy Starlette wymaga `templates.TemplateResponse(request, name, ctx)` |
| WeasyPrint w PDF endpointcie — `OSError: cannot load library 'libpango'` | Brak system deps w obrazie app | W `docker/Dockerfile.app` doinstaluj: libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 fonts-liberation |
| Audyt status `failed`, error: `net::ERR_*` | Playwright nie może załadować strony (offline / blok DNS / cert) | Sprawdź `make logs` (worker), zweryfikuj URL z `curl -I` |
| Brak dostępu do `/admin` mimo loginu | Rola nadal `user` | Ręczny UPDATE w psql (patrz §8) |

Logi:

```bash
make logs                                                 # wszystko
docker compose ... logs worker --tail=100                 # tylko worker (gdzie leci audyt)
docker compose ... logs app --tail=100                    # tylko aplikacja
```

---

**Autor:** Oleksij Navrotskyi
**Kontakt:** przez Issues w repozytorium
