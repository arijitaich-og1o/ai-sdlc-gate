# Runbook — Accounts Service

## Overview

The accounts service handles login, profiles and the nightly cleanup job. It talks to PostgreSQL and the
partner verification API. Ask in #accounts-dev if something is wrong.

## Alerts

| Alert | Condition | What to do |
|---|---|---|
| AccountsHighCPU | CPU > 50% for 1 minute | Have a look |
| AccountsAnyError | Any 5xx in the last minute | Have a look |
| AccountsDiskFull | Disk > 99% | Restart the pod |

## Deployments

Deployments go straight to production from the pipeline. To roll back, ask the platform team to find the
previous image; we do not keep a list of tags.

## Backups

TODO — the database is on RDS so it is probably backed up. We have never restored one.

## Logs

Logs are written to stdout and kept forever in the log cluster. They include the request body for debugging
(login requests contain the username and password so that failed logins are easy to trace).

## Cleanup job

`cron/cleanup.py` runs nightly at 02:00 IST. If it fails, run it again manually.
