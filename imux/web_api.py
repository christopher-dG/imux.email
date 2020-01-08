from typing import Any, Dict, Tuple

from flask import Flask, Response as FlaskResponse, request

from . import DOMAIN, order_manager
from .account_manager import Account
from .order_manager import Order

Response = Tuple[Dict[str, Any], int]
app = Flask(__name__)


@app.after_request
def cors(response: FlaskResponse) -> FlaskResponse:
    response.headers["Access-Control-Allow-Origin"] = f"https://{DOMAIN}"
    return response


@app.route("/payments", methods=["POST"])
def create_order() -> Response:
    recipients = [r.strip() for r in request.form.get("recipients", "").split(",")]
    weeks = request.form.get("weeks", "")
    try:
        weeks = int(weeks)
    except ValueError:
        return {"error": "Invalid input for weeks, expected an integer"}, 400
    if not recipients:
        return {"error": "No recipients were specified"}, 400
    if weeks <= 0:
        return {"error": "Number of weeks should be positive"}, 400
    order = Order.new(recipients=recipients, weeks=weeks)
    return {"client_secret": order.client_secret}, 200


@app.route("/payments/webhook", methods=["POST"])
def payment_webhook() -> Response:
    status = order_manager.webhook(
        request.json, request.headers.get("HTTP_STRIPE_SIGNATURE", ""),
    )
    return {}, status


@app.route("/unsubscribe/<uuid>/<token>", methods=["POST"])
def unsubscribe(uuid: str, token: str) -> Response:
    account = Account.get(uuid)
    if not account:
        return {"error": "The email account was not found"}, 400
    recipient = account.recipient_from_token(token)
    if not recipient:
        return {"error": "The email recipient was not found"}, 400
    account.unsubscribe(recipient)
    return {}, 200
