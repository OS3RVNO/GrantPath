# Install Guide

GrantPath can be installed in three practical ways.

## 1. Docker Appliance

This is the easiest path for most users.

1. Copy `.env.production.example` to `.env`
2. Adjust secrets and hostnames
3. Start the stack

```bash
cp .env.production.example .env
docker compose -f docker-compose.production.yml up -d
```

Then open the frontend URL exposed by your deployment.

## 2. Windows Release Package

Recommended for users who want a local desktop-style package.

1. Download the Windows asset from GitHub Releases
2. Extract the archive
3. Run `GrantPath.exe`

The packaged app serves the UI and backend locally and opens the browser automatically by default.

## 3. Linux System Install

Recommended for self-hosted Linux environments.

```bash
sudo ./scripts/install-linux.sh
```

Production example:

```bash
sudo ./scripts/install-linux.sh --production-host access.example.com --scan-root /srv/data
```

## 4. Install From Source

For contributors or advanced operators.

### Windows

```powershell
.\scripts\install-from-source.ps1
```

### Linux / macOS

```bash
./scripts/install-from-source.sh
```

## Recommended Public Distribution Strategy

For GitHub publication, the best user experience is:

- publish Docker instructions for fast self-hosting
- publish a Windows release artifact for non-technical users
- keep the Linux installer for system deployments
- keep source install scripts for contributors and advanced operators

## Notes

- internal environment variables still use the `EIP_*` prefix for compatibility
- cloud connectors remain conservatively labeled when they are not live-validated
