from abc import ABC, abstractmethod
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError

InputModel = TypeVar("InputModel", bound=BaseModel)
ResultModel = TypeVar("ResultModel", bound=BaseModel)
ToolKind = Literal["read", "write"]


class ToolError(Exception):
    """Base error for deterministic tool execution."""


class ToolInputError(ToolError):
    pass


class ToolExecutionError(ToolError):
    pass


class ToolResultError(ToolError):
    """A tool returned a value that violates its declared output schema."""


class Tool(Generic[InputModel, ResultModel], ABC):
    name: str
    description: str
    input_schema: type[InputModel]
    result_schema: type[ResultModel]
    kind: ToolKind = "read"

    def run(self, payload: dict[str, Any] | InputModel) -> ResultModel:
        try:
            parameters = payload if isinstance(payload, self.input_schema) else self.input_schema.model_validate(payload)
        except ValidationError as exc:
            raise ToolInputError(str(exc)) from exc
        try:
            result = self.execute(parameters)
            try:
                return self.result_schema.model_validate(result)
            except ValidationError as exc:
                raise ToolResultError(f"{self.name} returned malformed structured data") from exc
        except ToolError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"{self.name} failed") from exc

    @abstractmethod
    def execute(self, parameters: InputModel) -> ResultModel:
        raise NotImplementedError
