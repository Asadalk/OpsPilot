from app.core.config import settings
from app.core.customer import DEFAULT_CUSTOMER, CustomerConfig
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


def build_default_tools(database_url: str = settings.database_url,
                        customer: CustomerConfig = DEFAULT_CUSTOMER) -> dict[str, Tool]:
    repository = SimulatorRepository(database_url)
    knowledge_repository = KnowledgeRepository(database_url)
    tools = [
        GetServiceHealth(repository, customer),
        GetMetrics(repository, customer),
        SearchLogs(repository, customer),
        GetRecentDeployments(repository, customer),
        GetIncidentHistory(repository, customer),
        SearchRunbooks(knowledge_repository),
        ProposeAction(),
    ]
    return {tool.name: tool for tool in tools}