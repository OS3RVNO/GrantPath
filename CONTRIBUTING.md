# Contributing

Thanks for helping improve GrantPath.

## Before You Start

- read [README.md](C:/test/EIP/README.md)
- check [docs/support-matrix.md](C:/test/EIP/docs/support-matrix.md)
- keep the product positioning honest: explainable access intelligence, not fake enterprise coverage

## Local Setup

### Backend

```powershell
cd C:\test\EIP
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt
```

### Frontend

```powershell
cd C:\test\EIP\frontend
npm ci
```

## Quality Gates

Run these before opening a pull request:

```powershell
cd C:\test\EIP
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m bandit -r backend/app -ll
.\.venv\Scripts\python.exe -m pip_audit -r backend/requirements.txt
cd .\frontend
npm run lint
npm run build
npm audit --omit=dev
```

## Contribution Rules

- prefer small, reviewable pull requests
- keep behavior deterministic in access calculation paths
- avoid overstating connector maturity
- document new env vars and operational side effects
- add tests for bug fixes and new behavior
- preserve backward compatibility for existing `EIP_*` env vars unless a change is explicitly intentional

## Pull Request Checklist

- tests added or updated
- docs updated where behavior changed
- security implications considered
- user-facing regressions checked
- support matrix updated if connector/runtime scope changed
