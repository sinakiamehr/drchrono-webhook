# api/webhook.py

import os
import hmac
import hashlib

def handler(request, response):
    # Vercel passes the request as an object with .body and .headers
    secret = os.environ.get("DRCHRONO_WEBHOOK_SECRET", "changeme")
    signature = request.headers.get("x-drchrono-signature")  # header keys are lowercased in Vercel
    if not signature:
        return response.status(401).send("No signature header found.")

    # Vercel provides the raw body as bytes
    body = request.body if isinstance(request.body, bytes) else request.body.encode()
    computed = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        return response.status(401).send("Signature mismatch.")

    return response.status(200).send("Signature OK")
