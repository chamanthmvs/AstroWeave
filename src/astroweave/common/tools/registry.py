from __future__ import annotations

from collections.abc import Iterable, Iterator

from .base import BaseTool, ToolMetadata


class ToolRegistry:
    """Collection of tools available to one agent."""

    def __init__(self, tools: Iterable[BaseTool] = ()) -> None:
        self._tools: dict[str, BaseTool] = {}
        for registered_tool in tools:
            self.register(registered_tool)

    def register(self, registered_tool: BaseTool) -> BaseTool:
        name = registered_tool.metadata.name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        self._tools[name] = registered_tool
        return registered_tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def require(self, name: str) -> BaseTool:
        registered_tool = self.get(name)
        if registered_tool is None:
            raise KeyError(f"Unknown tool '{name}'")
        return registered_tool

    def metadata(self) -> list[ToolMetadata]:
        return [registered_tool.metadata for registered_tool in self._tools.values()]

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __iter__(self) -> Iterator[BaseTool]:
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)