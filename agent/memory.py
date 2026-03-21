"""Agent memory — persistent key-value store per agent instance.

This is the L2 cache for agents: conversation-level context lives in
the Claude API's message history (L1), but cross-conversation preferences
and learned behaviors are stored here (L2) and injected into context.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemory


async def get_memory(db: AsyncSession, agent_type: str, user_id: str, key: str) -> dict | None:
    result = await db.execute(
        select(AgentMemory).where(
            AgentMemory.agent_type == agent_type,
            AgentMemory.user_id == user_id,
            AgentMemory.key == key,
        )
    )
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_memory(db: AsyncSession, agent_type: str, user_id: str, key: str, value: dict):
    existing = await db.execute(
        select(AgentMemory).where(
            AgentMemory.agent_type == agent_type,
            AgentMemory.user_id == user_id,
            AgentMemory.key == key,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AgentMemory(agent_type=agent_type, user_id=user_id, key=key, value=value))
    await db.commit()
