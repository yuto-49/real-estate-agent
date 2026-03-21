"""Tool Registry — maps tool names to async handler functions."""

from typing import Any, Callable, Awaitable


class ToolRegistry:
    """Central registry mapping tool names to their async handler functions."""

    def __init__(self):
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(self, name: str, handler: Callable[..., Awaitable[Any]]) -> None:
        self._handlers[name] = handler

    def get(self, name: str) -> Callable[..., Awaitable[Any]] | None:
        return self._handlers.get(name)

    async def execute(self, name: str, **kwargs) -> Any:
        handler = self._handlers.get(name)
        if not handler:
            raise ValueError(f"No handler registered for tool '{name}'")
        return await handler(**kwargs)

    @property
    def tool_names(self) -> list[str]:
        return list(self._handlers.keys())

    def has(self, name: str) -> bool:
        return name in self._handlers
