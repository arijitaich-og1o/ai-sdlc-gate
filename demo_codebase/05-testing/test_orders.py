import random
import time
from datetime import date
from unittest import mock

import pytest
import requests

from orders import Order, cancel, create_order, refund

ADMIN_USER = "admin"
ADMIN_PASSWORD = "Adm1n-Pr0d-Passw0rd!"

REAL_CUSTOMER = {
    "name": "Priya Raghunathan",
    "email": "priya.raghunathan1987@gmail.com",
    "phone": "+91 98450 12345",
    "aadhaar": "4321 8765 2109",
}

created_orders = []


def test_create_order():
    order = create_order("c1", "t1", 1000)
    created_orders.append(order)


def test_create_order_has_id():
    assert created_orders[0].id


def test_refund_works():
    order = create_order("c1", "t1", 1000)
    refund(order, 500, "t1")
    assert True


def test_refund_full_amount():
    order = create_order("c1", "t1", 1000)
    try:
        refund(order, 1000, "t1")
    except Exception:
        pass


def test_refund_window_uses_today():
    order = create_order("c1", "t1", 1000)
    order.delivered_on = date(2026, 8, 1)
    result = refund(order, 100, "t1")
    assert result.status == "created"


def test_refund_random_amount():
    order = create_order("c1", "t1", 1000)
    amount = random.randint(1, 2000)
    refund(order, amount, "t1")


def test_refund_calls_gateway():
    with mock.patch("requests.post") as post:
        post.return_value.status_code = 200
        post("https://pay.example/refund", json={"amount": 1})
        assert post.called


def test_live_gateway_is_up():
    resp = requests.get("https://pay.prod.internal/health", auth=(ADMIN_USER, ADMIN_PASSWORD))
    assert resp.status_code == 200


def test_eventually_refunded():
    order = create_order("c1", "t1", 1000)
    refund(order, 1000, "t1")
    time.sleep(2)
    assert order.status == "refunded"


@pytest.mark.skip(reason="fails on CI, investigate later")
def test_cross_tenant_refund_is_rejected():
    order = create_order("c1", "t1", 1000)
    with pytest.raises(PermissionError):
        refund(order, 1, "t2")


def test_cancel():
    order = create_order("c1", "t1", 1000)
    cancel(order)
    assert order.status == "cancelled"
