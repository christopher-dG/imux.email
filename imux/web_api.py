from typing import Any, Dict, Tuple
from urllib.parse import quote

from flask import Flask, Response as FlaskResponse, redirect, request
from werkzeug import Response as WerkzeugResponse

from . import DOMAIN, order_manager
from .account_manager import Account
from .order_manager import Order

JSONResponse = Tuple[Dict[str, Any], int]
app = Flask(__name__)


@app.after_request
def cors(response: FlaskResponse) -> FlaskResponse:
    response.headers["Access-Control-Allow-Origin"] = f"https://{DOMAIN}"
    return response


@app.route("/payments", methods=["POST"])
def create_order() -> WerkzeugResponse:
    recipients = [r for r in request.form.getlist("recipients") if r]
    weeks = request.form.get("weeks", "")
    try:
        weeks = int(weeks)
    except ValueError:
        return _redirect("/", message="Invalid number input for weeks")
    if weeks <= 0:
        return _redirect("/", message="Invalid number input for weeks")
    if not recipients:
        return _redirect("/", message="You need to enter at least one recipient")
    order = Order.new(recipients=recipients, weeks=weeks)
    return _redirect("/redirect", id=order.id)


@app.route("/payments/webhook", methods=["POST"])
def payment_webhook() -> JSONResponse:
    status = order_manager.webhook(
        request.json, request.headers.get("HTTP_STRIPE_SIGNATURE", ""),
    )
    return {}, status


@app.route("/unsubscribe/<uuid>/<token>", methods=["POST"])
def unsubscribe(uuid: str, token: str) -> JSONResponse:
    account = Account.get(uuid)
    if not account:
        return {"error": "The email account was not found"}, 400
    recipient = account.recipient_from_token(token)
    if not recipient:
        return {"error": "The email recipient was not found"}, 400
    account.unsubscribe(recipient)
    return {}, 200


def _redirect(destination: str, **kwargs: str) -> WerkzeugResponse:
    query = "&".join(f"{k}={quote(v)}" for k, v in kwargs.items())
    return redirect(f"{destination}?{query}")
