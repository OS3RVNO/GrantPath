# Support Matrix

This matrix is intentionally strict. It separates what is production-credible today from what is still partial or blueprint-only.

| Area | Status | Notes |
|---|---|---|
| Local admin bootstrap + MFA | `supported` | Local setup, password auth and TOTP are implemented. |
| `LDAP` / `OIDC` auth | `supported` | Federated auth paths are available. |
| Local filesystem collection | `supported` | Windows and Linux filesystem collection are implemented. |
| SSH Linux targets | `supported` | SSH-backed Linux collection is available. |
| Explainability | `supported` | Deterministic `why` answers and ranked paths are implemented. |
| Effective access / exposure | `supported` | Materialized access queries are available and paginated. |
| What-if simulation | `supported` | What-if works with scoped delta-style recomputation. |
| Reports `HTML/PDF/XLSX` | `supported` | Export pipeline is implemented. |
| Review campaigns | `supported` | Review, decisions and remediation plans are implemented. |
| Scheduled reports | `supported` | Scheduling, archive delivery and manual execution are implemented. |
| Worker split `all / api / worker` | `supported` | Worker heartbeat and ownership are implemented. |
| RBAC inside the app | `supported` | Viewer, investigator, auditor, connector admin, executive and admin roles exist. |
| Docker / Windows / Linux packaging | `supported` | Build and installer paths are present. |
| Dense investigation graph | `supported` | Available with capped, on-demand loading. |
| `PostgreSQL` production path | `supported` | Production flow is designed around PostgreSQL. |
| `OpenSearch` runtime use | `partial` | Search support exists, but not every deployment runs it as primary runtime. |
| `Valkey` runtime use | `partial` | Cache support exists, but remains optional. |
| `ClickHouse` runtime use | `partial` | Query metrics and analytics export exist, but usage is still evolving. |
| `Neo4j` runtime use | `partial` | Optional graph backend support exists, but not every deployment uses it as primary store. |
| Multi-tenant concurrent isolation | `partial` | Workspace management exists, but true concurrent tenant isolation is not complete. |
| `AD / LDAP` collector validation | `partial` | Designed and partially implemented, but not validated live here. |
| `Microsoft Graph / Entra` | `partial` | Implemented/documented in part, not validated live here. |
| `Azure RBAC` | `partial` | Partial coverage and support notes exist. |
| `Okta` | `partial` | Partial runtime support exists. |
| `CyberArk` | `partial` | Partial runtime support exists. |
| `AWS IAM / Organizations` | `blueprint` | Modeled from official docs, not fully live in this runtime. |
| `Google Workspace / Drive` | `blueprint` | Modeled from official docs, not fully live in this runtime. |
| `M365 collaboration` | `blueprint` | Blueprint-only at the moment. |

## Notes

- Cloud and enterprise connector status is intentionally conservative.
- A connector is not treated as fully supported without real runtime validation.
- Internal environment variables still use the `EIP_*` prefix for backward compatibility.
