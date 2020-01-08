import json

from datetime import datetime, timedelta
from email.message import Message
from uuid import UUID, uuid4

from typing import Any, Dict, List, Optional, Union

from . import ACCOUNTS, DOMAIN, INTRO, SES, receipt_rule


class Recipient:
    """An email forwarding recipient."""

    def __init__(self, address: str, unsubscribe: Union[str, UUID] = "") -> None:
        self.address = address
        self.unsubscribe = str(unsubscribe or uuid4())


class Account:
    """An email receiving/forwarding account."""

    def __init__(
        self, uuid: Union[str, UUID], recipients: List[Recipient], expires: datetime,
    ) -> None:
        self.uuid = str(uuid)
        self.recipients = recipients
        self.expires = round(expires.timestamp())

    @staticmethod
    def new(recipients: List[str], period: timedelta) -> "Account":
        """Create a brand new account."""
        account = Account(
            uuid4(), [Recipient(r) for r in recipients], datetime.now() + period,
        )
        account._put()
        return account

    @staticmethod
    def get(uuid: str) -> Optional["Account"]:
        resp = ACCOUNTS.get_item(Key={"uuid": uuid})
        if "Item" in resp:
            return Account.from_ddb(resp["Item"])
        return None

    @staticmethod
    def from_ddb(data: Dict[str, Any]) -> "Account":
        """Get an account from a DynamoDB GetItem response."""
        return Account(
            data["uuid"],
            [Recipient(r["address"], r["unsubscribe"]) for r in data["recipients"]],
            data["expires"],
        )

    @staticmethod
    def from_stream(data: Dict[str, Any]) -> "Account":
        """Get an account from a DynamoDB stream event."""
        return Account(
            uuid=data["uuid"]["S"],
            recipients=[
                Recipient(r["M"]["address"]["S"], r["M"]["unsubscribe"]["S"])
                for r in data["recipients"]["L"]
            ],
            expires=data["expires"]["N"],
        )

    def recipient_from_token(self, token: str) -> Optional[Recipient]:
        """Get the recipient that has a given unsubscribe token."""
        for recipient in self.recipients:
            if token == recipient.unsubscribe:
                return recipient
        return None

    def unsubscribe(self, recipient: Recipient) -> None:
        self.recipients.remove(recipient)
        ACCOUNTS.update_item(
            Key={"uuid": self.uuid},
            AttributeUpdates={"recipients": self._recipients_as_dicts()},
        )

    def activate(self) -> None:
        """Activate an email account."""
        receipt_rule.update(add=self._address())

    def deactivate(self) -> None:
        """Deactivate the email account."""
        receipt_rule.update(remove=self._address())

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
            Source=f"noreply@{DOMAIN}",
            Template=INTRO,
            DefaultTemplateData=json.dumps({"uuid": self.uuid}),
            Destinations=destinations,
        )

    def forward(self, message: Message) -> None:
        """Forward an email to each recipient."""
        print(message.as_string())  # TODO

    def _recipients_as_dicts(self) -> List[Dict[str, str]]:
        return [
            {"address": recipient.address, "unsubscribe": recipient.unsubscribe}
            for recipient in self.recipients
        ]

    def _put(self) -> None:
        ACCOUNTS.put_item(
            Item={
                "uuid": self.uuid,
                "recipients": [
                    {"address": recipient.address, "unsubscribe": recipient.unsubscribe}
                    for recipient in self.recipients
                ],
                "expires": self.expires,
            }
        )

    def _address(self) -> str:
        """Get the account's email address."""
        return f"{self.uuid}@{DOMAIN}"


def handler(event: Dict[str, Any], _ctx: Any) -> None:
    print(json.dumps(event, indent=2))
    for r in event["Records"]:
        name = r["eventName"]
        ddb = r["dynamodb"]
        if name == "INSERT":
            account = Account.from_stream(ddb["NewImage"])
            account.activate()
            account.notify()
        elif name == "REMOVE":
            account = Account.from_stream(ddb["OldImage"])
            account.deactivate()
