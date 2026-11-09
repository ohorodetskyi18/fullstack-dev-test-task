#!/usr/bin/env bash
# One-click Ghost deployment with no public SSH: the server has no open inbound ports and is
# reachable only through Tailscale (Funnel for the public blog, Tailscale SSH for admins).
#
# Usage:
#   ./deploy.sh           create a Hetzner Cloud VPS (needs HCLOUD_TOKEN in .env)
#   ./deploy.sh --local   create a local Multipass VM from the same cloud-init (no Hetzner needed)
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source ./lib.sh
init "$@"
require_cmd curl envsubst jq nc openssl tailscale dig
require_var TS_AUTHKEY

GHOST_ADMIN_EMAIL="${GHOST_ADMIN_EMAIL:-admin@example.com}"
GHOST_BLOG_TITLE="${GHOST_BLOG_TITLE:-Ghost on Hetzner}"
CREDENTIALS_FILE=".ghost-admin-credentials"

# --- Preflight ---------------------------------------------------------------------------------
log "Preflight checks ($MODE mode, server '$SERVER_NAME')"
tailscale status >/dev/null 2>&1 || die "this machine is not connected to Tailscale"
if in_tailnet; then
  die "a device named '$SERVER_NAME' already exists in the tailnet — remove it in the Tailscale admin console (or run ./destroy.sh), otherwise the new server would get a different hostname"
fi
if [[ "$MODE" == hetzner ]]; then
  hcloud server describe "$SERVER_NAME" >/dev/null 2>&1 \
    && die "Hetzner server '$SERVER_NAME' already exists — run ./destroy.sh first"
  hcloud server-type describe "$SERVER_TYPE" >/dev/null 2>&1 \
    || die "unknown SERVER_TYPE '$SERVER_TYPE' — see: hcloud server-type list"
else
  multipass info "$SERVER_NAME" >/dev/null 2>&1 \
    && die "Multipass VM '$SERVER_NAME' already exists — run ./destroy.sh --local first"
fi

# --- Render cloud-init (contains the auth key → temp file, removed on exit) ------------------
USER_DATA="$(mktemp)"
trap 'rm -f "$USER_DATA"' EXIT
export TS_AUTHKEY SERVER_NAME GHOST_URL
# shellcheck disable=SC2016  # the single quotes are intentional: envsubst gets the variable list
envsubst '${TS_AUTHKEY} ${SERVER_NAME} ${GHOST_URL}' < cloud-init.yaml > "$USER_DATA"

# --- Create the server -------------------------------------------------------------------------
if [[ "$MODE" == hetzner ]]; then
  if ! hcloud firewall describe "$FIREWALL_NAME" >/dev/null 2>&1; then
    log "Creating Hetzner Cloud Firewall '$FIREWALL_NAME' with no inbound rules (= all inbound blocked)"
    hcloud firewall create --name "$FIREWALL_NAME" --label app=ghost >/dev/null
  fi
  log "Creating server ($SERVER_TYPE, ubuntu-24.04, $LOCATION)"
  hcloud server create \
    --name "$SERVER_NAME" --type "$SERVER_TYPE" --image ubuntu-24.04 --location "$LOCATION" \
    --firewall "$FIREWALL_NAME" --user-data-from-file "$USER_DATA" --label app=ghost >/dev/null
else
  log "Launching Multipass VM (Ubuntu 24.04, same cloud-init; the first run downloads the image)"
  # `multipass launch` waits for cloud-init over SSH, but cloud-init masks sshd, so the command
  # may never report success. Run it in the background and track progress through Tailscale.
  LAUNCH_LOG="$(mktemp)"
  multipass launch 24.04 --name "$SERVER_NAME" --cpus 2 --memory 2G --disk 10G \
    --cloud-init "$USER_DATA" --timeout 1800 >"$LAUNCH_LOG" 2>&1 &
  launch_pid=$!
  trap 'rm -f "$USER_DATA" "$LAUNCH_LOG"; kill "$launch_pid" 2>/dev/null || true' EXIT
  for _ in $(seq 360); do
    multipass info "$SERVER_NAME" >/dev/null 2>&1 && break
    kill -0 "$launch_pid" 2>/dev/null || break
    sleep 5
  done
  multipass info "$SERVER_NAME" >/dev/null 2>&1 \
    || die "multipass could not create the VM: $(cat "$LAUNCH_LOG")"
fi

# --- Wait until the server has joined the tailnet and Ghost answers ----------------------------
log "Waiting for the server to join the tailnet (usually 2–4 min)"
for _ in $(seq 120); do in_tailnet && break; sleep 5; done
in_tailnet || die "server did not join the tailnet in 10 min — check the auth key and ACL (README → Troubleshooting)"
log "Server is in the tailnet; its public IP is $(public_ip)"

log "Waiting for Ghost at $GHOST_URL (image pulls + DB init, usually 2–5 min)"
for _ in $(seq 120); do
  curl -fsS -o /dev/null --max-time 10 "$GHOST_URL/ghost/api/admin/site/" 2>/dev/null && break
  sleep 5
done
curl -fsS -o /dev/null --max-time 10 "$GHOST_URL/ghost/api/admin/site/" \
  || die "Ghost is not responding — inspect: tailscale ssh root@$SERVER_NAME cat /var/log/ghost-bootstrap.log"

# --- Create the Ghost owner account, so nobody else can claim /ghost ---------------------------
setup_done="$(curl -fsS "$GHOST_URL/ghost/api/admin/authentication/setup/" | jq -r '.setup[0].status')"
if [[ "$setup_done" == false ]]; then
  log "Creating the Ghost owner account ($GHOST_ADMIN_EMAIL)"
  password="${GHOST_ADMIN_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)}"
  jq -n --arg n "Admin" --arg e "$GHOST_ADMIN_EMAIL" --arg p "$password" --arg t "$GHOST_BLOG_TITLE" \
      '{setup: [{name: $n, email: $e, password: $p, blogTitle: $t}]}' \
    | curl -fsS -o /dev/null -X POST "$GHOST_URL/ghost/api/admin/authentication/setup/" \
        -H 'Content-Type: application/json' -H "Origin: $GHOST_URL" --data @-
  (umask 077; printf 'url=%s/ghost\nemail=%s\npassword=%s\n' "$GHOST_URL" "$GHOST_ADMIN_EMAIL" "$password" > "$CREDENTIALS_FILE")
else
  log "Ghost owner already exists, skipping setup"
fi

# --- Verify ------------------------------------------------------------------------------------
./verify.sh "$@"

cat <<EOF

Done.
  Blog:         $GHOST_URL
  Admin panel:  $GHOST_URL/ghost   (credentials in $(pwd)/$CREDENTIALS_FILE)
  Admin shell:  tailscale ssh root@$SERVER_NAME
  Tear down:    ./destroy.sh$([[ "$MODE" == local ]] && echo " --local")
EOF
