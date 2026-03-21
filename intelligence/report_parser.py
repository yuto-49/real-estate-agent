"""Report Parser — transforms raw MiroFish ReportAgent JSON into structured sections."""

from intelligence.mirofish_client import MiroFishReportData


def parse_report_for_display(report: MiroFishReportData) -> dict:
    """Transform MiroFish output into the Intelligence Report structure from Section 5.5.1."""
    return {
        "sections": [
            {
                "id": "market_outlook",
                "title": "Market Outlook",
                "content": report.market_outlook,
                "expandable": True,
            },
            {
                "id": "timing",
                "title": "Timing Recommendation",
                "content": report.timing_recommendation,
                "expandable": True,
            },
            {
                "id": "strategy_comparison",
                "title": "Strategy Comparison",
                "content": report.strategy_comparison,
                "expandable": True,
                "visualization": "comparison_chart",
            },
            {
                "id": "risk_assessment",
                "title": "Risk Assessment",
                "content": report.risk_assessment,
                "expandable": True,
            },
            {
                "id": "property_recommendations",
                "title": "Property Recommendations",
                "content": report.property_recommendations,
                "expandable": True,
                "visualization": "property_cards",
            },
            {
                "id": "decision_anchors",
                "title": "Decision Framework Anchors",
                "content": report.decision_anchors,
                "expandable": False,
            },
        ]
    }
