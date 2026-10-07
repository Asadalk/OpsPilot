from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

InputModel = TypeVar("InputModel", bound=BaseModel)
ResultModel = TypeVar("ResultModel", bound=BaseModel)


class ToolError(Exception):
    """Base error for deterministic tool execution."""


class ToolInputError(ToolError):
    pass


class ToolExecutionError(ToolError):
    pass


class Tool(Generic[InputModel, ResultModel], ABC):
    name: str
    description: str
    input_schema: type[InputModel]
    result_schema: type[ResultModel]

    def run(self, payload: dict[str, Any] | InputModel) -> ResultModel:
        try:
            parameters = payload if isinstance(payload, self.input_schema) else self.input_schema.model_validate(payload)
        except ValidationError as exc:
            raise ToolInputError(str(exc)) from exc
        try:
            result = self.execute(parameters)
            return self.result_schema.model_validate(result)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"{self.name} failed") from exc

    @abstractmethod
    def execute(self, parameters: InputModel) -> ResultModel:
        raise NotImplementedError