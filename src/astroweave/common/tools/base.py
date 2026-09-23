from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from functools import update_wrapper
from typing import Any, ParamSpec, TypeVar, overload

from pydantic import BaseModel, ConfigDict


class BaseToolReturnType(BaseModel):
    success: bool
    error: str | None = None


class ToolType(str, Enum):
    FUNCTION = "function"


ToolResponseType = type[BaseToolReturnType]


class ToolMetadata(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    type: ToolType = ToolType.FUNCTION
    returns: ToolResponseType


class BaseTool(ABC):
    """Base contract for actions exposed to an agent."""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        raise NotImplementedError

    @abstractmethod
    def invoke(self, *args: Any, **kwargs: Any) -> BaseToolReturnType:
        raise NotImplementedError


Parameters = ParamSpec("Parameters")
ReturnType = TypeVar("ReturnType", bound=BaseToolReturnType)


class FunctionTool(BaseTool):
    def __init__(
        self,
        function: Callable[..., BaseToolReturnType],
        metadata: ToolMetadata,
    ) -> None:
        self._function = function
        self._metadata = metadata
        update_wrapper(self, function)

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    @property
    def signature(self) -> inspect.Signature:
        return inspect.signature(self._function)

    def invoke(self, *args: Any, **kwargs: Any) -> BaseToolReturnType:
        result = self._function(*args, **kwargs)
        if not isinstance(result, self.metadata.returns):
            raise TypeError(
                f"Tool '{self.metadata.name}' must return "
                f"{self.metadata.returns.__name__}, got {type(result).__name__}"
            )
        return result

    def __call__(self, *args: Any, **kwargs: Any) -> BaseToolReturnType:
        return self.invoke(*args, **kwargs)


@overload
def tool(
    *,
    description: str,
    name: str | None = None,
    returns: type[ReturnType] = BaseToolReturnType,
) -> Callable[[Callable[Parameters, ReturnType]], FunctionTool]: ...


def tool(
    *,
    description: str,
    name: str | None = None,
    returns: type[BaseToolReturnType] = BaseToolReturnType,
) -> Callable[[Callable[..., BaseToolReturnType]], FunctionTool]:
    """Create a tool from a function that returns a tool response model."""

    def decorator(function: Callable[..., BaseToolReturnType]) -> FunctionTool:
        return FunctionTool(
            function,
            ToolMetadata(
                name=name or function.__name__,
                description=description,
                returns=returns,
            ),
        )

    return decorator