# Backup i restore

## Architektura

```
   app-navrotskyi              backup-navrotskyi
   ┌──────────┐                ┌──────────────────┐
   │ cron     │                │ restic/rest-server│
   │ 03:00    │                │ port 8000        │
   │ codziennie                │                  │
   │          │                │ /data            │
   │ backup.sh├────────────────► (volume restic_data)
   └──────────┘   restic push  └──────────────────┘
        │
        │ pg_dump
        ▼
   db-navrotskyi
   ┌──────────┐
   │ postgres │
   │ :5432    │
   └──────────┘
```

`cron` w kontenerze na app-navrotskyi codziennie o 03:00 odpala `/scripts/backup.sh`:
1. `pg_dump` z db-navrotskyi → `/tmp/seoauditor-{timestamp}.sql.gz`
2. `restic backup` do backup-navrotskyi
3. `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 3 --prune`
4. Usunięcie lokalnego dumpu

## Bezpieczeństwo

- Restic REST server bez auth (`--no-auth`) — security group `sg-backup-navrotskyi` ogranicza dostęp **tylko z `sg-app`**
- Snapshoty szyfrowane symetrycznie kluczem `RESTIC_PASSWORD` (generowany losowo przy deploy, zapisany w `.deploy-secrets` na DevStacku)
- DB credentials trzymane w `.env` z `0600` na każdej instancji

## Polityka retencji

Skonfigurowane w `scripts/backup.sh`:
- 7 dziennych snapshotów
- 4 tygodniowe
- 3 miesięczne

## Sprawdzenie ostatnich backupów

### Z UI

`http://<adres-app>/admin/backups` — tabela: timestamp, ID snapshotu, host, tagi, ścieżki.

### Z CLI

```bash
APP_FIP=$(openstack server show app-navrotskyi -f json | jq -r '.addresses | to_entries[].value[]' | grep -vE '^192\.168\.')

ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  sudo docker exec seo-checker-app-cron-1 restic snapshots
"
```

## Manualne wywołanie backupu

### Przez UI

`http://<adres-app>/admin/backups` → przycisk **„Wymuś backup teraz"**. Wrzuca task do Celery, worker odpala backup.sh, zakończenie po 30-60s.

### Przez SSH (direct)

```bash
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  sudo docker exec seo-checker-app-cron-1 /scripts/backup.sh
"
```

## Restore

Skrypt `scripts/restore.sh` w cron containerze. Restoruje **do osobnej bazy** `${DB_NAME}_restore` — nie nadpisuje produkcyjnej. Po weryfikacji ręczny swap.

```bash
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP

# Skopiuj restore.sh do cron containera (jednorazowo)
sudo docker cp /opt/seo-auditor/scripts/restore.sh seo-checker-app-cron-1:/scripts/restore.sh
sudo docker exec seo-checker-app-cron-1 chmod +x /scripts/restore.sh

# Restore najnowszego snapshotu
sudo docker exec seo-checker-app-cron-1 /scripts/restore.sh latest

# Albo konkretnego snapshotu
sudo docker exec seo-checker-app-cron-1 /scripts/restore.sh 7af1cd4e
```

Restore:
1. `restic restore latest --target /tmp/restore`
2. Znajdź `seoauditor-*.sql.gz`
3. `DROP DATABASE IF EXISTS seoauditor_restore` + `CREATE DATABASE seoauditor_restore`
4. `gunzip | psql ...seoauditor_restore`

### Weryfikacja restore

Porównaj liczność tabel w `seoauditor` i `seoauditor_restore`:

```bash
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  sudo docker exec seo-checker-app-app-1 sh -c '
    echo \"=== prod ===\"
    psql \"postgresql://\$DB_USER:\$DB_PASSWORD@\$DB_HOST/\$DB_NAME\" -c \"SELECT count(*) FROM users; SELECT count(*) FROM audits; SELECT count(*) FROM audit_logs;\"
    echo \"=== restore ===\"
    psql \"postgresql://\$DB_USER:\$DB_PASSWORD@\$DB_HOST/seoauditor_restore\" -c \"SELECT count(*) FROM users; SELECT count(*) FROM audits; SELECT count(*) FROM audit_logs;\"
  '
"
```

Liczby powinny być identyczne.

### Swap prod ↔ restore (gdy weryfikacja OK)

```bash
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  sudo docker exec seo-checker-app-app-1 psql \
    \"postgresql://\$DB_USER:\$DB_PASSWORD@\$DB_HOST/postgres\" -c \"
      ALTER DATABASE seoauditor RENAME TO seoauditor_old;
      ALTER DATABASE seoauditor_restore RENAME TO seoauditor;
    \"
"

# Restart app żeby reconnect do nowej bazy
sudo docker compose --env-file .env -f compose/docker-compose.app.yml restart app worker migrate
```

`seoauditor_old` zostaje jako safety net. Usuń ręcznie po sprawdzeniu że nowa działa:

```sql
DROP DATABASE seoauditor_old;
```

## Cleanup snapshotów

Forget retencja działa automatycznie po każdym `backup.sh`. Manualne:

```bash
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  sudo docker exec seo-checker-app-cron-1 sh -c '
    restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 3 --prune
  '
"
```

## Konfiguracja cron

W `docker/Dockerfile.cron`:
```
0 3 * * * /scripts/backup.sh >> /var/log/backup.log 2>&1
```

Logi: `docker exec seo-checker-app-cron-1 cat /var/log/backup.log`
