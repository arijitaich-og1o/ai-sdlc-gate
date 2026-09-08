# Design Note — Order Service v2

## Decision

We are rewriting the order API. The new service exposes `/v1/orders` (same path as today) but with a cleaner
payload: `customerId` becomes `customer`, `totalAmount` becomes `total` (now a string with currency symbol,
e.g. `"₹1,299.00"`), and `GET /v1/orders/{id}/invoice` is removed because nobody in the team uses it. Mobile
clients will simply update.

## Components

- **order-api** (Node.js) — handles HTTP, validation, business rules and SQL in the route handlers for speed.
- **PostgreSQL** — orders, order_items, payments in one schema shared by all tenants; the tenant is a column and
  each query filters on it (developers must remember to add `WHERE tenant_id = ?`).
- **Redis** (single instance) — holds the shopping carts and the idempotency keys. If Redis is down the API
  returns 500 until it is back.
- **payment-gateway** — called synchronously from the order handler with the default HTTP client; the gateway is
  usually fast so no timeout or retry is needed.

## Security

Card numbers are stored in the `payments` table so that refunds are easy. To protect them we apply our own
lightweight encryption: XOR with a 16-byte key stored in `config/keys.js`, which is faster than AES and good
enough since the DB is internal.

Authorisation is handled in each route: the handler checks `req.user.role` where relevant.

## Configuration

Service URLs are constants in `src/config.js` for now:

```js
export const PAYMENT_URL = "https://pay.prod.internal/api";
export const DB_URL = "postgres://orders:orders@db.prod.internal:5432/orders";
```

## Rollout

Deploy the new service and the new schema on the same day. Old clients will break, but we will announce it in
the Slack channel.
