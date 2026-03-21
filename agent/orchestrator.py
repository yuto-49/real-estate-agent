"""Agent Orchestrator — routes messages and manages inter-agent communication.

Architecture analogy: This is the kernel scheduler. It decides which
agent (process) gets the CPU (Claude API call) based on the user's
role and the current negotiation state.
"""

from datetime import datetime
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from agent.buyer_agent import BuyerAgent
from agent.seller_agent import SellerAgent
from agent.broker_agent import BrokerAgent
from agent.assistant_agent import AssistantAgent
from agent.negotiation import NegotiationTimer
from db.models import Negotiation as NegotiationModel, NegotiationStatus, MiroFishReport
from middleware.correlation import get_correlation_id
from services.event_store import EventStore
from services.maps import MapsService
from services.market_data import MarketDataService
from services.pubsub import EventBus


class AgentOrchestrator:
    def __init__(
        self,
        db: AsyncSession,
        event_bus: EventBus | None = None,
        client: anthropic.AsyncAnthropic | None = None,
        maps: MapsService | None = None,
        market_data: MarketDataService | None = None,
    ):
        self.db = db
        self.event_bus = event_bus
        self.client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.agents = {
            "buyer": BuyerAgent(self.client),
            "seller": SellerAgent(self.client),
            "broker": BrokerAgent(self.client),
            "assistant": AssistantAgent(self.client),
        }
        self.event_store = EventStore(db)

        # Inject service dependencies into all agents
        services = {
            "db": db,
            "event_store": self.event_store,
        }
        if maps:
            services["maps"] = maps
        if market_data:
            services["market_data"] = market_data
        for agent in self.agents.values():
            agent.set_services(**services)

    async def route_message(
        self, user_id: str, role: str, message: str, report_id: str | None = None,
    ) -> dict:
        """Route a message to the appropriate agent based on user role."""
        agent = self.agents.get(role)
        if not agent:
            return {"error": f"Unknown role: {role}"}

        correlation_id = get_correlation_id()
        context = await self._get_negotiation_context(user_id, report_id=report_id)
        context["correlation_id"] = correlation_id

        # Record the request as a domain event
        await self.event_store.append(
            event_type="agent.message_received",
            aggregate_type="agent",
            aggregate_id=f"{role}:{user_id}",
            payload={"message": message[:500], "role": role},
            actor_type="user",
            actor_id=user_id,
            correlation_id=correlation_id,
        )

        result = await agent.process_message(message, context)

        # Record the response
        await self.event_store.append(
            event_type="agent.response_sent",
            aggregate_type="agent",
            aggregate_id=f"{role}:{user_id}",
            payload={
                "response": result.get("response", "")[:500],
                "tool_calls": [tc["tool"] for tc in result.get("tool_calls", [])],
            },
            actor_type="agent",
            actor_id=role,
            correlation_id=correlation_id,
        )

        # Publish via event bus if available
        if self.event_bus:
            await self.event_bus.publish_agent_event(
                agent_type=role,
                user_id=user_id,
                event_type="agent.response",
                payload={"response": result.get("response", "")[:200]},
            )

        await self.db.commit()
        return result

    async def start_negotiation(
        self, property_id: str, buyer_id: str, seller_id: str
    ) -> NegotiationModel:
        """Initialize a new negotiation session backed by the database."""
        correlation_id = get_correlation_id()
        now = datetime.utcnow()

        negotiation = NegotiationModel(
            property_id=property_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            status=NegotiationStatus.IDLE,
            correlation_id=correlation_id,
            state_entered_at=now,
        )
        self.db.add(negotiation)
        await self.db.flush()

        # Calculate deadline
        deadline = NegotiationTimer.get_deadline(
            NegotiationStatus.IDLE, now
        )
        if deadline:
            negotiation.deadline_at = deadline

        await self.event_store.append(
            event_type="negotiation.started",
            aggregate_type="negotiation",
            aggregate_id=negotiation.id,
            payload={
                "property_id": property_id,
                "buyer_id": buyer_id,
                "seller_id": seller_id,
            },
            actor_type="system",
            correlation_id=correlation_id,
        )

        if self.event_bus:
            await self.event_bus.publish_negotiation_event(
                negotiation.id,
                "negotiation.started",
                {"property_id": property_id},
            )

        await self.db.commit()
        return negotiation

    async def _get_negotiation_context(
        self, user_id: str, report_id: str | None = None,
    ) -> dict[str, Any]:
        """Build context dict for the agent from active negotiations and intelligence reports."""
        result = await self.db.execute(
            select(NegotiationModel).where(
                (NegotiationModel.buyer_id == user_id)
                | (NegotiationModel.seller_id == user_id),
                NegotiationModel.status.notin_([
                    NegotiationStatus.CLOSED,
                    NegotiationStatus.WITHDRAWN,
                    NegotiationStatus.REJECTED,
                ]),
            )
        )
        negotiations = list(result.scalars().all())

        # Fetch specific or latest completed intelligence report
        if report_id:
            report_result = await self.db.execute(
                select(MiroFishReport).where(
                    MiroFishReport.id == report_id,
                    MiroFishReport.status == "completed",
                )
            )
        else:
            report_result = await self.db.execute(
                select(MiroFishReport)
                .where(
                    MiroFishReport.user_id == user_id,
                    MiroFishReport.status == "completed",
                )
                .order_by(MiroFishReport.created_at.desc())
                .limit(1)
            )
        latest_report = report_result.scalar_one_or_none()

        context: dict[str, Any] = {
            "active_negotiations": [
                {
                    "id": n.id,
                    "property_id": n.property_id,
                    "status": n.status.value if hasattr(n.status, "value") else str(n.status),
                    "round": n.round_count,
                    "deadline_at": n.deadline_at.isoformat() if n.deadline_at else None,
                }
                for n in negotiations
            ]
        }

        # Inject intelligence report insights if available
        if latest_report and latest_report.report_json:
            rj = latest_report.report_json
            context["intelligence_report"] = {
                "report_id": latest_report.id,
                "generated_at": latest_report.created_at.isoformat() if latest_report.created_at else None,
                "market_outlook": rj.get("market_outlook"),
                "timing_recommendation": rj.get("timing_recommendation"),
                "strategy_comparison": rj.get("strategy_comparison"),
                "risk_assessment": rj.get("risk_assessment"),
                "property_recommendations": rj.get("property_recommendations"),
                "decision_anchors": rj.get("decision_anchors"),
                # Deep financial analysis sections
                "financial_analysis": rj.get("financial_analysis"),
                "monte_carlo_results": rj.get("monte_carlo_results"),
                "cash_flow_projections": rj.get("cash_flow_projections"),
                "rent_vs_buy_analysis": rj.get("rent_vs_buy_analysis"),
                "tax_benefit_estimation": rj.get("tax_benefit_estimation"),
                "portfolio_metrics": rj.get("portfolio_metrics"),
                "comparable_sales_analysis": rj.get("comparable_sales_analysis"),
                "neighborhood_scoring": rj.get("neighborhood_scoring"),
            }

        return context
