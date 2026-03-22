# GrantPath

GrantPath is a self-hosted **Access Path Intelligence Platform** for teams that need to answer:

- who has access
- why that access exists
- what changes if a grant, group or ACL path is removed

It is built as an explainable control plane, not as a static ACL auditor.

## Why It Matters

GrantPath models real access relationships across identities, groups, ACLs, inheritance and effective permissions, then turns them into operational answers that admins and security teams can actually use.

Core product goals:

- deterministic entitlement reasoning
- fast materialized access queries
- explainable access paths
- operator-grade reporting and access reviews
- self-hosted deployment without paid dependencies

## Current Maturity

GrantPath is currently best described as:

- `advanced MVP / private beta`
- strong for `filesystem + explainability + reporting + review`
- partially implemented for several enterprise connector surfaces
- architected for a larger enterprise stack, with some components already integrated and others still optional

What is already solid:

- local admin bootstrap with MFA
- `LDAP` and `OIDC` integration paths
- live filesystem collection
- raw snapshot retention
- normalization pipeline
- graph-backed explainability
- materialized access index
- `who-has-access`, `why`, `what-if`, `risk`, `changes`
- access review campaigns and remediation plans
- scheduled reports
- worker split `all / api / worker`
- RBAC inside the application
- Docker, Windows package, Linux installer

What is still partial:

- full cloud/runtime validation for `Graph`, `Azure`, `Okta`, `AWS`, `Google`, `CyberArk`
- deeper multi-tenant isolation
- broader enterprise governance and analytics

## Architecture

GrantPath follows a layered design:

1. `Connector / Collector Layer`
2. `Raw Snapshot Store`
3. `Normalization Pipeline`
4. `Graph Engine`
5. `Materialized Access Index`
6. `Query / API Gateway`
7. `Web UI`

Main query surfaces:

- `SearchSvc`
- `EntitlementSvc`
- `ExplainSvc`
- `RiskSvc`
- `WhatIfSvc`
- `GraphSvc`
- `ChangesSvc`

The UI is task-oriented rather than scanner-oriented:

- `Home`
- `Investigate`
- `Govern`
- `Sources`
- `Operations`

## Tech Stack

Current stack in the repository:

- backend: `FastAPI`
- frontend: `React + TypeScript`
- primary production store: `PostgreSQL`
- optional runtime integrations: `Neo4j`, `OpenSearch`, `ClickHouse`, `Valkey`
- observability base: `OpenTelemetry`

Important compatibility note:

- internal configuration prefixes still use `EIP_*` for backward compatibility

## Quick Start

### Backend

```powershell
cd C:\test\EIP
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir .\backend
```

### Frontend

```powershell
cd C:\test\EIP\frontend
npm run dev
```

UI:

- `http://127.0.0.1:5173`

### Local Quality Checks

```powershell
cd C:\test\EIP
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m bandit -r backend/app -ll
.\.venv\Scripts\python.exe -m pip_audit -r backend/requirements.txt
cd .\frontend
npm run lint
npm run build
npm audit --omit=dev
```

## Deployment Paths

Supported packaging paths:

- Docker appliance / production compose
- Windows packaged executable
- Linux install script

Key files:

- [backend/Dockerfile](C:/test/EIP/backend/Dockerfile)
- [backend/requirements-dev.txt](C:/test/EIP/backend/requirements-dev.txt)
- [frontend/Dockerfile](C:/test/EIP/frontend/Dockerfile)
- [Dockerfile.appliance](C:/test/EIP/Dockerfile.appliance)
- [docker-compose.production.yml](C:/test/EIP/docker-compose.production.yml)
- [docker-compose.enterprise.yml](C:/test/EIP/docker-compose.enterprise.yml)
- [scripts/build-windows.ps1](C:/test/EIP/scripts/build-windows.ps1)
- [scripts/install-linux.sh](C:/test/EIP/scripts/install-linux.sh)

## Documentation

- [Support Matrix](C:/test/EIP/docs/support-matrix.md)
- [Roadmap](C:/test/EIP/ROADMAP.md)
- [Official Integration Notes](C:/test/EIP/docs/official-integration-notes.md)
- [Enterprise Readiness Review](C:/test/EIP/docs/enterprise-readiness-review.md)

## Repository Layout

- [backend](C:/test/EIP/backend)
- [frontend](C:/test/EIP/frontend)
- [docs](C:/test/EIP/docs)
- [deploy](C:/test/EIP/deploy)
- [scripts](C:/test/EIP/scripts)

## Supported vs Partial

At a high level:

- `supported`: local filesystem investigation, explainability, reporting, review, scheduling, self-hosted deployment
- `partial`: enterprise connector runtime coverage, analytics depth, tenant isolation
- `blueprint`: some cloud connectors modeled from official documentation but not fully live in this runtime

See the full matrix in [docs/support-matrix.md](C:/test/EIP/docs/support-matrix.md).

## Publishing Notes

GrantPath is publishable as an open-source project today if positioned honestly:

- not as a finished enterprise suite
- but as a serious, self-hosted access intelligence platform with a strong architecture and working end-to-end flows

Recommended positioning:

- `Access Path Intelligence Platform`
- `advanced MVP / private beta`
- `self-hosted, explainable, operator-first`

Public launch assets:

- [GitHub Launch Kit](C:/test/EIP/docs/github-launch-kit.md)
- [Release v0.1.0 Notes](C:/test/EIP/RELEASE_v0.1.0.md)
- [License Decision](C:/test/EIP/docs/license-decision.md)

## Security

Please read [SECURITY.md](C:/test/EIP/SECURITY.md) before reporting vulnerabilities.

## Contributing

Contribution guidelines are in [CONTRIBUTING.md](C:/test/EIP/CONTRIBUTING.md).

## License

This repository is prepared for publication under the [Apache-2.0 License](C:/test/EIP/LICENSE).
