from app.core.config import settings
from app.db.simulator import SimulatorRepository
from app.tools.base import Tool
from app.tools.operational import (
    GetIncidentHistory,
    GetMetrics,
    GetRecentDeployments,
    GetServiceHealth,
    SearchLogs,
    SearchRunbooks,
)


def build_default_tools(database_url: str = settings.database_url) -> dict[str, Tool]:
    repository = SimulatorRepository(database_url)
    tools = [
        GetServiceHealth(repository),
        GetMetrics(repository),
        SearchLogs(repository),
        GetRecentDeployments(repository),
        GetIncidentHistory(repository),
        SearchRunbooks(),
    ]
    return {tool.name: tool for tool in tools}