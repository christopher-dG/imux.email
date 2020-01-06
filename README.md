# imux.email

Required stuff:

- Verified domain in SES (`DOMAIN` environment variable)
- Pre-existing S3 bucket (`EMAILS_BUCKET` environment variable)
- Set the created receipt ruleset as active

Deploy checklist:

- Deactivate receipt ruleset
- Deploy
- Reactivate receipt ruleset

(this should probably be scripted)
