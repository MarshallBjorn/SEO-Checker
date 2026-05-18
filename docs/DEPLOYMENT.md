# Deployment na OpenStack

Procedura wdrożenia SEO Auditora jako 3-instancyjna aplikacja w OpenStacku (DevStack).

## Architektura

```
                       Internet
                          │
                          ▼
              ┌────────────────────┐
              │  Floating IP       │
              └─────────┬──────────┘
                        │
                        ▼
   ┌─────────────────────────────────────┐
   │  app-navrotskyi (m1.app-navrotskyi) │
   │    nginx :80 → app :8000            │
   │    + worker (Celery + Playwright)   │
   │    + redis (sesje + broker)         │
   │    + cron (nocny backup)            │
   └───┬─────────────────────────────┬───┘
       │ tenant 192.168.233.0/24     │
       ▼                             ▼
   ┌────────────────┐         ┌─────────────────┐
   │ db-navrotskyi  │         │ backup-navrotskyi│
   │ postgres :5432 │         │ restic-rest :8000│
   │ (m1.small)     │         │ (m1.small)       │
   └────────────────┘         └─────────────────┘
```

Floating IP tylko dla `app-navrotskyi`. Komunikacja db ↔ backup ↔ app po tenant network. Security groups ograniczają porty (SSH/HTTP z zewnątrz, 5432/8000 tylko z sg-app).

## Wymagania wstępne

### OpenStack (DevStack)

- Bazowy obraz: `ubuntu-2204-navrotskyi-base` (Ubuntu 22.04 cloud, ~2.6 GB)
- Security groups:
  - `sg-app-navrotskyi` — ingress 22 (z DevStack), 80 (0.0.0.0/0), ICMP
  - `sg-db-navrotskyi` — ingress 22 (z DevStack), 5432 (z sg-app)
  - `sg-backup-navrotskyi` — ingress 22 (z DevStack), 8000 (z sg-app)
- Keypair: `navrotskyi-keypair`
- Custom flavor: `m1.app-navrotskyi` (1-4 vCPU, 2 GB RAM, 15 GB disk)
- Sieć tenant: `shared` (192.168.233.0/24)

### GitHub

- Repo publiczne: `https://github.com/MarshallBjorn/SEO-Checker`
- GitHub Actions włączone — workflow `build-images.yml` buduje 3 obrazy (app/worker/cron) i pushuje do GHCR przy każdym pushu do `main`
- Pakiety w GHCR ustawione jako **public** (inaczej instancja nie pullnie bez auth)

## Procedura deployu

### 1. Na DevStack VMce

```bash
# Sklonuj repo
git clone https://github.com/MarshallBjorn/SEO-Checker ~/seo-auditor
cd ~/seo-auditor

# Source credentiali OpenStacka
source /opt/stack/devstack/openrc admin admin

# Sprawdź że jq jest (deploy.sh wymaga)
sudo apt-get install -y jq

# Sprawdź wymagania
openstack image list | grep ubuntu-2204-navrotskyi-base
openstack security group list | grep navrotskyi   # 3 sztuki
openstack keypair list | grep navrotskyi
openstack flavor show m1.app-navrotskyi -f value -c vcpus -c disk
```

### 2. Uruchom deploy

```bash
bash scripts/deploy.sh
```

Co robi skrypt:
1. Generuje secrety do `.deploy-secrets` (DB_PASSWORD, RESTIC_PASSWORD, APP_SECRET_KEY)
2. Tworzy `db-navrotskyi` (m1.small) z cloud-init
3. Tworzy `backup-navrotskyi` (m1.small) z cloud-init
4. Tworzy `app-navrotskyi` (m1.app-navrotskyi) z cloud-init
5. Przypisuje floating IP do app

Skrypt jest **idempotentny** — istniejące instancje pomija.

### 3. Czekaj 5-10 min na cloud-init

Każda instancja wykonuje:
1. Ustawia MTU 1280 na `ens3` (rozwiązanie problemu MTU OVN)
2. Konfiguruje docker daemon (`/etc/docker/daemon.json`: MTU 1280, DNS 8.8.8.8 1.1.1.1)
3. Restart docker
4. Czeka na DNS
5. `git clone https://github.com/MarshallBjorn/SEO-Checker /opt/seo-auditor`
6. Przenosi `.env` z `/tmp` do `/opt/seo-auditor/.env`
7. (Tylko app) czeka aż db:5432 i backup:8000 odpowiedzą TCP
8. `docker compose up -d` z odpowiednim compose.yaml

Obserwacja na żywo:
```bash
APP_FIP=$(openstack server show app-navrotskyi -f json | jq -r '.addresses | to_entries[].value[]' | grep -vE '^192\.168\.')
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP 'sudo tail -f /var/log/cloud-init-output.log'
```

### 4. Weryfikacja

```bash
APP_FIP=$(openstack server show app-navrotskyi -f json | jq -r '.addresses | to_entries[].value[]' | grep -vE '^192\.168\.')

# Health
curl -sS http://$APP_FIP/health
# Oczekiwane: {"status":"ok"}

# Status kontenerów
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  cd /opt/seo-auditor
  sudo docker compose --env-file .env -f compose/docker-compose.app.yml ps
"
```

Powinno być widać: `nginx`, `app` (healthy), `worker`, `redis` (healthy), `cron`.

## Dostęp z przeglądarki (Windows host)

Aplikacja działa na floating IP `10.0.2.X` które jest dostępne **tylko z DevStack VMki**. Żeby otworzyć w przeglądarce Windowsa, potrzeba:

### A. Dodaj bridged adapter do DevStack VMki (jednorazowo)

W VirtualBox:
- Settings → Network → Adapter 2 → Bridged Adapter
- Wybierz interfejs Wi-Fi/Ethernet hosta

Po starcie DevStacka:
```bash
sudo ip link set eth1 up
sudo dhclient eth1
ip addr show eth1 | grep inet
```

Trwale (netplan):
```bash
sudo tee /etc/netplan/60-bridge.yaml >/dev/null <<EOF
network:
  version: 2
  ethernets:
    eth1:
      dhcp4: true
EOF
sudo netplan apply
```

### B. iptables DNAT (jednorazowo lub przez systemd service)

```bash
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-forward.conf

APP_FIP=10.0.2.245   # podstaw aktualny

sudo iptables -P FORWARD ACCEPT
sudo iptables -t nat -A PREROUTING -i eth1 -p tcp --dport 80 -j DNAT --to-destination $APP_FIP:80
sudo iptables -t nat -A POSTROUTING -o eth0 ! -s 10.0.2.15 -j MASQUERADE
sudo iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

**WAŻNE:** `-i eth1` w PREROUTING — bez tego DNAT złapie też ruch z localhost i położy Horizon na :80.

Po tym: `http://<eth1-ip>` w przeglądarce Windowsa.

### Persistujący systemd service (opcjonalnie)

`/etc/systemd/system/seo-iptables.service`:
```ini
[Unit]
Description=SEO Auditor iptables DNAT rules
After=network-online.target openvswitch-switch.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/seo-iptables-up.sh

[Install]
WantedBy=multi-user.target
```

`/usr/local/sbin/seo-iptables-up.sh`:
```bash
#!/bin/bash
set -e
source /opt/stack/devstack/openrc admin admin
APP_FIP=$(openstack server show app-navrotskyi -f json 2>/dev/null \
  | jq -r '.addresses | to_entries[].value[]' \
  | grep -vE '^192\.168\.' | head -1)
[ -z "$APP_FIP" ] && exit 1

iptables -t nat -C PREROUTING -i eth1 -p tcp --dport 80 -j DNAT --to-destination $APP_FIP:80 2>/dev/null \
  || iptables -t nat -A PREROUTING -i eth1 -p tcp --dport 80 -j DNAT --to-destination $APP_FIP:80
iptables -t nat -C POSTROUTING -o eth0 ! -s 10.0.2.15 -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -o eth0 ! -s 10.0.2.15 -j MASQUERADE
iptables -P FORWARD ACCEPT
sysctl -w net.ipv4.ip_forward=1
```

```bash
sudo chmod +x /usr/local/sbin/seo-iptables-up.sh
sudo systemctl enable --now seo-iptables.service
```

Reguły dograją się po każdym boocie z **aktualnym** FIP.

## Restart instancji

```bash
# Soft reboot (graceful)
openstack server reboot app-navrotskyi

# Hard reboot (kill)
openstack server reboot --hard app-navrotskyi

# Stop + start (gdy chcesz czysty stan)
openstack server stop app-navrotskyi
openstack server start app-navrotskyi
```

Po restarcie:
- `restart: unless-stopped` w compose → kontenery wstają same
- Floating IP może się zmienić → zaktualizuj iptables (systemd service robi to automatycznie)

## Troubleshooting

### Cloud-init padło — kontenery nie wstały
```bash
# SSH do instancji
ssh -i ~/navrotskyi_key ubuntu@<FIP-lub-tenant-IP>

# Logi cloud-init
sudo tail -100 /var/log/cloud-init-output.log

# Najczęściej: git clone padło na timeout DNS — ręcznie:
sudo rm -rf /opt/seo-auditor
sudo git clone https://github.com/MarshallBjorn/SEO-Checker /opt/seo-auditor
# Przenieś .env z /tmp jeśli zostało:
sudo mv /tmp/seoauditor.env /opt/seo-auditor/.env 2>/dev/null
cd /opt/seo-auditor
sudo docker compose --env-file .env -f compose/docker-compose.app.yml up -d
```

### 502 Bad Gateway na nginx
App container nie wstał albo nginx ma cached stary IP po recreate app:
```bash
sudo docker compose --env-file .env -f compose/docker-compose.app.yml restart nginx
```

### App `unhealthy` — migrate się zacina
```bash
sudo docker compose --env-file .env -f compose/docker-compose.app.yml logs migrate --tail 30
```
Najczęściej: nie dosięga `DB_HOST`. Sprawdź czy postgres na `db-navrotskyi` chodzi.

### DNS w kontenerach nie działa (`gaierror: name resolution`)
Restart docker z naszym `/etc/docker/daemon.json` (mtu + dns):
```bash
sudo systemctl restart docker
sudo docker compose --env-file .env -f compose/docker-compose.app.yml up -d --force-recreate
```

### Aktualizacja aplikacji po pushu do GitHuba
GitHub Actions buduje nowe obrazy GHCR przy każdym pushu do `main`. Na instancji:
```bash
ssh -i ~/navrotskyi_key ubuntu@$APP_FIP "
  cd /opt/seo-auditor
  sudo git pull
  sudo docker compose --env-file .env -f compose/docker-compose.app.yml pull
  sudo docker compose --env-file .env -f compose/docker-compose.app.yml up -d --force-recreate
  sudo docker compose --env-file .env -f compose/docker-compose.app.yml restart nginx
"
```

## Decyzje deploymentowe

| Decyzja | Uzasadnienie |
|---|---|
| 3 instancje (nie 1) | Separacja warstw, security groups jako firewall |
| Floating IP tylko dla app | db i backup niedostępne z internetu |
| Restic na osobnej instancji | Backup poza maszyną aplikacji |
| Custom flavor `m1.app-navrotskyi` (15 GB) | Standard m1.medium ma 40 GB — nie mieści się w 80 GB DevStack hosta razem z innymi instancjami |
| MTU 1280 | OVN tenant ma MTU 1442; transfer >1442 B fragmentuje się i throughput pada |
| DNS `8.8.8.8` w docker daemon | systemd-resolved na instancji okresowo gubi się; explicit DNS w dockerze omija |
| MASQUERADE wszystkiego z eth0 | OVN router SNAT-uje na FIP, ale VBox NAT nie zna FIP-ów → trzeba 2-krotnego NAT |
| GHCR build pipeline | Build na instancji (1 vCPU, brak hardware virt) trwa godziny; GHCR runner buduje w 3 min |
