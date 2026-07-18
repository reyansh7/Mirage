#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
API="http://${HOST}:8001"

echo "== health =="
curl -sS "${API}/health"
echo

echo "== dashboard =="
curl -sS -o /dev/null -w "GET / -> %{http_code}\n" "${API}/"
curl -sS -o /dev/null -w "GET /sessions -> %{http_code}\n" "${API}/sessions"
curl -sS -o /dev/null -w "GET /events -> %{http_code}\n" "${API}/events"

echo "== website =="
curl -sS -o /dev/null -w "GET / -> %{http_code}\n" "http://${HOST}:8080/"
curl -sS -o /dev/null -w "GET /login -> %{http_code}\n" "http://${HOST}:8080/login"
curl -sS -o /dev/null -w "GET /admin -> %{http_code}\n" "http://${HOST}:8080/admin"
curl -sS -o /dev/null -w "GET /dashboard -> %{http_code}\n" "http://${HOST}:8080/dashboard"

echo "== typed event =="
curl -sS -X POST "${API}/events" \
  -H "Content-Type: application/json" \
  -d "{\"service\":\"test\",\"event_type\":\"CONNECT\",\"ip\":\"${HOST}\",\"payload\":{\"message\":\"smoke\"}}"
echo

echo "== world session + command =="
SID=$(curl -sS -X POST "${API}/world/session" \
  -H "Content-Type: application/json" \
  -d '{"user":"developer","source_ip":"127.0.0.1"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["session_id"])')
curl -sS -X POST "${API}/command" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SID}\",\"command\":\"pwd\"}"
echo
curl -sS -o /dev/null -w "timeline -> %{http_code}\n" "${API}/sessions/${SID}/timeline"
curl -sS -o /dev/null -w "replay -> %{http_code}\n" "${API}/sessions/${SID}/replay"
curl -sS -X POST "${API}/sessions/${SID}/end" -H "Content-Type: application/json" -d '{"reason":"smoke"}' >/dev/null

echo "== mysql =="
docker exec honeypot-mysql mysql -u admin -padmin123 -e "SELECT 1 AS ok;" corporate

echo "== ssh =="
docker exec honeypot-ssh bash -c "sshd -t && echo SSHD_CONFIG_OK"

echo
echo "Smoke test finished."
