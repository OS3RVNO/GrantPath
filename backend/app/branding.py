from __future__ import annotations

PRODUCT_NAME = "GrantPath"
PRODUCT_CATEGORY = "Access Path Intelligence Platform"
PRODUCT_API_TITLE = f"{PRODUCT_NAME} API"
PRODUCT_DEFAULT_TENANT_NAME = PRODUCT_NAME
PRODUCT_DEFAULT_TENANT_PLACEHOLDER = "Contoso GrantPath Workspace"
PRODUCT_REPORT_TITLE = f"{PRODUCT_NAME} Access Intelligence Report"
PRODUCT_REPORT_SUBJECT_PREFIX = f"{PRODUCT_NAME} report"
PRODUCT_REPORT_BODY = f"Your scheduled {PRODUCT_NAME} report is attached."


def default_workspace_name(hostname: str) -> str:
    safe_host = hostname.strip() or "Local"
    return f"{safe_host} - {PRODUCT_NAME}"
