"""Base agent class — the abstract interface all agents implement.

Architecture analogy: this is like the syscall interface in an OS.
Every agent (Buyer, Seller, Broker) inherits this and registers
its own tools and system prompt, but the message loop is standardized.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

import anthropic

from agent.tool_acl import AgentRole, filter_tools_for_role, validate_tool_access
from agent.tool_registry import ToolRegistry


class BaseAgent(ABC):
    """Abstract base for all production agents."""

    def __init__(self, client: anthropic.AsyncAnthropic, role: AgentRole | None = None):
        self.client = client
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 4096
        self.role = role
        self.tool_registry = ToolRegistry()
        self._services: dict[str, Any] = {}

    def set_services(self, **services: Any) -> None:
        """Inject service dependencies (db, event_store, maps, market_data)."""
        self._services = services

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the agent's system prompt."""
        ...

    @abstractmethod
    def tools(self) -> list[dict]:
        """Return the agent's tool definitions."""
        ...

    def filtered_tools(self) -> list[dict]:
        """Return tools filtered by role ACL."""
        if self.role:
            return filter_tools_for_role(self.role, self.tools())
        return self.tools()

    async def process_message(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Run one turn of the agent's conversation loop.

        Implements a tool-use loop: when Claude returns stop_reason="tool_use",
        we execute the tools, send results back, and re-call Claude until it
        produces a text response (stop_reason != "tool_use").
        """
        messages = list(conversation_history or [])
        messages.append({"role": "user", "content": message})

        system = self.system_prompt()
        if context:
            system += f"\n\n<context>\n{json.dumps(context, indent=2)}\n</context>"

        text_parts: list[str] = []
        tool_calls: list[dict] = []
        max_tool_rounds = 10  # Safety limit to prevent infinite loops

        for _ in range(max_tool_rounds):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=self.filtered_tools(),
                messages=messages,
            )

            # Collect text and tool_use blocks from this response
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    # Post-validate tool access
                    if self.role and not validate_tool_access(self.role, block.name):
                        result = {"error": f"Tool '{block.name}' not permitted for role '{self.role.value}'"}
                        tool_calls.append({
                            "tool": block.name,
                            "input": block.input,
                            "output": result,
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                        continue

                    tool_result = await self.execute_tool(block.name, block.input)
                    tool_calls.append({
                        "tool": block.name,
                        "input": block.input,
                        "output": tool_result,
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result,
                    })

            # If Claude didn't request any tools, we're done
            if response.stop_reason != "tool_use":
                break

            # Append assistant message and tool results, then loop
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        return {
            "response": "\n".join(text_parts),
            "tool_calls": tool_calls,
            "stop_reason": response.stop_reason,
        }

    async def execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool call by dispatching to the tool registry."""
        if self.tool_registry.has(tool_name):
            # Inject service dependencies into tool kwargs
            return await self.tool_registry.execute(tool_name, **tool_input, **self._services)
        return {"error": f"Tool '{tool_name}' not implemented"}
