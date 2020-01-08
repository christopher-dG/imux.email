from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

import stripe

from stripe import PaymentIntent, Webhook
from stripe.error import SignatureVerificationError

from . import ORDERS, STRIPE_KEY, STRIPE_WEBHOOK
from .account_manager import Account

stripe.api_key = STRIPE_KEY
CREATED = "created"
CANCELLED = "cancelled"
FAILED = "failed"
SUCCEEDED = "succeeded"
FULLFILLED = "fulfilled"


@dataclass
class Order:
    client_secret: int
    price: int
    state: str
    recipients: List[str]
    weeks: int

    @staticmethod
    def new(*, weeks: int, recipients: List[str]) -> "Order":
        price = Order._price(recipients=len(recipients), weeks=weeks)
        intent = PaymentIntent.create(amount=price, currency="usd")
        order = Order(
            client_secret=intent.client_secret,
            price=price,
            recipients=recipients,
            state=CREATED,
            weeks=weeks,
        )
        order._put()
        return order

    @staticmethod
    def from_intent(intent: PaymentIntent) -> Optional["Order"]:
        resp = ORDERS.get_item(Key={"client_secret": intent.client_secret})
        if "Item" not in resp:
            return None
        item = resp["Item"]
        return Order(
            client_secret=item["client_secret"],
            price=item["price"],
            recipients=item["recipients"],
            state=item["state"],
            weeks=item["weeks"],
        )

    def on_cancel(self) -> None:
        self._update(state=CANCELLED)

    def on_failure(self) -> None:
        self._update(state=FAILED)

    def on_success(self) -> None:
        Account.new(self.recipients, timedelta(weeks=self.weeks))

    def _put(self) -> None:
        ORDERS.put_item(
            Item={
                "client_secret": self.client_secret,
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
        ORDERS.update_item(
            Key={"client_secret": self.client_secret}, AttributeUpdates=updates,
        )

    @staticmethod
    def _price(*, recipients: int, weeks: int) -> int:
        return 500  # TODO


def webhook(data: Dict[str, Any], signature: str) -> int:
    try:
        event = Webhook.construct_from(data, signature, STRIPE_WEBHOOK)
    except (ValueError, SignatureVerificationError):
        return 400
    scope, action = event.type.split(".", 1)
    if scope != "payment_intent":
        return 400
    order = Order.from_intent(event.data.object)
    if not order:
        print("Order was not found")
        return 500
    if scope == "cancelled":
        order.on_cancel()
    elif scope == "payment_failure":
        order.on_failure()
    elif scope == "succeeded":
        order.on_success()
    else:
        return 400
    return 200
