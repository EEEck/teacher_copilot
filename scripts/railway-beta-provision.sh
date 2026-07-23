#!/usr/bin/env bash
# Provision a Railway beta tester from a short name/prefix (Git Bash / macOS / Linux).
#
# Usage:
#   ./scripts/railway-beta-provision.sh maria
#   ./scripts/railway-beta-provision.sh lb "LB (Chemie 9b)"
#   LOGIN_URL=https://klassenpilot-beta.up.railway.app/beta/login ./scripts/railway-beta-provision.sh matt "user testing"
#
# Requires: railway CLI logged in + project linked, SSH key registered
#   (railway ssh keys add -k ~/.ssh/railway_ed25519.pub -n railway-klassenpilot-beta)
set -euo pipefail

PREFIX="${1:-}"
DISPLAY_LABEL="${2:-}"
SUFFIX_LEN="${SUFFIX_LEN:-22}"
SERVICE="${SERVICE:-backend}"
LOGIN_URL="${LOGIN_URL:-https://klassenpilot-beta.up.railway.app/beta/login}"
IDENTITY_FILE="${IDENTITY_FILE:-$HOME/.ssh/railway_ed25519}"

if [[ -z "$PREFIX" ]]; then
  echo "Usage: $0 <prefix> [display-label]" >&2
  exit 1
fi

if ! [[ "$PREFIX" =~ ^[A-Za-z][A-Za-z0-9_-]{0,31}$ ]]; then
  echo "Prefix must start with a letter and use only A-Z a-z 0-9 _ -" >&2
  exit 1
fi

if ! command -v railway >/dev/null 2>&1; then
  echo "railway CLI not found. In Git Bash try: npm i -g @railway/cli" >&2
  echo "Then open a new Git Bash window so PATH picks up ~/AppData/Roaming/npm" >&2
  exit 1
fi

slug=$(echo "$PREFIX" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//')
if [[ -z "$slug" ]]; then
  echo "Prefix produced an empty slug" >&2
  exit 1
fi

alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
suffix=""
for ((i = 0; i < SUFFIX_LEN; i++)); do
  idx=$((RANDOM % ${#alphabet}))
  suffix+="${alphabet:idx:1}"
done

invite_code="${PREFIX}_${suffix}"
tester_id="t_${slug}"
workspace_id="w_${slug}"
if [[ -z "$DISPLAY_LABEL" ]]; then
  DISPLAY_LABEL="${PREFIX} beta"
fi

# Escape for remote single-quoted sh string
sh_escape() {
  printf "%s" "$1" | sed "s/'/'\\\\''/g"
}

# Avoid Git Bash rewriting /data/... to a Windows path before SSH.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

# chmod after provision: SSH often runs as root; the API runs as uid 1000.
# Use //data so MSYS never converts the path even if env vars are ignored.
remote=$(
  cat <<EOF
python -m app.services.beta_cli provision \
  --tester-id '$(sh_escape "$tester_id")' \
  --workspace-id '$(sh_escape "$workspace_id")' \
  --invite-code '$(sh_escape "$invite_code")' \
  --display-label '$(sh_escape "$DISPLAY_LABEL")'
chmod -R a+rwX /data/beta_data 2>/dev/null || true
chown -R 1000:1000 /data/beta_data 2>/dev/null || true
EOF
)

ssh_args=(ssh -s "$SERVICE")
if [[ -f "$IDENTITY_FILE" ]]; then
  ssh_args+=(-i "$IDENTITY_FILE")
fi
ssh_args+=(-- sh -lc "$remote")

echo "Provisioning ${tester_id} -> ${workspace_id} on Railway service '${SERVICE}'..."
railway "${ssh_args[@]}"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
tracker="${repo_root}/deploy/railway/invites.local.md"
if [[ ! -f "$tracker" ]]; then
  cat >"$tracker" <<'HDR'
# Local beta invite tracker (gitignored — do not commit)

| Account / label | Invite code | tester_id | workspace_id | Created |
|-----------------|-------------|-----------|--------------|---------|
HDR
fi
created="$(date -u +"%Y-%m-%d %H:%M")Z"
echo "| ${DISPLAY_LABEL} | \`${invite_code}\` | \`${tester_id}\` | \`${workspace_id}\` | ${created} |" >>"$tracker"

cat <<EOF

=== Invite (share out of band) ===
${invite_code}

=== Message template ===
Hi — you're invited to the KlassenPilot beta (private teacher copilot).

1. Open: ${LOGIN_URL}
2. Paste this invite code:
   ${invite_code}
3. Choose a display name, then explore with the sample class Chemie 9b.

Notes:
- Your workspace is private to you (your invite only).
- Early beta: expect rough edges; feedback is welcome via the app menu.
- Please don't reshare the invite code.

Thanks!

Tracked in: ${tracker}
Ids: tester=${tester_id} workspace=${workspace_id}
EOF
