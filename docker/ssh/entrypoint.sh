#!/bin/bash
set -euo pipefail

# Acme Technologies — build-server-01 decoy users
declare -A USER_PASS=(
  [developer]="Welcome1!"
  [admin]="admin123"
  [jenkins]="jenkins"
  [backup]="backup"
  [finance]="finance2026"
  [intern]="intern"
)

echo "root:honeypot" | chpasswd

for user in "${!USER_PASS[@]}"; do
  if ! id "$user" &>/dev/null; then
    useradd -m -s /bin/bash "$user"
  fi
  echo "${user}:${USER_PASS[$user]}" | chpasswd
done

# Keep legacy admin password also available via HONEYPOT_* env
if [[ -n "${HONEYPOT_USER:-}" && -n "${HONEYPOT_PASSWORD:-}" ]]; then
  if ! id "${HONEYPOT_USER}" &>/dev/null; then
    useradd -m -s /bin/bash "${HONEYPOT_USER}"
  fi
  echo "${HONEYPOT_USER}:${HONEYPOT_PASSWORD}" | chpasswd
fi

mkdir -p /var/log
touch /var/log/sshd.log

python3 /opt/log_shipper.py &

# Real sshd for auth only; ForceCommand runs fake_shell (no real OS commands)
/usr/sbin/sshd -D -e 2>&1 | tee -a /var/log/sshd.log
