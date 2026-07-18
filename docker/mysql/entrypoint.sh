#!/bin/bash
set -euo pipefail

mkdir -p /var/log/mysql
touch /var/log/mysql/general.log
chown -R mysql:mysql /var/log/mysql

# Start log shipper once MySQL is up (background)
(
  for i in $(seq 1 90); do
    if mysqladmin ping -h 127.0.0.1 -uroot -p"${MYSQL_ROOT_PASSWORD}" --silent 2>/dev/null; then
      break
    fi
    sleep 2
  done
  python3 /opt/log_shipper.py
) &

exec docker-entrypoint.sh mysqld
