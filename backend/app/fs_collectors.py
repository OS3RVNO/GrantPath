from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess  # nosec B404
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import paramiko

from app.branding import default_workspace_name
from app.config import settings
from app.models import ConnectorStatus, Entity, HistoricalPoint, InsightNote, Relationship, ScanTarget, Snapshot

WINDOWS_BUILTIN_GROUPS = {
    "administrators",
    "users",
    "guests",
    "authenticated users",
    "everyone",
    "interactive",
    "backup operators",
    "performance monitor users",
    "performance log users",
}
SERVICE_MARKERS = ("system", "service", "daemon", "trustedinstaller", "local service", "network service")
BROAD_ACCESS_MARKERS = ("everyone", "authenticated users", "builtin\\users", " users")
PRIVILEGED_PERMISSION_MARKERS = ("write", "modify", "delete", "full", "takeownership", "changepermissions")


@dataclass
class IdentityRecord:
    name: str
    kind: str
    description: str
    aliases: set[str]


@dataclass
class MembershipRecord:
    member: str
    group: str
    member_kind: str


@dataclass
class AccessEntry:
    identity: str
    permissions: list[str]
    access_type: str
    inherited: bool


@dataclass
class PathRecord:
    path: str
    is_directory: bool
    owner: str | None
    access_entries: list[AccessEntry]
    size: int
    fingerprint: str | None = None


@dataclass
class TargetScanResult:
    target: ScanTarget
    items: list[PathRecord]
    warnings: list[str]
    duration_ms: float
    cache_hits: int = 0
    cache_misses: int = 0


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def collect_real_snapshot(
    targets: list[ScanTarget],
    historical_metrics: list[dict[str, object]],
    *,
    cache_by_target: dict[str, dict[str, dict[str, object]]] | None = None,
) -> dict[str, object]:
    timings: list[tuple[str, float]] = []
    cache_by_target = cache_by_target or {}

    enabled_targets = [target for target in targets if target.enabled]
    scan_results: list[TargetScanResult] = []
    all_warnings: list[str] = []
    filesystem_started = perf_counter()
    worker_count = min(
        max(1, int(os.getenv("EIP_TARGET_SCAN_WORKERS", "4"))),
        len(enabled_targets) if enabled_targets else 1,
    )
    ordered_results: list[TargetScanResult | None] = [None] * len(enabled_targets)
    with ThreadPoolExecutor(
        max_workers=max(1, worker_count + 1),
        thread_name_prefix="eip-collect",
    ) as executor:
        identity_future: Future[tuple[list[IdentityRecord], list[MembershipRecord], float]] = executor.submit(
            _enumerate_local_identities_timed
        )
        futures = {
            executor.submit(_scan_target, target, cache_by_target.get(target.id, {})): index
            for index, target in enumerate(enabled_targets)
        }
        for future in as_completed(futures):
            index = futures[future]
            result = future.result()
            ordered_results[index] = result
            all_warnings.extend(result.warnings)
        identities, memberships, identity_duration_ms = identity_future.result()
    timings.append(("identity_enumeration", identity_duration_ms))
    scan_results = [result for result in ordered_results if result is not None]
    timings.append(("filesystem_collection", (perf_counter() - filesystem_started) * 1000))

    snapshot_started = perf_counter()
    snapshot_payload = _build_snapshot(
        identities=identities,
        memberships=memberships,
        scan_results=scan_results,
        warnings=all_warnings,
        historical_metrics=historical_metrics,
    )
    timings.append(("snapshot_build", (perf_counter() - snapshot_started) * 1000))
    snapshot_payload["timings"] = timings
    snapshot_payload["cache_records_by_target"] = {
        result.target.id: [_cache_record_for_target(item) for item in result.items]
        for result in scan_results
    }
    snapshot_payload["raw_payload"] = _raw_collection_payload(
        identities=identities,
        memberships=memberships,
        scan_results=scan_results,
        generated_at=snapshot_payload["snapshot"].generated_at,
    )
    snapshot_payload["cache_hits"] = sum(result.cache_hits for result in scan_results)
    snapshot_payload["cache_misses"] = sum(result.cache_misses for result in scan_results)
    if snapshot_payload["cache_hits"]:
        snapshot_payload["notes"] = list(snapshot_payload["notes"]) + [
            f"Incremental collection cache reused {snapshot_payload['cache_hits']} unchanged filesystem objects."
        ]
    return snapshot_payload


def _enumerate_local_identities() -> tuple[list[IdentityRecord], list[MembershipRecord]]:
    if platform.system() == "Windows":
        return _enumerate_windows_identities()
    return _enumerate_linux_identities()


def _enumerate_local_identities_timed() -> tuple[list[IdentityRecord], list[MembershipRecord], float]:
    started = perf_counter()
    identities, memberships = _enumerate_local_identities()
    return identities, memberships, (perf_counter() - started) * 1000


def _enumerate_windows_identities() -> tuple[list[IdentityRecord], list[MembershipRecord]]:
    hostname = os.environ.get("COMPUTERNAME", socket.gethostname())
    users: list[IdentityRecord] = []
    memberships: list[MembershipRecord] = []
    groups: list[IdentityRecord] = []

    user_rows = _run_powershell_json_lines(
        """
        Get-LocalUser | ForEach-Object {
          [PSCustomObject]@{
            name = $_.Name
            enabled = [bool]$_.Enabled
            description = $_.Description
          } | ConvertTo-Json -Compress -Depth 4
        }
        """
    )
    for row in user_rows:
        name = str(row["name"])
        principal = f"{hostname}\\{name}"
        users.append(
            IdentityRecord(
                name=principal,
                kind="user",
                description=(
                    f"Local Windows user on {hostname}."
                    if not row.get("description")
                    else str(row["description"])
                ),
                aliases={principal, name},
            )
        )

    group_rows = _run_powershell_json_lines(
        """
        Get-LocalGroup | ForEach-Object {
          [PSCustomObject]@{
            name = $_.Name
            description = $_.Description
          } | ConvertTo-Json -Compress -Depth 4
        }
        """
    )
    for row in group_rows:
        name = str(row["name"])
        aliases = {
            name,
            f"{hostname}\\{name}",
            f"BUILTIN\\{name}",
        }
        groups.append(
            IdentityRecord(
                name=f"BUILTIN\\{name}" if name.lower() in WINDOWS_BUILTIN_GROUPS else f"{hostname}\\{name}",
                kind="group",
                description=(
                    f"Local Windows group on {hostname}."
                    if not row.get("description")
                    else str(row["description"])
                ),
                aliases=aliases,
            )
        )

    membership_rows = _run_powershell_json_lines(
        """
        $groups = Get-LocalGroup | Select-Object -ExpandProperty Name
        foreach ($group in $groups) {
          try {
            Get-LocalGroupMember -Group $group -ErrorAction Stop | ForEach-Object {
              [PSCustomObject]@{
                group = $group
                member = $_.Name
                object_class = $_.ObjectClass.ToString()
              } | ConvertTo-Json -Compress -Depth 4
            }
          } catch {
            continue
          }
        }
        """
    )
    for row in membership_rows:
        object_class = str(row.get("object_class", "")).lower()
        memberships.append(
            MembershipRecord(
                member=str(row["member"]),
                group=str(row["group"]),
                member_kind="group" if "grupp" in object_class or "group" in object_class else "user",
            )
        )

    return users + groups, memberships


def _enumerate_linux_identities() -> tuple[list[IdentityRecord], list[MembershipRecord]]:
    import grp
    import pwd

    users: list[IdentityRecord] = []
    groups: list[IdentityRecord] = []
    memberships: list[MembershipRecord] = []

    for user in pwd.getpwall():
        principal = user.pw_name
        users.append(
            IdentityRecord(
                name=principal,
                kind="service_account" if principal in {"root"} or principal.endswith("$") else "user",
                description=f"Local Linux account {principal}.",
                aliases={principal},
            )
        )

    for group in grp.getgrall():
        groups.append(
            IdentityRecord(
                name=group.gr_name,
                kind="group",
                description=f"Local Linux group {group.gr_name}.",
                aliases={group.gr_name},
            )
        )
        for member in group.gr_mem:
            memberships.append(MembershipRecord(member=member, group=group.gr_name, member_kind="user"))

    groups.append(
        IdentityRecord(
            name="Everyone",
            kind="group",
            description="Synthetic POSIX fallback group representing other/world permissions.",
            aliases={"Everyone", "Other"},
        )
    )

    return users + groups, memberships


def _scan_target(
    target: ScanTarget,
    cache_for_target: dict[str, dict[str, object]] | None = None,
) -> TargetScanResult:
    started = perf_counter()
    cache_for_target = cache_for_target or {}
    if target.connection_mode == "ssh":
        result = _scan_ssh_target(target, cache_for_target)
    else:
        current_platform = platform.system().lower()
        platform_hint = target.platform if target.platform != "auto" else current_platform
        if platform_hint == "windows":
            result = _scan_windows_target(target)
        else:
            result = _scan_linux_target(target, cache_for_target)
    result.duration_ms = (perf_counter() - started) * 1000
    return result


def _scan_windows_target(target: ScanTarget) -> TargetScanResult:
    escaped_path = target.path.replace("'", "''")
    hidden_expr = "$true" if target.include_hidden else "$false"
    recursive_expr = "$true" if target.recursive else "$false"
    script = f"""
    $Path = '{escaped_path}'
    $Recursive = {recursive_expr}
    $MaxDepth = {target.max_depth}
    $MaxEntries = {target.max_entries}
    $IncludeHidden = {hidden_expr}

    try {{
      $root = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    }} catch {{
      Write-Output "__WARN__Target unavailable: $Path :: $($_.Exception.Message)"
      exit 0
    }}

    $queue = New-Object System.Collections.Queue
    $queue.Enqueue([PSCustomObject]@{{ Item = $root; Depth = 0 }})
    $count = 0
    while ($queue.Count -gt 0 -and $count -lt $MaxEntries) {{
      $current = $queue.Dequeue()
      $item = $current.Item
      $attributes = $item.Attributes.ToString()
      if (-not $IncludeHidden -and $attributes.Contains('Hidden')) {{
        continue
      }}

      try {{
        $acl = Get-Acl -LiteralPath $item.FullName -ErrorAction Stop
      }} catch {{
        Write-Output "__WARN__ACL unavailable: $($item.FullName) :: $($_.Exception.Message)"
        continue
      }}

      $access = @(
        $acl.Access | ForEach-Object {{
          [PSCustomObject]@{{
            identity = $_.IdentityReference.Value
            rights = $_.FileSystemRights.ToString()
            access_type = $_.AccessControlType.ToString()
            inherited = [bool]$_.IsInherited
          }}
        }}
      )

      [PSCustomObject]@{{
        path = $item.FullName
        is_directory = [bool]$item.PSIsContainer
        size = if ($item.PSIsContainer) {{ 0 }} else {{ [int64]$item.Length }}
        owner = $acl.Owner
        access = $access
      }} | ConvertTo-Json -Compress -Depth 6
      $count++

      if ($Recursive -and $item.PSIsContainer -and $current.Depth -lt $MaxDepth) {{
        try {{
          Get-ChildItem -LiteralPath $item.FullName -Force -ErrorAction Stop | ForEach-Object {{
            $queue.Enqueue([PSCustomObject]@{{ Item = $_; Depth = $current.Depth + 1 }})
          }}
        }} catch {{
          Write-Output "__WARN__Enumeration unavailable: $($item.FullName) :: $($_.Exception.Message)"
        }}
      }}
    }}
    """

    rows, warnings = _run_powershell_structured(script)
    items = [
        PathRecord(
            path=str(row["path"]),
            is_directory=bool(row["is_directory"]),
            owner=str(row["owner"]) if row.get("owner") else None,
            size=int(row.get("size", 0) or 0),
            access_entries=[
                AccessEntry(
                    identity=str(access["identity"]),
                    permissions=_normalize_windows_permissions(str(access.get("rights", ""))),
                    access_type=str(access.get("access_type", "Allow")),
                    inherited=bool(access.get("inherited", False)),
                )
                for access in row.get("access", [])
                if _normalize_windows_permissions(str(access.get("rights", "")))
            ],
            fingerprint=None,
        )
        for row in rows
    ]
    return TargetScanResult(target=target, items=items, warnings=warnings, duration_ms=0.0)


def _scan_linux_target(
    target: ScanTarget,
    cache_for_target: dict[str, dict[str, object]],
) -> TargetScanResult:
    import grp
    import pwd

    warnings: list[str] = []
    items: list[PathRecord] = []
    cache_hits = 0
    cache_misses = 0
    root = Path(target.path)
    if not root.exists():
        return TargetScanResult(
            target=target,
            items=[],
            warnings=[f"Target unavailable: {target.path}"],
            duration_ms=0.0,
        )

    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    while queue and len(items) < target.max_entries:
        current, depth = queue.popleft()
        if not target.include_hidden and current.name.startswith(".") and current != root:
            continue

        try:
            file_stat = current.stat(follow_symlinks=False)
        except OSError as exc:
            warnings.append(f"Stat unavailable: {current} :: {exc}")
            continue

        try:
            owner = pwd.getpwuid(file_stat.st_uid).pw_name
        except KeyError:
            owner = str(file_stat.st_uid)
        try:
            group_name = grp.getgrgid(file_stat.st_gid).gr_name
        except KeyError:
            group_name = str(file_stat.st_gid)

        path_value = str(current)
        is_directory = stat.S_ISDIR(file_stat.st_mode)
        fingerprint = _linux_fingerprint(path_value, file_stat)
        cached_record = _cached_path_record(path_value, fingerprint, cache_for_target)
        if cached_record is not None:
            items.append(cached_record)
            cache_hits += 1
        else:
            access_entries = _linux_access_entries(path_value, owner, group_name, file_stat.st_mode)
            access_entries = [entry for entry in access_entries if entry.permissions]
            items.append(
                PathRecord(
                    path=path_value,
                    is_directory=is_directory,
                    owner=owner,
                    size=0 if is_directory else int(file_stat.st_size),
                    access_entries=access_entries,
                    fingerprint=fingerprint,
                )
            )
            cache_misses += 1

        if target.recursive and is_directory and depth < target.max_depth:
            try:
                with os.scandir(current) as iterator:
                    children = sorted(
                        [Path(entry.path) for entry in iterator],
                        key=lambda item: item.name.lower(),
                    )
            except OSError as exc:
                warnings.append(f"Enumeration unavailable: {current} :: {exc}")
                continue
            for child in children:
                queue.append((child, depth + 1))

    return TargetScanResult(
        target=target,
        items=items,
        warnings=warnings,
        duration_ms=0.0,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


def _scan_ssh_target(
    target: ScanTarget,
    cache_for_target: dict[str, dict[str, object]],
) -> TargetScanResult:
    warnings: list[str] = []
    items: list[PathRecord] = []
    cache_hits = 0
    cache_misses = 0
    if not target.host or not target.username:
        return TargetScanResult(
            target=target,
            items=[],
            warnings=["SSH target requires host and username."],
            duration_ms=0.0,
        )

    connect_kwargs: dict[str, object] = {
        "hostname": target.host,
        "port": target.port,
        "username": target.username,
        "timeout": 20,
        "look_for_keys": True,
    }
    if target.key_path:
        connect_kwargs["key_filename"] = target.key_path
    elif target.secret_env and os.getenv(target.secret_env):
        connect_kwargs["password"] = os.getenv(target.secret_env)

    script = _remote_linux_enumerator_script(
        target.path,
        recursive=target.recursive,
        max_depth=target.max_depth,
        max_entries=target.max_entries,
        include_hidden=target.include_hidden,
        cache_for_target=cache_for_target,
    )

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if settings.ssh_known_hosts_path:
        client.load_host_keys(settings.ssh_known_hosts_path)
    if settings.allow_insecure_ssh_host_keys:
        warnings.append(
            "EIP_ALLOW_INSECURE_SSH_HOST_KEYS is set, but the hardened runtime still enforces strict host key verification."
        )
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(**connect_kwargs)
        output, error = _exec_remote_python(client, script)
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("__WARN__"):
                warnings.append(line.replace("__WARN__", "", 1).strip())
                continue
            payload = json.loads(line)
            if payload.get("cache_hit"):
                cache_hits += 1
            else:
                cache_misses += 1
            items.append(
                PathRecord(
                    path=str(payload["path"]),
                    is_directory=bool(payload["is_directory"]),
                    owner=str(payload.get("owner")) if payload.get("owner") else None,
                    size=int(payload.get("size", 0) or 0),
                    access_entries=[
                        AccessEntry(
                            identity=str(entry["identity"]),
                            permissions=list(entry["permissions"]),
                            access_type=str(entry.get("access_type", "Allow")),
                            inherited=False,
                        )
                        for entry in payload.get("access", [])
                    ],
                    fingerprint=str(payload.get("fingerprint")) if payload.get("fingerprint") else None,
                )
            )
        if error.strip():
            warnings.append(error.strip())
    except Exception as exc:
        warnings.append(str(exc))
    finally:
        client.close()

    return TargetScanResult(
        target=target,
        items=items,
        warnings=warnings,
        duration_ms=0.0,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


def _normalize_windows_permissions(raw_rights: str) -> list[str]:
    permissions: set[str] = set()
    lowered = raw_rights.lower()
    tokens = [token.strip().lower() for token in raw_rights.split(",")]

    if "fullcontrol" in lowered:
        permissions.update({"Read", "Write", "Delete", "Execute", "ChangePermissions", "TakeOwnership"})
    if "modify" in lowered:
        permissions.update({"Read", "Write", "Delete", "Execute"})
    if "readandexecute" in lowered:
        permissions.update({"Read", "Execute"})
    if "read" in lowered:
        permissions.add("Read")
    if "write" in lowered or "createfiles" in lowered or "createdirectories" in lowered:
        permissions.add("Write")
    if "delete" in lowered:
        permissions.add("Delete")
    if "traverse" in lowered or "executefile" in lowered:
        permissions.add("Execute")
    if "changepermissions" in lowered:
        permissions.add("ChangePermissions")
    if "takeownership" in lowered:
        permissions.add("TakeOwnership")

    if not permissions and raw_rights:
        permissions.add(raw_rights)

    if "synchronize" in tokens and len(permissions) > 1:
        permissions.discard("Synchronize")
    return sorted(permissions)


def _mode_to_permissions(mode: int, scope: str) -> list[str]:
    permission_map = {
        "owner": (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
        "group": (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
        "other": (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH),
    }
    read_bit, write_bit, execute_bit = permission_map[scope]
    permissions: list[str] = []
    if mode & read_bit:
        permissions.append("Read")
    if mode & write_bit:
        permissions.append("Write")
    if mode & execute_bit:
        permissions.append("Execute")
    return permissions


def _linux_access_entries(path_value: str, owner: str, group_name: str, mode: int) -> list[AccessEntry]:
    acl_entries = _getfacl_entries(path_value)
    if acl_entries:
        return acl_entries
    return [
        AccessEntry(identity=owner, permissions=_mode_to_permissions(mode, "owner"), access_type="Allow", inherited=False),
        AccessEntry(identity=group_name, permissions=_mode_to_permissions(mode, "group"), access_type="Allow", inherited=False),
        AccessEntry(identity="Everyone", permissions=_mode_to_permissions(mode, "other"), access_type="Allow", inherited=False),
    ]


def _getfacl_entries(path_value: str) -> list[AccessEntry]:
    getfacl_binary = shutil.which("getfacl")
    if not getfacl_binary:
        return []
    try:
        completed = subprocess.run(
            [getfacl_binary, "-cp", path_value],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )  # nosec B603
    except FileNotFoundError:
        return []
    if completed.returncode != 0:
        return []

    entries: list[AccessEntry] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 3:
            continue
        tag = parts[0]
        subject = parts[1] or ("Everyone" if tag == "other" else "")
        permissions = _rwx_to_permissions(parts[2])
        if not permissions:
            continue
        identity = subject or tag
        if tag == "group" and subject:
            identity = subject
        elif tag == "user" and subject:
            identity = subject
        entries.append(
            AccessEntry(
                identity=identity,
                permissions=permissions,
                access_type="Allow",
                inherited=False,
            )
        )
    return entries


def _rwx_to_permissions(raw: str) -> list[str]:
    permissions: list[str] = []
    if len(raw) >= 1 and raw[0] == "r":
        permissions.append("Read")
    if len(raw) >= 2 and raw[1] == "w":
        permissions.append("Write")
    if len(raw) >= 3 and raw[2] in {"x", "X"}:
        permissions.append("Execute")
    return permissions


def _linux_fingerprint(path_value: str, file_stat_result) -> str:
    seed = (
        f"{path_value}|{file_stat_result.st_mode}|{file_stat_result.st_uid}|"
        f"{file_stat_result.st_gid}|{file_stat_result.st_size}|"
        f"{getattr(file_stat_result, 'st_mtime_ns', int(file_stat_result.st_mtime * 1_000_000_000))}|"
        f"{getattr(file_stat_result, 'st_ctime_ns', int(file_stat_result.st_ctime * 1_000_000_000))}"
    )
    return hashlib.blake2s(seed.encode("utf-8"), digest_size=8).hexdigest()


def _cache_record_for_target(record: PathRecord) -> dict[str, object]:
    fingerprint = hashlib.blake2s(
        json.dumps(
            {
                "path": record.path,
                "is_directory": record.is_directory,
                "owner": record.owner,
                "size": record.size,
                "access": [
                    {
                        "identity": entry.identity,
                        "permissions": entry.permissions,
                        "access_type": entry.access_type,
                        "inherited": entry.inherited,
                    }
                    for entry in record.access_entries
                ],
            },
            sort_keys=True,
        ).encode("utf-8"),
        digest_size=8,
    ).hexdigest()
    return {
        "path": record.path,
        "fingerprint": record.fingerprint or fingerprint,
        "record": {
            "path": record.path,
            "is_directory": record.is_directory,
            "owner": record.owner,
            "size": record.size,
            "access_entries": [
                {
                    "identity": entry.identity,
                    "permissions": entry.permissions,
                    "access_type": entry.access_type,
                    "inherited": entry.inherited,
                }
                for entry in record.access_entries
            ],
        },
    }


def _cached_path_record(
    path_value: str,
    fingerprint: str,
    cache_for_target: dict[str, dict[str, object]],
) -> PathRecord | None:
    cached = cache_for_target.get(path_value)
    if not cached or str(cached.get("fingerprint")) != fingerprint:
        return None
    payload = cached.get("record")
    if not isinstance(payload, dict):
        return None
    return PathRecord(
        path=str(payload.get("path", path_value)),
        is_directory=bool(payload.get("is_directory", False)),
        owner=str(payload.get("owner")) if payload.get("owner") is not None else None,
        size=int(payload.get("size", 0) or 0),
        access_entries=[
            AccessEntry(
                identity=str(entry.get("identity", "")),
                permissions=list(entry.get("permissions", [])),
                access_type=str(entry.get("access_type", "Allow")),
                inherited=bool(entry.get("inherited", False)),
            )
            for entry in payload.get("access_entries", [])
            if entry.get("identity")
        ],
        fingerprint=fingerprint,
    )


def _remote_linux_enumerator_script(
    path_value: str,
    *,
    recursive: bool,
    max_depth: int,
    max_entries: int,
    include_hidden: bool,
    cache_for_target: dict[str, dict[str, object]],
) -> str:
    cache_json = json.dumps(cache_for_target, separators=(",", ":"))
    script = f"""
import collections, hashlib, json, os, pathlib, pwd, grp, stat, subprocess
ROOT = pathlib.Path({path_value!r})
RECURSIVE = {str(recursive)}
MAX_DEPTH = {max_depth}
MAX_ENTRIES = {max_entries}
INCLUDE_HIDDEN = {str(include_hidden)}
CACHE = json.loads({cache_json!r})

def rwx_to_permissions(raw):
    items = []
    if len(raw) >= 1 and raw[0] == 'r':
        items.append('Read')
    if len(raw) >= 2 and raw[1] == 'w':
        items.append('Write')
    if len(raw) >= 3 and raw[2] in ('x', 'X'):
        items.append('Execute')
    return items

def mode_string(mode, scope):
    mapping = {{
        'owner': (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
        'group': (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
        'other': (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH),
    }}
    read_bit, write_bit, execute_bit = mapping[scope]
    return (
        ('r' if mode & read_bit else '-') +
        ('w' if mode & write_bit else '-') +
        ('x' if mode & execute_bit else '-')
    )

def acl_entries(path_obj, owner, group_name, mode):
    try:
        completed = subprocess.run(['getfacl', '-cp', str(path_obj)], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        completed = None
    if completed and completed.returncode == 0:
        entries = []
        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(':')
            if len(parts) < 3:
                continue
            tag = parts[0]
            subject = parts[1] or ('Everyone' if tag == 'other' else '')
            permissions = rwx_to_permissions(parts[2])
            if permissions:
                entries.append({{'identity': subject or tag, 'permissions': permissions, 'access_type': 'Allow'}})
        if entries:
            return entries
    return [
        {{'identity': owner, 'permissions': rwx_to_permissions(mode_string(mode, 'owner')), 'access_type': 'Allow'}},
        {{'identity': group_name, 'permissions': rwx_to_permissions(mode_string(mode, 'group')), 'access_type': 'Allow'}},
        {{'identity': 'Everyone', 'permissions': rwx_to_permissions(mode_string(mode, 'other')), 'access_type': 'Allow'}},
    ]

def fingerprint(path_obj, file_stat):
    seed = (
        f"{{path_obj}}|{{file_stat.st_mode}}|{{file_stat.st_uid}}|{{file_stat.st_gid}}|{{file_stat.st_size}}|"
        f"{{getattr(file_stat, 'st_mtime_ns', int(file_stat.st_mtime * 1000000000))}}|"
        f"{{getattr(file_stat, 'st_ctime_ns', int(file_stat.st_ctime * 1000000000))}}"
    )
    return hashlib.blake2s(seed.encode('utf-8'), digest_size=8).hexdigest()

queue = collections.deque([(ROOT, 0)])
count = 0
while queue and count < MAX_ENTRIES:
    current, depth = queue.popleft()
    if not INCLUDE_HIDDEN and current.name.startswith('.') and current != ROOT:
        continue
    try:
        file_stat = current.lstat()
    except OSError as exc:
        print(f"__WARN__Stat unavailable: {{current}} :: {{exc}}")
        continue
    try:
        owner = pwd.getpwuid(file_stat.st_uid).pw_name
    except KeyError:
        owner = str(file_stat.st_uid)
    try:
        group_name = grp.getgrgid(file_stat.st_gid).gr_name
    except KeyError:
        group_name = str(file_stat.st_gid)
    current_fingerprint = fingerprint(current, file_stat)
    cached = CACHE.get(str(current))
    if cached and cached.get('fingerprint') == current_fingerprint:
        cached_payload = dict(cached.get('record') or {{}})
        cached_payload['fingerprint'] = current_fingerprint
        cached_payload['cache_hit'] = True
        print(json.dumps(cached_payload, separators=(',', ':')))
        count += 1
        if RECURSIVE and current.is_dir() and depth < MAX_DEPTH:
            try:
                with os.scandir(current) as iterator:
                    children = sorted((pathlib.Path(entry.path) for entry in iterator), key=lambda item: item.name.lower())
                for child in children:
                    queue.append((child, depth + 1))
            except OSError as exc:
                print(f"__WARN__Enumeration unavailable: {{current}} :: {{exc}}")
        continue
    print(json.dumps({{
        'path': str(current),
        'is_directory': current.is_dir(),
        'size': 0 if current.is_dir() else int(file_stat.st_size),
        'owner': owner,
        'fingerprint': current_fingerprint,
        'cache_hit': False,
        'access': [entry for entry in acl_entries(current, owner, group_name, file_stat.st_mode) if entry.get('permissions')],
    }}, separators=(',', ':')))
    count += 1
    if RECURSIVE and current.is_dir() and depth < MAX_DEPTH:
        try:
            with os.scandir(current) as iterator:
                children = sorted((pathlib.Path(entry.path) for entry in iterator), key=lambda item: item.name.lower())
            for child in children:
                queue.append((child, depth + 1))
        except OSError as exc:
            print(f"__WARN__Enumeration unavailable: {{current}} :: {{exc}}")
"""
    return script


def _exec_remote_python(client: paramiko.SSHClient, script: str) -> tuple[str, str]:
    stdin, stdout, stderr = client.exec_command("python3 -")  # nosec B601
    stdin.write(script)
    stdin.flush()
    stdin.channel.shutdown_write()
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        stdin, stdout, stderr = client.exec_command("python -")  # nosec B601
        stdin.write(script)
        stdin.flush()
        stdin.channel.shutdown_write()
        stdout.channel.recv_exit_status()
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")


def _build_snapshot(
    *,
    identities: list[IdentityRecord],
    memberships: list[MembershipRecord],
    scan_results: list[TargetScanResult],
    warnings: list[str],
    historical_metrics: list[dict[str, object]],
) -> dict[str, object]:
    host = socket.gethostname()
    operating_system = platform.system()
    environment = "on-prem"
    generated_at = utc_now_iso()

    alias_index: dict[str, str] = {}
    entities: dict[str, Entity] = {}
    relationships: dict[str, Relationship] = {}

    def stable_id(prefix: str, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:48] or prefix
        digest = hashlib.blake2s(value.encode("utf-8"), digest_size=5).hexdigest()
        return f"{prefix}_{slug}_{digest}"

    def ensure_entity(record: IdentityRecord) -> str:
        for alias in record.aliases | {record.name}:
            existing = alias_index.get(alias.lower())
            if existing:
                return existing
        current_id = stable_id("principal", record.name)
        entities[current_id] = Entity(
            id=current_id,
            name=record.name,
            kind=record.kind,
            source=f"{operating_system} Local Identity",
            environment=environment,
            description=record.description,
            criticality=4 if record.kind == "service_account" else 2,
            risk_score=65 if record.kind == "service_account" else 24,
            tags=["identity", operating_system.lower()],
        )
        for alias in record.aliases | {record.name}:
            alias_index[alias.lower()] = current_id
        return current_id

    def ensure_identity(name: str, *, kind_hint: str | None = None) -> str:
        normalized = name.strip()
        resolved = alias_index.get(normalized.lower())
        if resolved:
            return resolved
        aliases = {normalized}
        if "\\" in normalized:
            aliases.add(normalized.split("\\", 1)[1])
        return ensure_entity(
            IdentityRecord(
                name=normalized,
                kind=kind_hint or _guess_identity_kind(normalized),
                description=f"Identity discovered from live ACL analysis on {host}.",
                aliases=aliases,
            )
        )

    for identity in identities:
        ensure_entity(identity)

    for membership in memberships:
        member_id = ensure_identity(membership.member, kind_hint=membership.member_kind)
        group_id = ensure_identity(membership.group, kind_hint="group")
        relation_kind = "nested_group" if entities[member_id].kind == "group" else "member_of"
        relation_id = stable_id("rel", f"{member_id}:{group_id}:{relation_kind}")
        relationships[relation_id] = Relationship(
            id=relation_id,
            kind=relation_kind,
            source=member_id,
            target=group_id,
            label=f"{entities[member_id].name} member of {entities[group_id].name}",
            rationale="Local group membership discovered from the host identity catalog.",
            removable=_is_removable_membership(entities[member_id].name, entities[group_id].name),
            metadata={"origin": "live-identity-catalog"},
        )

    resource_by_path: dict[str, str] = {}
    broad_access_count = 0
    deny_count = 0
    privileged_acl_count = 0
    target_coverage = 0

    for result in scan_results:
        target_coverage += len(result.items)
        sorted_items = sorted(result.items, key=lambda item: (item.path.count(os.sep), item.path.lower()))
        for item in sorted_items:
            resource_id = stable_id("res", item.path)
            resource_by_path[item.path] = resource_id
            path_obj = Path(item.path)
            target_source = _resource_source_for_target(result.target, operating_system)
            target_tags = _resource_tags_for_target(result.target, operating_system)
            entities[resource_id] = Entity(
                id=resource_id,
                name=item.path,
                kind="resource",
                source=target_source,
                environment=environment,
                description=f"Live filesystem object discovered under monitored target {result.target.name}.",
                criticality=_resource_criticality(item.path, item.access_entries),
                risk_score=_resource_risk_score(item.access_entries, item.is_directory),
                tags=target_tags
                + [
                    "resource",
                    "directory" if item.is_directory else "file",
                    "remote" if _is_remote_path(item.path) else "local",
                ],
                owner=item.owner,
            )

            parent_path = str(path_obj.parent) if str(path_obj.parent) != item.path else None
            parent_id = resource_by_path.get(parent_path or "")
            if parent_id:
                contains_id = stable_id("rel", f"{parent_id}:{resource_id}:contains")
                relationships[contains_id] = Relationship(
                    id=contains_id,
                    kind="contains",
                    source=parent_id,
                    target=resource_id,
                    label=f"{Path(parent_path).name or parent_path} contains {path_obj.name or item.path}",
                    rationale="Filesystem hierarchy observed during the live crawl.",
                    metadata={"origin": "filesystem"},
                )

            for access_entry in item.access_entries:
                principal_id = ensure_identity(access_entry.identity)
                relation_kind = "deny_acl" if access_entry.access_type.lower() == "deny" else "direct_acl"
                if relation_kind == "deny_acl":
                    deny_count += 1
                if _is_privileged(access_entry.permissions):
                    privileged_acl_count += 1
                if _is_broad_access(access_entry.identity):
                    broad_access_count += 1

                relation_id = stable_id(
                    "rel",
                    f"{principal_id}:{resource_id}:{relation_kind}:{','.join(access_entry.permissions)}:{access_entry.inherited}",
                )
                relationships[relation_id] = Relationship(
                    id=relation_id,
                    kind=relation_kind,
                    source=principal_id,
                    target=resource_id,
                    label=_acl_label(access_entry, item.path),
                    rationale=(
                        "Inherited ACL entry observed directly on the filesystem object during the live scan."
                        if access_entry.inherited
                        else "Explicit ACL entry observed directly on the filesystem object during the live scan."
                    ),
                    permissions=access_entry.permissions,
                    removable=relation_kind == "direct_acl" and not _is_protected_identity(access_entry.identity),
                    metadata={
                        "origin": "filesystem",
                        "inherited": str(access_entry.inherited).lower(),
                        "target": result.target.name,
                    },
                )

    snapshot = Snapshot(
        tenant=default_workspace_name(host),
        generated_at=generated_at,
        entities=list(entities.values()),
        relationships=list(relationships.values()),
        connectors=_build_connectors(
            operating_system=operating_system,
            scan_results=scan_results,
            warnings=warnings,
            target_coverage=target_coverage,
            generated_at=generated_at,
        ),
        history=_build_history(historical_metrics, privileged_acl_count, broad_access_count),
        insights=_build_insights(
            warnings=warnings,
            broad_access_count=broad_access_count,
            deny_count=deny_count,
            enabled_target_count=len(scan_results),
            privileged_acl_count=privileged_acl_count,
        ),
    )
    return {
        "snapshot": snapshot,
        "warning_count": len(warnings),
        "privileged_path_count": privileged_acl_count,
        "broad_access_count": broad_access_count,
        "notes": warnings,
    }


def _raw_collection_payload(
    *,
    identities: list[IdentityRecord],
    memberships: list[MembershipRecord],
    scan_results: list[TargetScanResult],
    generated_at: str,
) -> dict[str, object]:
    return {
        "generated_at": generated_at,
        "host": socket.gethostname(),
        "platform": platform.system(),
        "identities": [
            {
                "name": record.name,
                "kind": record.kind,
                "description": record.description,
                "aliases": sorted(record.aliases),
            }
            for record in identities
        ],
        "memberships": [
            {
                "member": record.member,
                "group": record.group,
                "member_kind": record.member_kind,
            }
            for record in memberships
        ],
        "targets": [
            {
                "id": result.target.id,
                "name": result.target.name,
                "path": result.target.path,
                "platform": result.target.platform,
                "connection_mode": result.target.connection_mode,
                "host": result.target.host,
                "duration_ms": round(result.duration_ms, 4),
                "warnings": list(result.warnings),
                "cache_hits": result.cache_hits,
                "cache_misses": result.cache_misses,
                "items": [
                    {
                        "path": item.path,
                        "is_directory": item.is_directory,
                        "owner": item.owner,
                        "size": item.size,
                        "fingerprint": item.fingerprint,
                        "access_entries": [
                            {
                                "identity": entry.identity,
                                "permissions": list(entry.permissions),
                                "access_type": entry.access_type,
                                "inherited": entry.inherited,
                            }
                            for entry in item.access_entries
                        ],
                    }
                    for item in result.items
                ],
            }
            for result in scan_results
        ],
    }


def _build_connectors(
    *,
    operating_system: str,
    scan_results: list[TargetScanResult],
    warnings: list[str],
    target_coverage: int,
    generated_at: str,
) -> list[ConnectorStatus]:
    total_latency = int(sum(result.duration_ms for result in scan_results))
    return [
        ConnectorStatus(
            name="Local Identity Collector",
            source=f"{operating_system} host",
            status="healthy",
            latency_ms=max(1, total_latency // max(len(scan_results), 1)),
            last_sync=generated_at,
            coverage="Local users, groups and membership catalog",
        ),
        ConnectorStatus(
            name="Filesystem ACL Collector",
            source=f"{operating_system} filesystem",
            status="warning" if warnings else "healthy",
            latency_ms=max(1, total_latency),
            last_sync=generated_at,
            coverage=f"{len(scan_results)} target(s), {target_coverage} filesystem objects materialized",
        ),
        ConnectorStatus(
            name="Access Graph Cache",
            source="Runtime engine",
            status="healthy" if scan_results else "degraded",
            latency_ms=max(1, total_latency // max(len(scan_results), 1) if scan_results else 1),
            last_sync=generated_at,
            coverage="Explainable paths cached from the latest live snapshot",
        ),
    ]


def _build_history(
    historical_metrics: list[dict[str, object]],
    privileged_acl_count: int,
    broad_access_count: int,
) -> list[HistoricalPoint]:
    day_buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"privileged": 0, "broad": 0, "scans": 0})
    for metric in historical_metrics:
        day = str(metric["started_at"])[:10]
        day_buckets[day]["privileged"] += int(metric["privileged_path_count"])
        day_buckets[day]["broad"] += int(metric["broad_access_count"])
        day_buckets[day]["scans"] += 1

    if not day_buckets:
        today = utc_now_iso()[:10]
        day_buckets[today]["privileged"] = privileged_acl_count
        day_buckets[today]["broad"] = broad_access_count
        day_buckets[today]["scans"] = 1

    points = [
        HistoricalPoint(
            day=day,
            privileged_paths=bucket["privileged"],
            dormant_entitlements=bucket["broad"],
            change_requests=bucket["scans"],
        )
        for day, bucket in sorted(day_buckets.items())
    ]
    return points[-7:]


def _build_insights(
    *,
    warnings: list[str],
    broad_access_count: int,
    deny_count: int,
    enabled_target_count: int,
    privileged_acl_count: int,
) -> list[InsightNote]:
    notes: list[InsightNote] = []
    if enabled_target_count == 0:
        notes.append(
            InsightNote(
                title="No monitored targets enabled",
                body="Add at least one filesystem target to materialize live permissions.",
                tone="warn",
            )
        )
    if warnings:
        notes.append(
            InsightNote(
                title="Some paths could not be scanned cleanly",
                body=f"{len(warnings)} enumeration or ACL warnings were captured during the last crawl.",
                tone="warn",
            )
        )
    if broad_access_count:
        notes.append(
            InsightNote(
                title="Broad principals are present on the monitored scope",
                body=f"{broad_access_count} ACL entries involve broad groups such as Users or Authenticated Users.",
                tone="critical" if broad_access_count >= 5 else "warn",
            )
        )
    if deny_count:
        notes.append(
            InsightNote(
                title="Deny ACL entries detected",
                body="Effective access explanations now account for deny entries found on scanned filesystem objects.",
                tone="neutral",
            )
        )
    if privileged_acl_count:
        notes.append(
            InsightNote(
                title="Privileged filesystem rights observed",
                body=f"{privileged_acl_count} ACL entries include write, modify or stronger permissions.",
                tone="warn" if privileged_acl_count < 10 else "critical",
            )
        )
    if not notes:
        notes.append(
            InsightNote(
                title="Live host baseline is healthy",
                body="The latest crawl completed without warnings and no broad or privileged exposures stood out immediately.",
                tone="good",
            )
        )
    return notes[:4]


def _guess_identity_kind(name: str) -> str:
    lowered = name.lower()
    if any(marker in lowered for marker in SERVICE_MARKERS):
        return "service_account"
    if any(marker in lowered for marker in WINDOWS_BUILTIN_GROUPS) or lowered.endswith("users"):
        return "group"
    if lowered.endswith("$") or lowered.startswith("svc"):
        return "service_account"
    return "user"


def _is_removable_membership(member_name: str, group_name: str) -> bool:
    protected_terms = ("system", "administrators", "users", "authenticated users")
    lowered = f"{member_name} {group_name}".lower()
    return not any(term in lowered for term in protected_terms)


def _is_protected_identity(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("system", "administrators", "trustedinstaller", "authenticated users"))


def _resource_criticality(path: str, access_entries: list[AccessEntry]) -> int:
    score = 2
    lowered = path.lower()
    if any(keyword in lowered for keyword in ("windows", "program files", "users", "secrets", "ssh")):
        score += 1
    if _is_privileged_permissions_flat(access_entries):
        score += 1
    if _is_remote_path(path):
        score += 1
    return min(5, score)


def _resource_risk_score(access_entries: list[AccessEntry], is_directory: bool) -> int:
    base = 22 if is_directory else 14
    if _is_privileged_permissions_flat(access_entries):
        base += 32
    broad_matches = sum(1 for entry in access_entries if _is_broad_access(entry.identity))
    base += min(25, broad_matches * 8)
    if any(entry.access_type.lower() == "deny" for entry in access_entries):
        base += 6
    return min(96, base)


def _is_privileged(permissions: list[str]) -> bool:
    return any(any(marker in permission.lower() for marker in PRIVILEGED_PERMISSION_MARKERS) for permission in permissions)


def _is_privileged_permissions_flat(access_entries: list[AccessEntry]) -> bool:
    return any(_is_privileged(entry.permissions) for entry in access_entries)


def _is_broad_access(identity_name: str) -> bool:
    lowered = identity_name.lower()
    return any(marker in lowered for marker in BROAD_ACCESS_MARKERS)


def _is_remote_path(path_value: str) -> bool:
    return path_value.startswith("\\\\") or path_value.startswith("//")


def _resource_source_for_target(target: ScanTarget, operating_system: str) -> str:
    if target.connection_mode == "ssh":
        location = target.host or "SSH target"
        return f"{location} Linux Filesystem"
    platform_hint = target.platform if target.platform != "auto" else operating_system.lower()
    return f"{platform_hint.capitalize()} Filesystem"


def _resource_tags_for_target(target: ScanTarget, operating_system: str) -> list[str]:
    if target.connection_mode == "ssh":
        return ["linux", "ssh"]
    platform_hint = target.platform if target.platform != "auto" else operating_system.lower()
    return [platform_hint]


def _acl_label(access_entry: AccessEntry, path_value: str) -> str:
    mode = "Deny" if access_entry.access_type.lower() == "deny" else "Allow"
    target_name = Path(path_value).name or path_value
    return f"{mode} {', '.join(access_entry.permissions)} on {target_name}"


def _run_powershell_json_lines(script: str) -> list[dict[str, object]]:
    rows, _ = _run_powershell_structured(script)
    return rows


def _run_powershell_structured(script: str) -> tuple[list[dict[str, object]], list[str]]:
    powershell_binary = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell_binary:
        return [], ["PowerShell is not available on this host."]
    completed = subprocess.run(
        [powershell_binary, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )  # nosec B603
    warnings: list[str] = []
    rows: list[dict[str, object]] = []

    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("__WARN__"):
            warnings.append(line.replace("__WARN__", "", 1).strip())
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            warnings.append(f"Collector output could not be parsed: {line[:180]}")

    stderr = completed.stderr.strip()
    if stderr:
        warnings.append(stderr)
    return rows, warnings
