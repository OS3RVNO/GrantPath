from __future__ import annotations

from app.models import ConnectorBlueprint, ConnectorBlueprintResponse, DocumentationLink


def build_connector_blueprints() -> ConnectorBlueprintResponse:
    blueprints = [
        ConnectorBlueprint(
            id="ad-ldap",
            vendor="Microsoft",
            surface="Active Directory / LDAP",
            collection_mode="hybrid",
            implementation_status="partial",
            priority=1,
            freshness="Near real-time membership snapshots, full ACL refresh on schedule",
            configuration_env=[
                "EIP_LDAP_SERVER_URI",
                "EIP_LDAP_BIND_DN",
                "EIP_LDAP_PASSWORD",
                "EIP_LDAP_BASE_DN",
            ],
            tenant_requirements=[
                "Reachable domain controllers or LDAP endpoints",
                "A read-only bind identity with directory read permissions",
            ],
            recommended_endpoints=[
                "LDAP search with member:1.2.840.113556.1.4.1941:=<DN> when the directory is Active Directory",
                "Security descriptor and ACL reads for file-share and object inheritance",
            ],
            required_permissions=[
                "Directory read on target domains",
                "Read access to security descriptors / ACL sources",
            ],
            supported_entities=[
                "Users",
                "Security groups",
                "Nested groups",
                "ACL-protected resources",
            ],
            algorithm_notes=[
                "Prefer server-side transitive evaluation over recursive client round-trips when the directory supports the AD matching rule in chain.",
                "Materialize membership closure once per snapshot and then join ACLs locally.",
                "Separate high-fanout subtree queries from steady-state delta polling.",
            ],
            consistency_notes=[
                "Subtree transitive queries can be CPU-intensive on high-fanout hierarchies.",
                "ACL inheritance must be modeled explicitly to explain downstream access paths.",
            ],
            official_limitations=[
                "LDAP_MATCHING_RULE_IN_CHAIN is Active Directory specific, not generic LDAP.",
                "Directory memberships alone do not replace ACL enumeration from files, shares or applications.",
            ],
            current_runtime_coverage=[
                "Reads users, groups and direct memberships from the configured base DN, and opportunistically upgrades to in-chain expansion when the directory accepts the AD matching rule.",
                "Does not yet collect directory object ACLs or replace dedicated file/share ACL collectors.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="Search Filter Syntax / LDAP_MATCHING_RULE_IN_CHAIN",
                    url="https://learn.microsoft.com/en-us/windows/win32/adsi/search-filter-syntax",
                ),
                DocumentationLink(
                    title="LDAP Matching Rules (MS-ADTS)",
                    url="https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/4e638665-f466-4597-93c4-12f2ebfabab5",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="entra-graph",
            vendor="Microsoft",
            surface="Microsoft Graph / Entra ID",
            collection_mode="incremental",
            implementation_status="partial",
            priority=1,
            freshness="Delta-driven with periodic full reconciliation",
            configuration_env=[
                "EIP_GRAPH_TENANT_ID",
                "EIP_GRAPH_CLIENT_ID",
                "EIP_GRAPH_CLIENT_SECRET",
            ],
            tenant_requirements=[
                "A Microsoft Entra application registration with application permissions",
                "Administrative consent for the required Graph scopes",
                "Sites.FullControl.All if SharePoint site permissions are collected",
            ],
            recommended_endpoints=[
                "GET /users/{id}/transitiveMemberOf",
                "Microsoft Graph delta query endpoints such as /users/delta and /groups/delta",
                "Microsoft Graph JSON batching for bounded fan-out collection",
            ],
            required_permissions=[
                "User.Read.All",
                "Group.Read.All",
                "GroupMember.Read.All",
                "RoleManagement.Read.Directory for directory role coverage",
                "Sites.FullControl.All for site permission enumeration",
            ],
            supported_entities=[
                "Users",
                "Groups",
                "Directory roles",
                "Administrative units",
            ],
            algorithm_notes=[
                "Use transitiveMemberOf for explainability and server-side closure.",
                "Use delta query tokens to reduce steady-state sync latency and payload size.",
                "Batch Graph calls, but keep batches within the documented 20-request limit.",
            ],
            consistency_notes=[
                "Advanced query behavior on directory objects requires the consistency header and can omit some properties.",
                "Delta pipelines need token persistence and fallback resync when tokens expire.",
                "Site permission enumeration should stay explicit and limited to the site surfaces the collector is told to crawl.",
            ],
            official_limitations=[
                "Graph batching is capped at 20 requests per batch.",
                "Delta tokens can expire and require a fallback full reconciliation.",
                "SharePoint site permission coverage is site-level and doesn't replace the separate Exchange or broader M365 collaboration surfaces.",
            ],
            current_runtime_coverage=[
                "Collects users, groups, batched transitive memberships and optional site-level SharePoint permissions for explicitly configured site IDs.",
                "Does not yet persist delta tokens or materialize directory roles and administrative units.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="List user transitiveMemberOf",
                    url="https://learn.microsoft.com/en-us/graph/api/user-list-transitivememberof?view=graph-rest-1.0",
                ),
                DocumentationLink(
                    title="Delta query overview",
                    url="https://learn.microsoft.com/en-us/graph/delta-query-overview",
                ),
                DocumentationLink(
                    title="JSON batching",
                    url="https://learn.microsoft.com/en-us/graph/json-batching",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="azure-rbac",
            vendor="Microsoft",
            surface="Azure RBAC",
            collection_mode="hybrid",
            implementation_status="partial",
            priority=1,
            freshness="Incremental role-assignment sync with scope-based rebuilds",
            configuration_env=[
                "EIP_GRAPH_TENANT_ID",
                "EIP_GRAPH_CLIENT_ID",
                "EIP_GRAPH_CLIENT_SECRET",
                "EIP_AZURE_SUBSCRIPTION_IDS",
            ],
            tenant_requirements=[
                "A service principal with authorization read access on the configured scopes",
                "Known subscription or management-group scopes to crawl",
            ],
            recommended_endpoints=[
                "Role Assignments - List For Scope",
                "Role definitions and management group / subscription scope enumeration",
            ],
            required_permissions=[
                "Microsoft.Authorization/roleAssignments/read",
                "Microsoft.Authorization/roleDefinitions/read",
            ],
            supported_entities=[
                "Role assignments",
                "Role definitions",
                "Subscriptions",
                "Resource groups",
                "Resources",
            ],
            algorithm_notes=[
                "Model scope inheritance from management group to resource instance.",
                "Partition collection by scope and cache role definitions separately from assignments.",
                "Recompute only impacted descendants when a scope-level assignment changes.",
            ],
            consistency_notes=[
                "Role assignments are attached to scopes and become effective on child scopes.",
                "Principal type filters and scope filters reduce collection volume significantly.",
            ],
            official_limitations=[
                "Assignments inherit down the scope tree, so scope modeling must stay explicit.",
                "Using $filter=atScope() only returns assignments at the current scope, so inherited parent scopes still need separate traversal.",
                "Listing only at a single scope is not enough to describe descendant exposure across management groups and resource groups.",
            ],
            current_runtime_coverage=[
                "Collects role assignments and role definitions for configured subscriptions using subscription-scope reads.",
                "Does not yet crawl management groups or enumerate inherited parent assignments above the configured subscription scopes.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="Understand Azure role assignments",
                    url="https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments",
                ),
                DocumentationLink(
                    title="Role Assignments - List For Scope",
                    url="https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/list-for-scope?view=rest-authorization-2022-04-01",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="m365-collaboration",
            vendor="Microsoft",
            surface="SharePoint Online / Exchange Online",
            collection_mode="hybrid",
            implementation_status="blueprint",
            priority=2,
            freshness="Site and mailbox snapshots with ticket-aware exception overlays",
            configuration_env=[
                "EIP_GRAPH_TENANT_ID",
                "EIP_GRAPH_CLIENT_ID",
                "EIP_GRAPH_CLIENT_SECRET",
            ],
            tenant_requirements=[
                "Graph application permissions for SharePoint surfaces",
                "Exchange Online admin or app-based access for mailbox permission enumeration",
            ],
            recommended_endpoints=[
                "GET /sites/{site-id}/permissions for site-level permissions",
                "Get-MailboxPermission for mailbox full-access and inherited grants",
            ],
            required_permissions=[
                "Sites.FullControl.All for site permissions enumeration",
                "Exchange Online permission to run Get-MailboxPermission",
            ],
            supported_entities=[
                "SharePoint site permissions",
                "Mailbox delegates",
                "Shared mailboxes",
            ],
            algorithm_notes=[
                "Treat SharePoint site permissions and Exchange mailbox permissions as separate collectors.",
                "Overlay direct exceptions and ticketed overrides on top of group-derived paths.",
                "Persist mailbox delegates separately because Graph does not replace Exchange permission views.",
            ],
            consistency_notes=[
                "Site permission enumeration has documented limitations for subsites and selected permissions.",
                "Mailbox permission analysis must account for inherited entries and deny flags.",
            ],
            official_limitations=[
                "Graph site permission coverage is not a full replacement for all SharePoint inheritance and selected-permission cases.",
                "Exchange mailbox permission analysis still depends on Exchange-specific administration surfaces.",
            ],
            current_runtime_coverage=[
                "Blueprint only in this runtime; SharePoint and Exchange remain intentionally separate until both collectors are wired.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="List site permissions",
                    url="https://learn.microsoft.com/en-us/graph/api/site-list-permissions?view=graph-rest-1.0",
                ),
                DocumentationLink(
                    title="Get-MailboxPermission",
                    url="https://learn.microsoft.com/en-us/powershell/module/exchange/get-mailboxpermission?view=exchange-ps",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="okta-ud",
            vendor="Okta",
            surface="Okta Universal Directory",
            collection_mode="incremental",
            implementation_status="partial",
            priority=2,
            freshness="Paginated sync with reconciliation windows for eventually-consistent search",
            configuration_env=[
                "EIP_OKTA_BASE_URL",
                "EIP_OKTA_API_TOKEN",
            ],
            tenant_requirements=[
                "An Okta org base URL reachable from the control plane",
                "API token with users and groups read scopes",
            ],
            recommended_endpoints=[
                "List all groups",
                "List all member users",
                "User resources / groups",
            ],
            required_permissions=[
                "okta.groups.read",
                "okta.users.read",
            ],
            supported_entities=[
                "Users",
                "Groups",
                "Group memberships",
                "Entitlement overlays",
            ],
            algorithm_notes=[
                "Drive sync from pagination Link headers instead of offset-based loops.",
                "Keep page sizes at or below documented limits for group-membership reads.",
                "Use search for discovery, but reconcile against point-in-time list reads before writing authoritative state.",
            ],
            consistency_notes=[
                "Search results are documented as eventually consistent.",
                "Group-membership list operations are paginated and capped per request.",
                "The default users list omits DEPROVISIONED users unless a separate search or filter path is used.",
            ],
            official_limitations=[
                "Search-based discovery is eventually consistent and should not be the only authoritative path.",
                "Membership expansion needs Link-header pagination handling to avoid silent truncation.",
                "The default users list doesn't give complete leaver coverage because DEPROVISIONED users aren't returned unless you query for them explicitly.",
            ],
            current_runtime_coverage=[
                "Collects users, groups and direct group memberships through paginated REST reads.",
                "Does not yet reconcile DEPROVISIONED users, application assignments or entitlement overlays beyond core directory objects.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="Groups API",
                    url="https://developer.okta.com/docs/api/openapi/okta-management/management/tag/Group/",
                ),
                DocumentationLink(
                    title="User Resources API",
                    url="https://developer.okta.com/docs/api/openapi/okta-management/management/tag/UserResources/",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="google-directory",
            vendor="Google",
            surface="Google Workspace Directory / Cloud Identity",
            collection_mode="incremental",
            implementation_status="blueprint",
            priority=2,
            freshness="User and group snapshots with pagination-aware reconciliation",
            configuration_env=[
                "EIP_GOOGLE_CUSTOMER_ID",
                "EIP_GOOGLE_SERVICE_ACCOUNT_JSON",
                "EIP_GOOGLE_ADMIN_SUBJECT",
            ],
            tenant_requirements=[
                "A Workspace or Cloud Identity tenant with domain-wide delegation approved",
                "A service account delegated to an administrative subject",
            ],
            recommended_endpoints=[
                "Directory API users.list",
                "Directory API groups.list",
                "Directory API members.list",
            ],
            required_permissions=[
                "admin.directory.user.readonly",
                "admin.directory.group.readonly",
                "admin.directory.group.member.readonly",
            ],
            supported_entities=[
                "Users",
                "Groups",
                "Group memberships",
                "Aliases",
            ],
            algorithm_notes=[
                "Persist page tokens and customer-scoped snapshots for deterministic reconciliation.",
                "Normalize primary email, aliases and immutable IDs separately to improve cross-source identity linking.",
            ],
            consistency_notes=[
                "Directory collection should respect customer-scoped pagination and delegated-admin boundaries.",
                "Group membership should be collected independently from user inventory to keep rebuilds smaller.",
            ],
            official_limitations=[
                "Domain-wide delegation is required for broad tenant collection.",
                "Directory inventory must stay scoped to either a customer or a domain during collection.",
                "Directory coverage alone does not explain Drive or Google Cloud resource permissions.",
            ],
            current_runtime_coverage=[
                "Blueprint only in this runtime.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="Users: list",
                    url="https://developers.google.com/workspace/admin/directory/reference/rest/v1/users/list",
                ),
                DocumentationLink(
                    title="Groups: list",
                    url="https://developers.google.com/workspace/admin/directory/reference/rest/v1/groups/list",
                ),
                DocumentationLink(
                    title="Members: list",
                    url="https://developers.google.com/workspace/admin/directory/reference/rest/v1/members/list",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="google-drive-collaboration",
            vendor="Google",
            surface="Google Drive / Shared Drives",
            collection_mode="hybrid",
            implementation_status="blueprint",
            priority=2,
            freshness="Drive and shared-drive permission snapshots with targeted exception overlays",
            configuration_env=[
                "EIP_GOOGLE_CUSTOMER_ID",
                "EIP_GOOGLE_SERVICE_ACCOUNT_JSON",
                "EIP_GOOGLE_ADMIN_SUBJECT",
            ],
            tenant_requirements=[
                "A delegated service account with Drive read scopes",
                "Resource discovery scoped to shared drives or selected corpora",
            ],
            recommended_endpoints=[
                "Drive API permissions.list",
                "Drive API files.list for resource discovery with shared-drive aware parameters",
            ],
            required_permissions=[
                "drive.metadata.readonly or broader Drive read scopes for metadata and permissions",
            ],
            supported_entities=[
                "Files",
                "Folders",
                "Shared drives",
                "Direct permissions",
            ],
            algorithm_notes=[
                "Separate directory identities from Drive permissions and join them through stable principals during normalization.",
                "Favor shared-drive and corpus-aware crawls instead of unrestricted resource fan-out.",
            ],
            consistency_notes=[
                "Drive permissions should be interpreted together with inheritance and shared-drive context.",
                "Large corpora require scoped discovery to keep collection predictable.",
            ],
            official_limitations=[
                "Drive permissions require resource discovery as well as permission enumeration.",
                "Shared-drive collection needs supportsAllDrives plus scoped corpora or driveId inputs.",
                "Resource-level access in Drive should not be inferred from Workspace directory objects alone.",
            ],
            current_runtime_coverage=[
                "Blueprint only in this runtime.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="Permissions: list",
                    url="https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/list",
                ),
                DocumentationLink(
                    title="Files: list",
                    url="https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="aws-iam",
            vendor="Amazon Web Services",
            surface="AWS IAM / Organizations",
            collection_mode="hybrid",
            implementation_status="blueprint",
            priority=2,
            freshness="Account-aware IAM snapshots with simulation-assisted what-if analysis",
            configuration_env=[
                "EIP_AWS_ACCESS_KEY_ID",
                "EIP_AWS_SECRET_ACCESS_KEY",
                "EIP_AWS_ACCOUNT_IDS",
            ],
            tenant_requirements=[
                "IAM read access in the target account or an assumed role per account",
                "Organizations visibility if account enumeration is centralized",
            ],
            recommended_endpoints=[
                "IAM ListUsers / ListRoles / ListPolicies",
                "IAM ListGroupsForUser / ListAttachedUserPolicies / ListAttachedRolePolicies",
                "Organizations ListAccounts",
                "IAM SimulatePrincipalPolicy",
            ],
            required_permissions=[
                "iam:ListUsers",
                "iam:ListRoles",
                "iam:ListPolicies",
                "iam:SimulatePrincipalPolicy",
                "organizations:ListAccounts",
            ],
            supported_entities=[
                "Users",
                "Groups",
                "Roles",
                "Managed policies",
                "Accounts",
            ],
            algorithm_notes=[
                "Collect identities and policies separately, then resolve policy attachments and simulations during graph materialization.",
                "Partition by account and cache reusable managed-policy documents independently from attachment edges.",
                "Honor Marker and NextToken pagination semantics separately for IAM and Organizations surfaces.",
            ],
            consistency_notes=[
                "IAM collection must remain account-aware even when centralized through Organizations.",
                "Policy simulation is task-oriented and should not replace snapshot inventory.",
            ],
            official_limitations=[
                "Organizations account inventory is separate from IAM identity inventory.",
                "IAM list APIs rely on Marker and IsTruncated pagination rather than Graph-style next links.",
                "Effective permission analysis in AWS often requires simulation in addition to raw policy attachment reads.",
            ],
            current_runtime_coverage=[
                "Blueprint only in this runtime.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="ListUsers",
                    url="https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListUsers.html",
                ),
                DocumentationLink(
                    title="ListGroupsForUser",
                    url="https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListGroupsForUser.html",
                ),
                DocumentationLink(
                    title="SimulatePrincipalPolicy",
                    url="https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html",
                ),
                DocumentationLink(
                    title="Organizations ListAccounts",
                    url="https://docs.aws.amazon.com/organizations/latest/APIReference/API_ListAccounts.html",
                ),
            ],
        ),
        ConnectorBlueprint(
            id="cyberark-privileged",
            vendor="CyberArk",
            surface="CyberArk Privileged Access / Secure Infrastructure Access",
            collection_mode="snapshot",
            implementation_status="partial",
            priority=3,
            freshness="Privileged safe and vault snapshots on tighter cadence for emergency paths",
            configuration_env=[
                "EIP_CYBERARK_BASE_URL",
                "EIP_CYBERARK_USERNAME",
                "EIP_CYBERARK_PASSWORD",
            ],
            tenant_requirements=[
                "An API-capable CyberArk deployment reachable from the control plane",
                "An integration identity allowed to read safes and memberships",
            ],
            recommended_endpoints=[
                "Safe member and privileged access APIs from the CyberArk API hub",
                "Vault / emergency responder membership collection with expiry awareness",
            ],
            required_permissions=[
                "Read access to privileged identities, safes or responder groups",
            ],
            supported_entities=[
                "Break-glass groups",
                "Vault memberships",
                "Privileged entitlements",
            ],
            algorithm_notes=[
                "Keep privileged connectors isolated and reconcile them independently from workforce identity syncs.",
                "Persist expiry and ticket metadata so emergency entitlements remain explainable.",
            ],
            consistency_notes=[
                "Privileged paths should be refreshed on a tighter interval than baseline identity data.",
                "Emergency entitlements require explicit expiry handling and audit export.",
            ],
            official_limitations=[
                "Privileged entitlements need explicit expiry and break-glass semantics, not just static membership edges.",
                "Safe inventories alone do not cover every privileged access path outside the collected CyberArk surfaces.",
            ],
            current_runtime_coverage=[
                "Collects safe memberships and basic permission flags from CyberArk safes.",
                "Does not yet collect responder expiry metadata or ticket overlays.",
            ],
            documentation_links=[
                DocumentationLink(
                    title="CyberArk API Hub",
                    url="https://api-docs.cyberark.com/",
                ),
                DocumentationLink(
                    title="Secure Infrastructure Access APIs",
                    url="https://api-docs.cyberark.com/docs/siem-and-utilities/secure-infrastructure-access",
                ),
            ],
        ),
    ]

    return ConnectorBlueprintResponse(
        generated_at="2026-03-14T10:30:00Z",
        blueprints=sorted(blueprints, key=lambda item: (item.priority, item.vendor, item.surface)),
    )
