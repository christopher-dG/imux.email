import email
import json

from email.message import Message

from typing import Any, Dict, Optional

from . import ACCOUNTS, DECRYPT, LAMBDA
from .accounts import Account


def forward(event: Dict[str, Any], _ctx: Any) -> None:
    print(json.dumps(event, indent=2))
    for r in event["Records"]:
        s3 = r["s3"]
        message = _fetch(s3["bucket"]["name"], s3["object"]["key"])
        if not message:
            return
        uuid = _recipient_uuid(message)
        resp = ACCOUNTS.get_item(Key={"uuid": uuid})
        if "Item" not in resp:
            print(f"Account {uuid} not found")
            return
        account = Account.from_ddb(resp["Item"])
        account.forward(message)


def _fetch(bucket: str, key: str) -> Optional[Message]:
    """Retrieve an email."""
    resp = LAMBDA.invoke(
        FunctionName=DECRYPT, Payload=json.dumps({"bucket": bucket, "key": key})
    )
    body = json.load(resp["Payload"])
    if "FunctionError" in resp:
        print("Decrypt function errored:", json.dumps(body, indent=2))
        return None
    if body is None:
        print("Email was not found")
        return None
    return email.message_from_string(body)


def _recipient_uuid(message: Message) -> str:
    """Get the local part of the recipient address."""
    return "dummy"
