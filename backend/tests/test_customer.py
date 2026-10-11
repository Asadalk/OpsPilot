"""Phase 29: two customer configurations, one unchanged agent."""
import asyncio
from pathlib import Path

import pytest

from app.actions.schemas import ActionProposal
from app.agent.agent import build_agent
from app.agent.scripted import MockDecisionProvider
from app.auth.schemas import UserPrincipal
from app.core.customer import CustomerConfigError, load_customer_config
from app.db.database import init_db
from app.policy.engine import PolicyEngine
from app.tools.base import ToolExecutionError
from app.tools.registry import build_default_tools

CUSTOMERS = Path(__file__).resolve().parents[1] / "config" / "customers"
ACME = load_customer_config(CUSTOMERS / "acme-payments.toml")
GLOBEX = load_customer_config(CUSTOMERS / "globex-retail.toml")
ADMIN = UserPrincipal(username="a", role="admin")
OPERATOR = UserPrincipal(username="o", role="operator")


def proposal(action: str, target: str) -> ActionProposal:
    return ActionProposal(action_type=action, target=target, reason="customer test", evidence=[],
                          risk_level="LOW", status="proposed")


def test_example_configs_load():
    assert (ACME.name, GLOBEX.name) == ("Acme Payments", "Globex Retail")
    assert ACME.manages("payments-api") and not GLOBEX.manages("payments-api")
    assert load_customer_config(None).manages("anything")  # no config: whole simulator


def test_unknown_settings_are_rejected(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('[customer]\nname = "X"\n[policies]\nskip_approval = true\n')
    with pytest.raises(CustomerConfigError):
        load_customer_config(bad)


def test_same_policy_engine_applies_each_customers_rules():
    restart = proposal("restart_service", "checkout-api")
    assert PolicyEngine(ACME).evaluate(restart, ADMIN, "production").outcome == "require_approval"
    assert PolicyEngine(GLOBEX).evaluate(restart, ADMIN, "production").outcome == "allow"
    issue = proposal("create_github_issue", "checkout-api")
    assert PolicyEngine(ACME).evaluate(issue, OPERATOR, "production").outcome == "allow"
    assert PolicyEngine(GLOBEX).evaluate(issue, OPERATOR, "production").outcome == "deny"
    assert PolicyEngine(ACME).evaluate(proposal("restart_service", "inventory-api"), ADMIN, "staging").outcome == "deny"


def test_tools_refuse_services_outside_the_customer_scope(database_path):
    init_db(database_path)
    assert build_default_tools(database_path, ACME)["get_service_health"].run({"service": "payments-api"}).name == "payments-api"
    with pytest.raises(ToolExecutionError, match="not managed for customer Globex Retail"):
        build_default_tools(database_path, GLOBEX)["get_service_health"].run({"service": "payments-api"})


def test_same_agent_code_runs_under_both_customers(database_path):
    init_db(database_path)
    request = "payments-api latency is high. Investigate."
    states = {}
    for customer in (ACME, GLOBEX):
        agent = build_agent(database_path, MockDecisionProvider(), customer)
        states[customer.name] = asyncio.run(agent.investigate(request, OPERATOR))
    acme, globex = states["Acme Payments"], states["Globex Retail"]
    assert acme.tool_calls and all(call.success for call in acme.tool_calls)
    assert globex.tool_calls and not any(call.success for call in globex.tool_calls)
    assert globex.status == "failed" and globex.approval is None  # out of scope: escalated, nothing runs
