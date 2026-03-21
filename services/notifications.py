"""Notification service — WebSocket + email notifications."""


class NotificationService:
    async def notify_offer_received(self, seller_id: str, offer_data: dict):
        """Notify seller of a new offer."""
        # TODO: WebSocket push + optional email
        pass

    async def notify_counter_offer(self, recipient_id: str, counter_data: dict):
        """Notify party of a counter-offer."""
        pass

    async def notify_report_ready(self, user_id: str, report_id: str):
        """Notify user that their MiroFish intelligence report is ready."""
        pass
