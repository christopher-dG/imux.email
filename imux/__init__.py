import boto3
import os

BOUNCE = os.getenv("BOUNCE", "")
DECRYPT = os.getenv("DECRYPT", "")
DOMAIN = os.getenv("DOMAIN", "")
INTRO = os.getenv("INTRO", "")
RULESET = os.getenv("RULESET", "")

ACCOUNTS = boto3.resource("dynamodb").Table(os.getenv("ACCOUNTS", ""))
LAMBDA = boto3.client("lambda")
SES = boto3.client("ses")
