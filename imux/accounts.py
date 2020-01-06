import boto3
import json
import os

from uuid import UUID, uuid4

from typing import Any, Dict, List, Union

BOUNCE = os.getenv("BOUNCE")
DOMAIN = os.getenv("DOMAIN")
INTRO = os.getenv("INTRO")
RULESET = os.getenv("RULESET")
SES = boto3.client("ses")


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


def handler(event: Dict[str, Any], _ctx: Any) -> None:
    print(json.dumps(event, indent=2))
    for r in event["Records"]:
        # TODO: Deal with errors nicely for a single record.
        # RIght now, if there are multiple records and the last one fails,
        # the ones that succeeded will still run again.
        name = r["eventName"]
        ddb = r["dynamodb"]
        if name == "INSERT":
            account = Account.from_stream(ddb["NewImage"])
            account.notify()
        elif name == "REMOVE":
            account = Account.from_stream(ddb["OldImage"])
            account.deactivate()
