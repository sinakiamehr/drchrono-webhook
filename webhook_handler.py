# webhook_handler.py

import os
import requests
import boto3
import hmac
import hashlib
from PyPDF2 import PdfReader
from io import BytesIO
import json
from dotenv import load_dotenv

load_dotenv()

def verify_signature(headers, body, secret):
    signature = headers.get("X-Drchrono-Signature")
    if not signature or not secret:
        return False
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

def refresh_token():
    resp = requests.post(
        "https://drchrono.com/o/token/",
        data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["DRCHRONO_REFRESH_TOKEN"],
            "client_id": os.environ["DRCHRONO_CLIENT_ID"],
            "client_secret": os.environ["DRCHRONO_CLIENT_SECRET"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    new_token = resp.json()["access_token"]
    os.environ["DRCHRONO_ACCESS_TOKEN"] = new_token
    return new_token

def fetch_note(note_id, token):
    url = f"https://drchrono.com/api/clinical_notes/{note_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        token = refresh_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def provider_in_pdf(pdf_bytes, provider):
    reader = PdfReader(BytesIO(pdf_bytes))
    if not reader.pages:
        return False
    text = reader.pages[0].extract_text() or ""
    return provider in text

def upload_pdf(pdf_bytes, bucket, key):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ["MY_AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["MY_AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("MY_AWS_REGION", "us-east-1"),
    )
    s3.put_object(Bucket=bucket, Key=key, Body=pdf_bytes)

def process_webhook(event):
    method = event.get("httpMethod", "GET")
    headers = event.get("headers", {})
    body = event.get("body", "").encode()
    secret = os.environ.get("DRCHRONO_WEBHOOK_SECRET")
    provider = os.environ.get("PROVIDER_STRING")
    bucket = os.environ.get("S3_BUCKET")

    # --- DrChrono webhook verification via GET with msg param ---
    if method == "GET":
        # DrChrono sends a GET with a 'msg' parameter for verification
        msg = None
        if "queryStringParameters" in event and event["queryStringParameters"]:
            msg = event["queryStringParameters"].get("msg")
            if isinstance(msg, list):
                msg = msg[0]
        elif "queryString" in event and event["queryString"]:
            from urllib.parse import parse_qs
            parsed = parse_qs(event["queryString"])
            msg = parsed.get("msg", [None])[0]

        if msg and secret:
            hashed = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
            return {"statusCode": 200, "body": json.dumps({"secret_token": hashed})}
        else:
            return {"statusCode": 400, "body": "Missing msg parameter"}


    if method != "POST":
        return {"statusCode": 405, "body": "Only POST allowed"}

    try:
        data = json.loads(event.get("body", "{}"))
    except Exception:
        data = {}

    # Allow DrChrono verification event (no signature, just receiver key)
    if "receiver" in data:
        return {"statusCode": 200, "body": ""}  # Empty body for verification

    if not verify_signature(headers, body, secret):
        return {"statusCode": 401, "body": json.dumps({"error": "Invalid signature"})}

    note_id = data.get("id") or data.get("clinical_note") or data.get("object_id")
    if not note_id:
        return {"statusCode": 400, "body": json.dumps({"error": "No note ID in webhook payload"})}

    try:
        token = os.environ.get("DRCHRONO_ACCESS_TOKEN")
        note = fetch_note(note_id, token)
        pdf_url = note.get("pdf")
        if not pdf_url:
            return {"statusCode": 200, "body": json.dumps({"status": "no_pdf"})}

        resp = requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
        pdf_bytes = resp.content

        if provider_in_pdf(pdf_bytes, provider):
            s3_key = f"chrono-webhook/note_{note_id}.pdf"
            upload_pdf(pdf_bytes, bucket, s3_key)
            return {"statusCode": 200, "body": json.dumps({"status": "uploaded", "s3_key": s3_key})}
        else:
            return {"statusCode": 200, "body": json.dumps({"status": "provider_not_found"})}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}