# Phase 2 — Fake World (Static Honeypot)

## Company

**Acme Technologies** — Cloud Software, 420 employees  
Departments: Engineering, DevOps, Finance, HR, Security

## Machine

- Hostname: `build-server-01`
- OS (presented): Ubuntu 24.04 LTS
- Fake IP: `10.0.5.18`
- Default SSH user: `developer` / `Welcome1!`

Other SSH users: `admin`, `jenkins`, `backup`, `finance`, `intern`

## Command Engine

```
Input → Parser → Permission Checker → Handler → Formatter
```

Code: `backend/app/world/`

SSH never runs real OS commands. `ForceCommand` launches `fake_shell.py`, which calls:

- `POST /world/session`
- `POST /command`

## World data

`backend/app/world/data/` — JSON + documents + logs

## Try it

```bash
ssh -p 2222 developer@127.0.0.1
# password: Welcome1!

whoami
hostname
ls /
ls /home
cd /home/developer
cat notes.md
systemctl status apache2
ip addr
mysql -e "SELECT * FROM employees"
```

Portal: http://127.0.0.1:8080/ (admin / admin123)

MySQL host: `127.0.0.1:3307` — `admin` / `admin123` — DB `corporate`
