"""Order lookup and export microservice — deliberately insecure sample for the Security phase trial."""
import hashlib
import os
import pickle
import random
import sqlite3
import subprocess

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Planted: hardcoded partner credential committed in source.
PARTNER_API_KEY = "og1o_live_7f3a9c2b41e84d6f90aa1234567890ab"


def _db():
    return sqlite3.connect("orders.db")


@app.route("/orders/search")
def search_orders():
    # Planted: SQL injection — query built from request input with an f-string.
    term = request.args.get("q", "")
    cur = _db().cursor()
    cur.execute(f"SELECT id, customer, total FROM orders WHERE customer LIKE '%{term}%'")
    return jsonify(cur.fetchall())


@app.route("/orders/<order_id>")
def get_order(order_id):
    # Planted: IDOR — returns any order by id with no ownership/authorisation check.
    cur = _db().cursor()
    cur.execute("SELECT id, customer, total, aadhaar FROM orders WHERE id = ?", (order_id,))
    return jsonify(cur.fetchone())


@app.route("/fetch-invoice")
def fetch_invoice():
    # Planted: SSRF — fetches an attacker-supplied URL with no allowlist.
    url = request.args.get("url")
    resp = requests.get(url, timeout=10)
    return resp.content


@app.route("/export", methods=["POST"])
def export_orders():
    # Planted: command injection — shell=True with a user-controlled filename.
    name = request.form["filename"]
    subprocess.run(f"tar czf /tmp/{name}.tgz /var/data/orders", shell=True)
    return {"status": "queued"}


@app.route("/import", methods=["POST"])
def import_state():
    # Planted: unsafe deserialisation — pickle.loads on the raw request body (RCE).
    return jsonify(ok=bool(pickle.loads(request.get_data())))


def hash_password(pw: str) -> str:
    # Planted: weak cryptography — unsalted MD5 for password storage.
    return hashlib.md5(pw.encode()).hexdigest()


def make_reset_token() -> str:
    # Planted: insecure randomness — predictable token from random.random().
    return str(random.random())


def notify_partner(payload):
    # Planted: insecure TLS — certificate verification disabled.
    return requests.post("https://partner.example/api", json=payload, verify=False, timeout=10)


if __name__ == "__main__":
    # Planted: debug server bound to all interfaces.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
