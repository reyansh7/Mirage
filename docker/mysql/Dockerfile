FROM mysql:8.0

USER root

RUN microdnf install -y python3 python3-pip \
    && pip3 install --no-cache-dir requests \
    && microdnf clean all \
    && mkdir -p /var/log/mysql \
    && chown mysql:mysql /var/log/mysql

COPY my.cnf /etc/mysql/conf.d/honeypot.cnf
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY log_shipper.py /opt/log_shipper.py
COPY entrypoint.sh /opt/entrypoint.sh

RUN chmod +x /opt/entrypoint.sh

ENTRYPOINT ["/opt/entrypoint.sh"]
