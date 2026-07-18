FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    python3 \
    python3-requests \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/sshd /var/log

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
COPY log_shipper.py /opt/log_shipper.py
COPY fake_shell.py /opt/fake_shell.py

RUN chmod +x /entrypoint.sh /opt/fake_shell.py \
    && ssh-keygen -A \
    && rm -f /etc/ssh/sshd_config.d/* \
    && mkdir -p /run/sshd

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
