#!/bin/bash
# OpenStack deployment orchestration for SEO Auditor.
# Run on DevStack VM after: source /opt/stack/devstack/openrc admin admin
set -euo pipefail

[ -z "${OS_AUTH_URL:-}" ] && { echo "Source OpenStack openrc first"; exit 1; }
command -v jq >/dev/null || { echo "jq required (apt install jq)"; exit 1; }

REPO_URL="https://github.com/MarshallBjorn/SEO-Checker"
IMAGE="ubuntu-2204-navrotskyi-base"
KEYPAIR="navrotskyi-keypair"
NETWORK="shared"

SECRETS_FILE="${SECRETS_FILE:-.deploy-secrets}"
if [ ! -f "$SECRETS_FILE" ]; then
    echo "==> Generating secrets in $SECRETS_FILE"
    cat > "$SECRETS_FILE" <<EOF
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
RESTIC_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
EOF
    chmod 600 "$SECRETS_FILE"
fi
# shellcheck disable=SC1090
source "$SECRETS_FILE"

server_ip() {
    openstack server show "$1" -f json \
        | jq -r '.addresses | to_entries[].value[]' \
        | grep -E '^192\.168\.[0-9]+\.[0-9]+$' | head -1
}

create_server() {
    local name="$1" flavor="$2" sg="$3" userdata="$4"
    if openstack server show "$name" >/dev/null 2>&1; then
        echo "==> $name exists, skipping create"
        return
    fi
    echo "==> Creating $name ($flavor, $sg)"
    openstack server create "$name" \
        --image "$IMAGE" \
        --flavor "$flavor" \
        --network "$NETWORK" \
        --security-group "$sg" \
        --key-name "$KEYPAIR" \
        --user-data "$userdata" \
        --wait
}

# --- db ---
sed "s|__INSERT_DB_PASSWORD__|$DB_PASSWORD|g" \
    cloud-init/db.yaml > /tmp/db-userdata.yaml
create_server db-navrotskyi m1.small sg-db-navrotskyi /tmp/db-userdata.yaml
DB_IP=$(server_ip db-navrotskyi)
echo "db-navrotskyi IP: $DB_IP"

# --- backup ---
sed "s|__INSERT_RESTIC_PASSWORD__|$RESTIC_PASSWORD|g" \
    cloud-init/backup.yaml > /tmp/backup-userdata.yaml
create_server backup-navrotskyi m1.small sg-backup-navrotskyi /tmp/backup-userdata.yaml
BACKUP_IP=$(server_ip backup-navrotskyi)
echo "backup-navrotskyi IP: $BACKUP_IP"

# --- app ---
sed -e "s|__INSERT_SECRET__|$APP_SECRET_KEY|g" \
    -e "s|__INSERT_DB_PASSWORD__|$DB_PASSWORD|g" \
    -e "s|__INSERT_RESTIC_PASSWORD__|$RESTIC_PASSWORD|g" \
    -e "s|__DB_INSTANCE_IP__|$DB_IP|g" \
    -e "s|__BACKUP_INSTANCE_IP__|$BACKUP_IP|g" \
    cloud-init/app.yaml > /tmp/app-userdata.yaml
create_server app-navrotskyi m1.medium sg-app-navrotskyi /tmp/app-userdata.yaml
APP_IP=$(server_ip app-navrotskyi)

# Floating IP — reuse existing if app already has one
EXISTING_FIP=$(openstack server show app-navrotskyi -f json \
    | jq -r '.addresses | to_entries[].value[]' \
    | grep -vE '^192\.168\.' | head -1 || true)
if [ -n "$EXISTING_FIP" ]; then
    FIP="$EXISTING_FIP"
    echo "Reusing floating IP: $FIP"
else
    FIP=$(openstack floating ip create public -f value -c floating_ip_address)
    openstack server add floating ip app-navrotskyi "$FIP"
fi

cat <<EOF

===== DEPLOYMENT COMPLETE =====
db-navrotskyi:     $DB_IP
backup-navrotskyi: $BACKUP_IP
app-navrotskyi:    $APP_IP (Floating: $FIP)

Open http://$FIP in browser
Wait ~3-5 minutes for cloud-init to finish on all instances.
Follow logs: ssh navrotskyi@<ip> 'sudo tail -f /var/log/cloud-init-output.log'
EOF
