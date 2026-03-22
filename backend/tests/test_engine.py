from app.demo_data import build_demo_snapshot
from app.engine import AccessGraphEngine
from app.models import Entity, Relationship


def test_alice_inherits_modify_on_payroll_folder_via_nested_group() -> None:
    engine = AccessGraphEngine(build_demo_snapshot())

    explanation = engine.explain("user_alice", "res_folder_payroll")

    assert explanation.permissions == ["Delete", "Read", "Write"]
    assert explanation.path_count >= 1
    first_path = explanation.paths[0]
    step_labels = [step.label for step in first_path.steps]
    assert "Finance Analysts nested into Payroll Editors" in step_labels
    assert "Modify on Finance Share and descendants" in step_labels


def test_omar_has_delegated_payroll_access() -> None:
    engine = AccessGraphEngine(build_demo_snapshot())

    explanation = engine.explain("user_omar", "res_folder_payroll")

    assert any(path.access_mode == "Delegated" for path in explanation.paths)
    assert any(
        step.edge_kind == "delegated_access"
        for path in explanation.paths
        for step in path.steps
    )


def test_simulation_removing_nested_group_impacts_alice() -> None:
    engine = AccessGraphEngine(build_demo_snapshot())

    simulation = engine.simulate_edge_removal("rel_finance_into_payroll_editors")

    impacted_principals = {item.principal.id for item in simulation.diff}
    impacted_resources = {item.resource.id for item in simulation.diff}

    assert "user_alice" in impacted_principals
    assert "res_folder_payroll" in impacted_resources
    assert simulation.impacted_principals >= 1
    assert simulation.removed_paths >= 1
    assert simulation.recomputed_principals >= simulation.impacted_principals
    assert simulation.recomputed_resources >= simulation.impacted_resources


def test_materialized_access_index_includes_path_complexity() -> None:
    engine = AccessGraphEngine(build_demo_snapshot())

    rows = engine.materialized_access_index()

    assert rows
    assert all(int(row["path_complexity"]) >= 1 for row in rows)


def test_identity_clusters_link_same_user_across_sources() -> None:
    snapshot = build_demo_snapshot()
    graph_entity = Entity(
        id="user_alice_graph",
        name="alice.wong@contoso.com",
        kind="user",
        source="Microsoft Graph",
        environment="cloud",
        description="Cloud identity for Alice Wong.",
        criticality=2,
        risk_score=42,
        tags=["graph", "entra", "user"],
    )
    graph_relationship = Relationship(
        id="rel_alice_graph_payroll",
        kind="direct_acl",
        source="user_alice_graph",
        target="res_folder_payroll",
        label="Read on Payroll Folder",
        rationale="Cloud grant discovered through the identity directory.",
        permissions=["Read"],
        removable=True,
    )
    engine = AccessGraphEngine(
        snapshot.model_copy(
            update={
                "entities": snapshot.entities + [graph_entity],
                "relationships": snapshot.relationships + [graph_relationship],
            }
        )
    )

    clusters = engine.identity_clusters()

    assert clusters.total_clusters >= 1
    alice_cluster = next(
        cluster for cluster in clusters.clusters if "Alice" in cluster.display_name or "alice" in cluster.display_name
    )
    detail = engine.identity_cluster_detail(alice_cluster.id)

    member_ids = {member.entity.id for member in detail.members}
    assert "user_alice" in member_ids
    assert "user_alice_graph" in member_ids
    assert any(resource.resource.id == "res_folder_payroll" for resource in detail.top_resources)


def test_explain_prefers_more_readable_direct_path_over_riskier_delegated_path() -> None:
    snapshot = build_demo_snapshot()
    snapshot = snapshot.model_copy(
        update={
            "relationships": snapshot.relationships
            + [
                Relationship(
                    id="rel_alice_direct_payroll",
                    kind="direct_acl",
                    source="user_alice",
                    target="res_folder_payroll",
                    label="Direct Read on Payroll Folder",
                    rationale="Direct grant added for readability ranking validation.",
                    permissions=["Read"],
                    removable=True,
                ),
                Relationship(
                    id="rel_alice_delegate_payroll",
                    kind="delegated_access",
                    source="user_alice",
                    target="group_payroll_editors",
                    label="Alice delegated into Payroll Editors",
                    rationale="Delegated path added for explain ranking validation.",
                    removable=True,
                ),
            ]
        }
    )
    engine = AccessGraphEngine(snapshot)

    explanation = engine.explain("user_alice", "res_folder_payroll")

    assert explanation.path_count >= 2
    first_path = explanation.paths[0]
    assert first_path.access_mode == "Direct"
    assert first_path.steps[0].label == "Direct Read on Payroll Folder"
