from app.actions.schemas import ActionProposal
from app.tools.registry import build_default_tools


def test_action_tools_are_explicitly_classified_and_proposal_only(database_path):
    tools = build_default_tools(database_path)

    assert tools["get_service_health"].kind == "read"
    assert tools["search_runbooks"].kind == "read"
    assert tools["propose_action"].kind == "write"

    proposal = tools["propose_action"].run(
        {
            "action_type": "rollback_deployment",
            "target": "payments-api@2026.10.07.14",
            "reason": "Recent deployment correlates with elevated latency.",
            "evidence": [{"tool": "get_metrics", "metric": "http_request_latency_ms"}],
        }
    )

    assert isinstance(proposal, ActionProposal)
    assert proposal.risk_level == "high"
    assert proposal.status == "proposed"