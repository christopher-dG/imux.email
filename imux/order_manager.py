from datetime import timedelta
from typing import Any, Dict, List, Optional

import stripe

from stripe import Webhook
from stripe.checkout import Session
from stripe.error import SignatureVerificationError

from . import DOMAIN, ORDERS, STRIPE_KEY, STRIPE_WEBHOOK
from .account_manager import Account

stripe.api_key = STRIPE_KEY
PENDING = "pending"
SUCCEEDED = "succeeded"


class Order:
    def __init__(
        self, *, id: str, price: int, state: str, recipients: List[str], weeks: int
    ) -> None:
        self.id = id
        self.price = price
        self.state = state
        self.recipients = recipients
        self.weeks = weeks

    @staticmethod
    def new(*, recipients: List[str], weeks: int) -> "Order":
        price = Order._price(n_recipients=len(recipients), n_weeks=weeks)
        session = Session.create(
            cancel_url=f"https://{DOMAIN}?cancelled=true&session_id={{CHECKOUT_SESSION_ID}}",  # noqa: E501
            success_url=f"https://{DOMAIN}/success.html&session_id={{CHECKOUT_SESSION_ID}}",  # noqa: E501
            payment_method_types=["card"],
            line_items=[
                {
                    "amount": price,
                    "currency": "usd",
                    "name": "Shared email address from imux.email",
                    "quantity": 1,
                },
            ],
        )
        order = Order(
            id=session.id,
            price=price,
            recipients=recipients,
            state=PENDING,
            weeks=weeks,
        )
        order._put()
        return order

    @staticmethod
    def from_session(session: Session) -> Optional["Order"]:
        resp = ORDERS.get_item(Key={"id": session.id})
        if "Item" not in resp:
            return None
        item = resp["Item"]
        return Order(
            id=item["id"],
            price=item["price"],
            recipients=item["recipients"],
            state=item["state"],
            weeks=item["weeks"],
        )

    def on_completed(self) -> None:
        account = Account.new(self.recipients, timedelta(weeks=self.weeks))
        self._update(state=SUCCEEDED)
        recipients = ", ".join(recipient.address for recipient in account.recipients)
        n = len(account.recipients)
        print(f"Created new account {account.uuid} for {n} recipients: {recipients}")

    def _put(self) -> None:
        ORDERS.put_item(
            Item={
                "id": self.id,
                "price": self.price,
                "state": self.state,
                "recipients": self.recipients,
                "weeks": self.weeks,
            }
        )

    def _update(self, **kwargs: Any) -> None:
        updates = {}
        for k, v in kwargs.values():
            self.__setattr__(k, v)
            updates[k] = {"Value": v, "Action": "PUT"}
        ORDERS.update_item(Key={"id": self.id}, AttributeUpdates=updates)

    @staticmethod
    def _price(*, n_recipients: int, n_weeks: int) -> int:
        return 500  # TODO


def webhook(data: Dict[str, Any], signature: str) -> int:
    try:
        event = Webhook.construct_from(data, signature, STRIPE_WEBHOOK)
    except (ValueError, SignatureVerificationError):
        return 400
    if event.type != "checkout.session.completed":
        return 400
    order = Order.from_session(event.data.object)
    if not order:
        print("Order was not found")
        return 500
    order.on_completed()
    return 200
