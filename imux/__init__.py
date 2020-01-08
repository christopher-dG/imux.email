import boto3
import os

DECRYPT = os.getenv("DECRYPT", "")
DOMAIN = os.getenv("DOMAIN", "")
INTRO = os.getenv("INTRO", "")
RECEIVE = os.getenv("RECEIVE", "")
RULESET = os.getenv("RULESET", "")
STRIPE_KEY = os.getenv("STRIPE_KEY", "")
STRIPE_WEBHOOK = os.getenv("STRIPE_WEBHOOK", "")

ddb = boto3.resource("dynamodb")
ACCOUNTS = ddb.Table(os.getenv("ACCOUNTS", ""))
LAMBDA = boto3.client("lambda")
ORDERS = ddb.Table(os.getenv("ORDERS", ""))
SES = boto3.client("ses")
