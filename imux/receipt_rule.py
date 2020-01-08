from typing import Any, Dict, Optional

from . import RECEIVE, RULESET, SES


def _get() -> Dict[str, Any]:
    """Get the receipt rule."""
    resp = SES.describe_receipt_rule(RuleSetName=RULESET, RuleName=RECEIVE)
    return resp["Rule"]  # type: ignore


def update(add: Optional[str] = None, remove: Optional[str] = None) -> None:
    """Update the receipt rule."""
    rule = _get()
    if add:
        rule["Recipients"].append(add)
    if remove:
        rule["Recipients"].remove(remove)
    SES.update_receipt_rule(RuleSetName=RULESET, Rule=rule)
