# imux.email

### WIP

This service is not yet online.
It's getting close though!

##### Deployment Notes

Required stuff:

- Verified domain in SES (`DOMAIN` environment variable)
- Pre-existing S3 bucket (`EMAILS_BUCKET` environment variable)
- Owner email address for support (`OWNER_EMAIL`) environment variable
- Set the created receipt ruleset as active

Deploy checklist:

- Deactivate receipt ruleset
- Deploy
- Reactivate receipt ruleset

(this should probably be scripted)

##### TODO

Deal with errors nicely for a single record.
RIght now, if there are multiple records and the last one fails, the ones that succeeded will still run again.
