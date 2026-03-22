# GrantPath v0.1.0

First public release of GrantPath, a self-hosted Access Path Intelligence Platform focused on explainable access reasoning and operator workflows.

## Highlights

- live filesystem collection with retained raw snapshots
- explainable access paths
- `who-has-access` and principal footprint views
- what-if simulation
- review campaigns and remediation plans
- scheduled report delivery
- RBAC inside the application
- worker split `all / api / worker`
- optional runtime integrations for `Neo4j`, `OpenSearch`, `ClickHouse`, `Valkey`

## Positioning

GrantPath is not a static ACL auditor. It is an explainable control plane for access path intelligence.

## Production Notes

- strongest current scope: local filesystem access intelligence and governance workflows
- cloud and IAM connectors remain conservatively labeled when not live-validated
- internal environment variables keep the `EIP_*` prefix for compatibility

## Quality Gates

- backend tests passing
- frontend lint and build passing
- backend static security checks passing
- dependency audits passing
