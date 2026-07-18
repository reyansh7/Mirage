# Working from WSL

Active project path:

```bash
cd ~/projects/adaptive-honeypot
```

## Open in Cursor

File → Open Folder → paste:

```text
\\wsl$\Ubuntu\home\reyansh\projects\adaptive-honeypot
```

Or: open a WSL terminal and run `cursor .` from the project folder.

## Enable Docker in Ubuntu WSL (required once)

1. Open **Docker Desktop**
2. **Settings → Resources → WSL Integration**
3. Enable **Ubuntu**
4. Apply & Restart

Then in WSL:

```bash
cd ~/projects/adaptive-honeypot/docker
docker compose up --build -d
```

Until integration is on, you can still run Compose from Windows PowerShell against the WSL path *after* integration is enabled. Without it, Docker cannot mount `\\wsl$\Ubuntu\...`.

## Old OneDrive copy

`C:\Users\reyan\OneDrive\Desktop\Ai-Honeypot` is obsolete. Do not edit both.
