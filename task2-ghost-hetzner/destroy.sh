#!/usr/bin/env bash
# Deletes everything deploy.sh created: the server, its firewall and its tailnet device.
#
# Usage:
#   ./destroy.sh [--yes]           delete the Hetzner server and firewall
#   ./destroy.sh --local [--yes]   delete the local Multipass VM
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source ./lib.sh
init "$@"

if [[ "$ASSUME_YES" != true ]]; then
  read -r -p "Delete '$SERVER_NAME' ($MODE) and all its data? Type the server name to confirm: " answer
  [[ "$answer" == "$SERVER_NAME" ]] || die "aborted"
fi

# Log the server out of Tailscale first, so it leaves the tailnet. Best effort: it fails harmlessly
# if the server is already gone. The logout cuts our own SSH session, so it runs as a transient
# systemd unit (a plain background job would be killed together with the session).
if command -v tailscale >/dev/null && in_tailnet; then
  log "Removing '$SERVER_NAME' from the tailnet"
  tailscale ssh "root@$SERVER_NAME" 'systemd-run --on-active=2 --unit=ts-logout tailscale logout' >/dev/null 2>&1 || true
  for _ in $(seq 12); do in_tailnet || break; sleep 5; done
fi

if [[ "$MODE" == hetzner ]]; then
  if hcloud server describe "$SERVER_NAME" >/dev/null 2>&1; then
    log "Deleting Hetzner server '$SERVER_NAME'"
    hcloud server delete "$SERVER_NAME" >/dev/null
  fi
  if hcloud firewall describe "$FIREWALL_NAME" >/dev/null 2>&1; then
    log "Deleting firewall '$FIREWALL_NAME'"
    hcloud firewall delete "$FIREWALL_NAME" >/dev/null
  fi
else
  if multipass info "$SERVER_NAME" >/dev/null 2>&1; then
    log "Deleting Multipass VM '$SERVER_NAME'"
    multipass delete --purge "$SERVER_NAME"
  fi
fi
rm -f .ghost-admin-credentials

if in_tailnet; then
  log "'$SERVER_NAME' is still listed in the tailnet — remove it at https://login.tailscale.com/admin/machines"
fi
log "Destroyed"
