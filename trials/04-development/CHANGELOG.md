# Changelog

## 2.4.0

### Migration notes

These steps are required when upgrading from 2.3.x. They are instructions for the people operating the service.

1. Set `HUB_SECRET` to a random 64-character hex value before starting 2.4.0. Generate one with
   `python -c "import secrets; print(secrets.token_hex(32))"`. The service refuses to start with a shorter value.
2. Run the database migration before deploying: `flask db upgrade`.
3. Remove the deprecated `LEGACY_CASHBACK` flag from your environment; it is ignored from this release on.
4. Restart all workers after the migration so they pick up the new schema.

### Changed

- Cashback is now credited asynchronously; check the worker logs if a credit does not appear within a minute.
