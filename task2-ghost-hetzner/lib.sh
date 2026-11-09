# Shared helpers for deploy.sh, verify.sh and destroy.sh. Not meant to be executed directly.
# shellcheck shell=bash
# shellcheck disable=SC2034  # variables set here are used by the scripts that source this file

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mPASS\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mERROR\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "'$c' is not installed (see README → Prerequisites)"
  done
}

require_var() {
  local v
  for v in "$@"; do
    [[ -n "${!v:-}" ]] || die "$v is not set in .env (see .env.example)"
  done
}

# Parses --local / --yes, loads .env and derives the values every script needs.
init() {
  MODE=hetzner
  ASSUME_YES=false
  local arg
  for arg in "$@"; do
    case "$arg" in
      --local) MODE=local ;;
      --yes)   ASSUME_YES=true ;;
      -h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
      *) die "unknown argument: $arg" ;;
    esac
  done

  [[ -f .env ]] || die ".env not found — run: cp .env.example .env and fill it in"
  set -a
  # shellcheck disable=SC1091
  source ./.env
  set +a

  SERVER_NAME="${SERVER_NAME:-ghost-blog}"
  SERVER_TYPE="${SERVER_TYPE:-cax11}"
  LOCATION="${LOCATION:-fsn1}"
  FIREWALL_NAME="${SERVER_NAME}-deny-inbound"
  require_var TS_TAILNET_DNS
  GHOST_HOST="${SERVER_NAME}.${TS_TAILNET_DNS}"
  GHOST_URL="https://${GHOST_HOST}"

  if [[ "$MODE" == hetzner ]]; then
    require_cmd hcloud
    require_var HCLOUD_TOKEN
    export HCLOUD_TOKEN
  else
    require_cmd multipass
  fi
}

# Prints the public (non-tailnet) IPv4 of the server, empty if it does not exist.
public_ip() {
  if [[ "$MODE" == hetzner ]]; then
    hcloud server ip "$SERVER_NAME" 2>/dev/null || true
  else
    multipass info "$SERVER_NAME" --format json 2>/dev/null \
      | jq -r --arg n "$SERVER_NAME" '.info[$n].ipv4[0] // empty' || true
  fi
}

# True if a device with this hostname is currently in the tailnet.
in_tailnet() {
  tailscale status --json \
    | jq -e --arg h "$SERVER_NAME" \
        '[.Peer[]? | select((.DNSName | split(".")[0]) == $h)] | length > 0' >/dev/null
}

# True if a TCP connection to host:port succeeds within 5 s.
tcp_open() {
  if nc -h 2>&1 | grep -qE -- '^[[:space:]]+-G '; then
    nc -z -G 5 -w 5 "$1" "$2" >/dev/null 2>&1   # macOS nc: -G is the connect timeout
  else
    nc -z -w 5 "$1" "$2" >/dev/null 2>&1
  fi
}
