# GrantPath

[![CI](https://github.com/OS3RVNO/GrantPath/actions/workflows/ci.yml/badge.svg)](https://github.com/OS3RVNO/GrantPath/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/OS3RVNO/GrantPath?display_name=tag)](https://github.com/OS3RVNO/GrantPath/releases)
[![License](https://img.shields.io/github/license/OS3RVNO/GrantPath)](./LICENSE)
![Status](https://img.shields.io/badge/status-early%20preview-EA580C)

> Who has access. Why it exists. What changes if you remove it.

GrantPath is a graph-powered, self-hosted **Access Path Intelligence Platform** for IAM, Active Directory and file server permissions. It shows who has access, explains why that access exists through groups, ACLs and inheritance, and helps teams simulate changes before they break production.

## Why GrantPath

GrantPath is built for a problem teams hit constantly:

- access is inherited through layers of groups, ACLs and exceptions
- static permission reports do not explain why an access path exists
- cleanup work is risky when nobody knows what will break

GrantPath turns that mess into something operational:

- `who has access`: find effective access across principals, groups, resources and inheritance
- `why it exists`: inspect explainable paths instead of guessing from raw ACLs
- `what changes if you remove it`: run safe what-if simulations before touching production
- `review and report`: generate access reviews, remediation plans and scheduled reports
- `self-hosted`: run it in Docker, Windows or Linux without paid platform dependencies

## What Feels Strong Today

GrantPath is an explainable, graph-powered control plane for access analysis, entitlement visibility and permission cleanup.

- it shows who can reach a resource or permission boundary
- it explains why that access exists across identities, nested groups, ACLs and inheritance
- it helps teams understand what changes if a grant, path or group is removed
- it turns review and cleanup work into something operators can act on quickly

It is built for self-hosted environments where access visibility, operational reporting and explainability matter more than static audit exports.

GrantPath is built for teams that need to answer:

- who has access
- why that access exists
- what changes if a grant, group or ACL path is removed

It is built as an explainable control plane, not as a static ACL auditor.

## Project Status

GrantPath is still an early public preview, not a finished enterprise suite. The core flows are already real and useful, but broader enterprise depth is still being built out.

Where it already feels strong:

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

What is still evolving:

- full cloud/runtime validation for `Graph`, `Azure`, `Okta`, `AWS`, `Google`, `CyberArk`
- deeper multi-tenant isolation
- broader enterprise governance and analytics

If you discover GrantPath through GitHub search, the right expectation is:

- already useful for `filesystem + explainability + access review + reporting`
- still maturing for deeper enterprise breadth and broader connector coverage

## Quick Start

Start here:

- [INSTALL.md](./INSTALL.md)

Recommended install paths:

1. Docker appliance
2. Windows release package
3. Linux system install

Core documentation:

- [Install Guide](./INSTALL.md)
- [Support Matrix](./docs/support-matrix.md)
- [Official Integration Notes](./docs/official-integration-notes.md)
- [Enterprise Readiness Review](./docs/enterprise-readiness-review.md)

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

## Quick Start From Source

### Backend

```powershell
cd <repo-root>
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir .\backend
```

### Frontend

```powershell
cd <repo-root>\frontend
npm run dev
```

UI:

- `http://127.0.0.1:5173`

### Local Quality Checks

```powershell
cd <repo-root>
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

- [backend/Dockerfile](./backend/Dockerfile)
- [backend/requirements-dev.txt](./backend/requirements-dev.txt)
- [frontend/Dockerfile](./frontend/Dockerfile)
- [Dockerfile.appliance](./Dockerfile.appliance)
- [docker-compose.production.yml](./docker-compose.production.yml)
- [docker-compose.enterprise.yml](./docker-compose.enterprise.yml)
- [scripts/build-windows.ps1](./scripts/build-windows.ps1)
- [scripts/install-linux.sh](./scripts/install-linux.sh)
- [scripts/install-from-source.ps1](./scripts/install-from-source.ps1)
- [scripts/install-from-source.sh](./scripts/install-from-source.sh)

## Repository Layout

- [backend](./backend)
- [frontend](./frontend)
- [docs](./docs)
- [deploy](./deploy)
- [scripts](./scripts)

## Supported vs Partial

At a high level:

- `supported`: local filesystem investigation, explainability, reporting, review, scheduling, self-hosted deployment
- `partial`: enterprise connector runtime coverage, analytics depth, tenant isolation
- `blueprint`: some cloud connectors modeled from official documentation but not fully live in this runtime

See the full matrix in [docs/support-matrix.md](./docs/support-matrix.md).

## Security

Please read [SECURITY.md](./SECURITY.md) before reporting vulnerabilities.

## Contributing

Contribution guidelines are in [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

This repository is prepared for publication under the [Apache-2.0 License](./LICENSE).
