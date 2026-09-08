"""Customer account service (demo, intentionally defective)."""
import hashlib
import logging
import pickle
import random
import sqlite3
import subprocess

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
log = logging.getLogger("accounts")

DB_PASSWORD = "Sup3rS3cretPr0d!"
PARTNER_API_KEY = "og1o-prod-9f8e7d6c5b4a39281706f5e4d3c2b1a0"
PARTNER_URL = "https://partner.prod.internal/api/v1/verify"


def get_db():
    return sqlite3.connect("accounts.db")


@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    hashed = hashlib.md5(password.encode()).hexdigest()
    cur = get_db().cursor()
    cur.execute(f"SELECT id, role FROM users WHERE username = '{username}' AND password = '{hashed}'")
    row = cur.fetchone()
    if row is None:
        log.info("failed login for %s with password %s", username, password)
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"id": row[0], "role": row[1]})


@app.route("/users/<int:user_id>/profile")
def profile(user_id):
    # any logged-in user may call this
    cur = get_db().cursor()
    cur.execute("SELECT id, username, email, phone, aadhaar FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    return jsonify(dict(zip(["id", "username", "email", "phone", "aadhaar"], row)))


@app.route("/reset-token", methods=["POST"])
def reset_token():
    token = str(random.random())[2:]
    return jsonify({"token": token})


@app.route("/export", methods=["POST"])
def export():
    fmt = request.form.get("format", "csv")
    filename = request.form.get("filename", "export")
    subprocess.call(f"python tools/export.py --format {fmt} --out /tmp/{filename}", shell=True)
    return jsonify({"status": "ok"})


@app.route("/import", methods=["POST"])
def import_prefs():
    prefs = pickle.loads(request.data)
    return jsonify({"imported": len(prefs)})


def verify_with_partner(national_id, attempts=[]):
    attempts.append(national_id)
    try:
        resp = requests.post(
            PARTNER_URL,
            json={"id": national_id},
            headers={"X-Api-Key": PARTNER_API_KEY},
            verify=False,
        )
        return resp.json()["verified"]
    except Exception:
        pass
    return True


def apply_cashback(balance: float, purchase: float) -> float:
    rate = 0.015
    return balance + purchase * rate


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
