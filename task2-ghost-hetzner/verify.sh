#!/usr/bin/env bash
# Checks a deployed server against the requirements. Called by deploy.sh; can be re-run any time.
#
# Usage:
#   ./verify.sh           verify the Hetzner server
#   ./verify.sh --local   verify the local Multipass VM
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source ./lib.sh
init "$@"
require_cmd curl dig jq nc tailscale

failures=0
check() { if "$@"; then ok "$DESC"; else fail "$DESC"; failures=$((failures + 1)); fi; }

log "Verifying $GHOST_URL ($MODE mode)"

# 1. The blog is public: resolve the name via public DNS so the request goes over the internet
#    to Tailscale Funnel, not through this machine's tailnet connection.
funnel_ip="$(dig +short @1.1.1.1 "$GHOST_HOST" A | tail -n1)"
# The public Funnel endpoint can take a few minutes to start answering after `tailscale funnel`.
public_blog() {
  [[ -n "$funnel_ip" ]] || return 1
  local _
  for _ in $(seq 60); do
    curl -fsS -o /dev/null --max-time 15 --resolve "$GHOST_HOST:443:$funnel_ip" "$GHOST_URL/" 2>/dev/null && return 0
    sleep 5
  done
  return 1
}
DESC="blog is reachable from the internet via Tailscale Funnel ($GHOST_HOST → ${funnel_ip:-no public DNS record})"
check public_blog

# 2. Nothing answers on the server's own public IP.
ip="$(public_ip)"
[[ -n "$ip" ]] || die "server '$SERVER_NAME' not found"
port_closed() { ! tcp_open "$ip" "$1"; }
for port in 22 80 443 2368; do
  DESC="port $port on public IP $ip is closed"
  check port_closed "$port"
done

# 3. Inside the server (reached only through Tailscale SSH — which itself proves admin access works).
# The remote commands below are single-quoted on purpose: they are expanded on the server.
remote() { tailscale ssh "root@$SERVER_NAME" "$@" 2>/dev/null; }
DESC="admin shell via Tailscale SSH works"
check remote true

DESC="sshd is masked (ssh.socket and ssh.service)"
# shellcheck disable=SC2016
check remote '[ "$(systemctl is-enabled ssh.socket ssh.service | sort -u)" = masked ]'

DESC="ufw is active and denies incoming traffic"
check remote 'ufw status verbose | grep -q "Status: active" && ufw status verbose | grep -q "deny (incoming)"'

# Every TCP listener must be on loopback or on the tailnet address.
DESC="no TCP service listens on a public interface"
# shellcheck disable=SC2016
check remote '! ss -tlnH | awk "{print \$4}" | grep -vE "^(127\.|\[::1\]|100\.|\[fd7a:)"'

echo
if (( failures > 0 )); then
  fail "$failures check(s) failed"
  exit 1
fi
ok "all checks passed"
