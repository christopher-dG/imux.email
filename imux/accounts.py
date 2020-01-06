import json

from email.message import Message
from uuid import UUID, uuid4

from typing import Any, Dict, List, Union

from . import BOUNCE, DOMAIN, INTRO, RULESET, SES


class Recipient:
    """An email forwarding recipient."""

    def __init__(self, address: str, unsubscribe: Union[str, UUID] = "") -> None:
        self.address = address
        self.unsubscribe = str(unsubscribe or uuid4())


class Account:
    """An email receiving/forwarding account."""

    def __init__(self, uuid: Union[str, UUID], recipients: List[Recipient]) -> None:
        self.uuid = str(uuid)
        self.recipients = recipients

    @staticmethod
    def new(recipients: List[str]) -> "Account":
        """Create a brand new account."""
        return Account(uuid4(), [Recipient(r) for r in recipients])

    @staticmethod
    def from_ddb(data: Dict[str, Any]) -> "Account":
        """Get an account from a DynamoDB GetItem response."""
        return Account(
            data["uuid"],
            [Recipient(r["address"], r["unsubscribe"]) for r in data["recipients"]],
        )

    @staticmethod
    def from_stream(event: Dict[str, Any]) -> "Account":
        """Get an account from a DynamoDB stream event."""
        return Account(
            uuid=event["uuid"]["S"],
            recipients=[
                Recipient(r["M"]["address"]["S"], r["M"]["unsubscribe"]["S"])
                for r in event["recipients"]["L"]
            ],
        )

    def deactivate(self) -> None:
        """Deactivate an email address by adding it to the bounce list."""
        resp = SES.describe_receipt_rule(RuleSetName=RULESET, RuleName=BOUNCE)
        resp["Rule"]["Recipients"].append(f"{self.uuid}@{DOMAIN}")
        SES.update_receipt_rule(RuleSetName=RULESET, Rule=resp["Rule"])

    def notify(self) -> None:
        """Send the intro email to each recipient."""
        destinations = [
            {
                "Destination": {"ToAddresses": [recipient.address]},
                "ReplacementTemplateData": json.dumps(
                    {"unsubscribe": recipient.unsubscribe}
                ),
            }
            for recipient in self.recipients
        ]
        SES.send_bulk_templated_email(
            Source=f"hello@{DOMAIN}",
            Template=INTRO,
            DefaultTemplateData=json.dumps({"uuid": self.uuid}),
            Destinations=destinations,
        )

    def forward(self, message: Message) -> None:
        """Forward an email to each recipient."""
        print(message.as_string())  # TODO


def handler(event: Dict[str, Any], _ctx: Any) -> None:
    print(json.dumps(event, indent=2))
    for r in event["Records"]:
        name = r["eventName"]
        ddb = r["dynamodb"]
        if name == "INSERT":
            account = Account.from_stream(ddb["NewImage"])
            account.notify()
        elif name == "REMOVE":
            account = Account.from_stream(ddb["OldImage"])
            account.deactivate()
