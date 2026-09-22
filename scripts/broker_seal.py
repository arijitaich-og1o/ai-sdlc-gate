#!/usr/bin/env python3
"""Seal a plaintext file to an RSA public key as a hybrid envelope.

A random AES-256-GCM key encrypts the payload; that key is wrapped with RSA-OAEP/SHA-256 to the requester's public
key. The envelope is JSON with base64 `key` (wrapped AES key), `nonce`, and `ct` (ciphertext incl. GCM tag). This
is used because a service-account credential is larger than RSA can wrap directly; the client's key broker decrypts
it. Usage: broker_seal.py <pub.pem> <plain.json> <out.enc>
"""
from __future__ import annotations

import base64
import json
import os
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def seal(pub_pem: bytes, plain: bytes) -> dict:
    pub = serialization.load_pem_public_key(pub_pem)
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plain, None)
    wrapped = pub.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return {"v": 1, "alg": "RSA-OAEP-256+A256GCM", "key": base64.b64encode(wrapped).decode(),
            "nonce": base64.b64encode(nonce).decode(), "ct": base64.b64encode(ct).decode()}


if __name__ == "__main__":
    pub_path, plain_path, out_path = sys.argv[1:4]
    env = seal(open(pub_path, "rb").read(), open(plain_path, "rb").read())
    open(out_path, "w", encoding="utf-8").write(json.dumps(env))
