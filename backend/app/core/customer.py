"""Customer-specific configuration: same OpsPilot code, different deployment settings.

A customer file (TOML, read with the standard library) names the customer, lists the
services OpsPilot may investigate and act on, switches integrations on or off, and
tightens policy. It is enforced in the deterministic layers (tools and policy engine);
the agent loop and prompt are unchanged.

Without CUSTOMER_CONFIG, OpsPilot runs unrestricted against the whole simulator.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ALLOWED_KEYS = {
    "customer": {"name"},
    "services": {"managed"},
    "integrations": {"github"},
    "policies": {"production_restart_requires_approval"},
}


class CustomerConfigError(ValueError):
    pass


@dataclass(frozen=True)
class CustomerConfig:
    name: str = "Simulator"
    managed_services: frozenset[str] | None = None  # None: every simulator service
    github_enabled: bool = True
    production_restart_requires_approval: bool = False

    def manages(self, service: str) -> bool:
        return self.managed_services is None or service in self.managed_services


DEFAULT_CUSTOMER = CustomerConfig()


def load_customer_config(path: str | Path | None) -> CustomerConfig:
    if not path:
        return DEFAULT_CUSTOMER
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CustomerConfigError(f"Cannot read customer config {path}: {exc}") from exc
    for section, values in data.items():
        if section not in ALLOWED_KEYS or not isinstance(values, dict) or set(values) - ALLOWED_KEYS[section]:
            raise CustomerConfigError(f"Unknown setting in {path}: [{section}] {sorted(values) if isinstance(values, dict) else ''}")
    name = data.get("customer", {}).get("name")
    if not isinstance(name, str) or not name.strip():
        raise CustomerConfigError(f"{path}: [customer] name is required")
    managed = data.get("services", {}).get("managed")
    if managed is not None and (not isinstance(managed, list) or not all(isinstance(item, str) for item in managed)):
        raise CustomerConfigError(f"{path}: [services] managed must be a list of service names")
    return CustomerConfig(
        name=name.strip(),
        managed_services=frozenset(managed) if managed is not None else None,
        github_enabled=bool(data.get("integrations", {}).get("github", True)),
        production_restart_requires_approval=bool(
            data.get("policies", {}).get("production_restart_requires_approval", False)),
    )
