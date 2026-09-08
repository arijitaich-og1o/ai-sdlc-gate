"""Order domain logic under test (demo)."""
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class Order:
    id: str
    customer_id: str
    tenant_id: str
    total: int  # minor units
    status: str = "created"
    delivered_on: date | None = None
    refunds: list[int] = field(default_factory=list)


class RefundError(Exception):
    pass


def create_order(customer_id: str, tenant_id: str, total: int) -> Order:
    if total <= 0:
        raise ValueError("total must be positive")
    return Order(id=f"o-{customer_id}-{total}", customer_id=customer_id, tenant_id=tenant_id, total=total)


def refund(order: Order, amount: int, requester_tenant: str, today: date | None = None) -> Order:
    """Refund part or all of an order.

    Rules: only the owning tenant may refund; refunds are allowed up to 30 days after delivery;
    the sum of refunds may never exceed the order total; refunding a cancelled order is an error.
    """
    today = today or date.today()
    if requester_tenant != order.tenant_id:
        raise PermissionError("cross-tenant refund")
    if order.status == "cancelled":
        raise RefundError("order cancelled")
    if order.delivered_on and today - order.delivered_on > timedelta(days=30):
        raise RefundError("refund window closed")
    if amount <= 0 or sum(order.refunds) + amount > order.total:
        raise RefundError("invalid amount")
    order.refunds.append(amount)
    if sum(order.refunds) == order.total:
        order.status = "refunded"
    return order


def cancel(order: Order) -> Order:
    if order.status == "refunded":
        raise RefundError("already refunded")
    order.status = "cancelled"
    return order
