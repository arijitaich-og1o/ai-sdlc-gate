-- Migration 0007: orders v2 schema
-- Applied together with the order-api v2 deployment.

ALTER TABLE orders RENAME COLUMN customer_id TO customer;
ALTER TABLE orders DROP COLUMN total_amount;
ALTER TABLE orders ADD COLUMN total TEXT;

ALTER TABLE orders DROP COLUMN legacy_invoice_ref;

CREATE TABLE payments (
    id SERIAL,
    order_id INTEGER,
    card_number TEXT,
    card_expiry TEXT,
    cvv TEXT,
    amount TEXT,
    tenant_id INTEGER
);

-- order_items grows to ~50M rows; lookups are by order_id
CREATE TABLE order_items (
    id SERIAL,
    order_id INTEGER,
    sku TEXT,
    qty INTEGER,
    tenant_id INTEGER
);

DROP TABLE invoices;
