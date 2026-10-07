from app.core.config import settings
from app.db.simulator import SimulatorRepository
from app.rag.repository import KnowledgeRepository
from app.tools.base import Tool
from app.tools.actions import ProposeAction
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
    knowledge_repository = KnowledgeRepository(database_url)
    tools = [
        GetServiceHealth(repository),
        GetMetrics(repository),
        SearchLogs(repository),
        GetRecentDeployments(repository),
        GetIncidentHistory(repository),
        SearchRunbooks(knowledge_repository),
        ProposeAction(),
    ]
    return {tool.name: tool for tool in tools}