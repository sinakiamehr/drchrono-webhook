# api/webhook.py

"""
DrChrono Webhook PDF Uploader (Vercel Serverless Function)
Production endpoint: https://drchrono-webhook.vercel.app/api/webhook

- Verifies DrChrono webhook signature using a shared secret.
- Fetches clinical note PDF, checks provider string, uploads to S3.
- Automatically refreshes DrChrono access token if expired.
"""

import os
import requests
import boto3
import hmac
import hashlib
from PyPDF2 import PdfReader
from io import BytesIO

def pdf_contains_provider(pdf_bytes, provider_string):
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if len(reader.pages) == 0:
            return False
        first_page = reader.pages[0]
        text = first_page.extract_text() or ""
        return provider_string in text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return False

def upload_to_s3(pdf_bytes, bucket, key, aws_access_key_id, aws_secret_access_key, aws_region):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region,
    )
    s3.put_object(Bucket=bucket, Key=key, Body=pdf_bytes)
    print(f"✅ Uploaded to S3: s3://{bucket}/{key}")

def refresh_access_token():
    token_url = "https://drchrono.com/o/token/"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.environ["DRCHRONO_REFRESH_TOKEN"],
        "client_id": os.environ["DRCHRONO_CLIENT_ID"],
        "client_secret": os.environ["DRCHRONO_CLIENT_SECRET"],
    }
    resp = requests.post(token_url, data=data, timeout=30)
    resp.raise_for_status()
    new_token = resp.json()["access_token"]
    os.environ["DRCHRONO_ACCESS_TOKEN"] = new_token
    print("🔄 Refreshed DrChrono access token.")
    return new_token

def fetch_note_metadata(note_id, access_token):
    DRCHRONO_API_BASE = os.environ.get("DRCHRONO_API_BASE", "https://drchrono.com/api/")
    url = f"{DRCHRONO_API_BASE}clinical_notes/{note_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        new_token = refresh_access_token()
        headers = {"Authorization": f"Bearer {new_token}"}
        resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def verify_drchrono_signature(request, secret):
    """
    Verifies the HMAC SHA256 signature of the request body using the shared secret.
    Assumes DrChrono sends the signature in the 'X-Drchrono-Signature' header.
    """
    signature = request.headers.get("X-Drchrono-Signature")
    if not signature:
        print("❌ No signature header found.")
        return False
    computed = hmac.new(
        secret.encode(),
        request.body,  # raw bytes of the request body
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(computed, signature):
        print("❌ Signature mismatch.")
        return False
    return True

def handler(event, context):
    import json
    
    # Parse event directly without Request class
    method = event.get('httpMethod', 'GET')
    headers = event.get('headers', {})
    body = event.get('body', '').encode()
    try:
        request_json = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        request_json = {}
    PROVIDER_STRING = os.environ.get("PROVIDER_STRING")
    S3_BUCKET = os.environ.get("S3_BUCKET")
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_FOLDER = "chrono-webhook"
    WEBHOOK_SECRET = os.environ.get("DRCHRONO_WEBHOOK_SECRET")
    
    if method == "GET":
        return {"statusCode": 200, "body": "Webhook is live!"}
    if method != "POST":
        return {"statusCode":405,"body":"Only POST allowed"}

    # Verify DrChrono webhook signature
    if not verify_drchrono_signature({"headers": headers, "body": body, "json": request_json}, WEBHOOK_SECRET):
        return {"statusCode": 401, "body": json.dumps({"error": "Invalid signature"})}

    data = request_json
    note_id = data.get("id") or data.get("clinical_note") or data.get("object_id")
    if not note_id:
        return {"statusCode": 400, "body": json.dumps({"error": "No note ID in webhook payload"})}

    try:
        access_token = os.environ.get("DRCHRONO_ACCESS_TOKEN")
        note = fetch_note_metadata(note_id, access_token)
        pdf_url = note.get("pdf")
        if not pdf_url:
            return {"statusCode": 200, "body": json.dumps({"status": "no_pdf"})}

        resp = requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
        pdf_bytes = resp.content

        if pdf_contains_provider(pdf_bytes, PROVIDER_STRING):
            s3_key = f"{S3_FOLDER}/note_{note_id}.pdf"
            upload_to_s3(
                pdf_bytes,
                S3_BUCKET,
                s3_key,
                AWS_ACCESS_KEY_ID,
                AWS_SECRET_ACCESS_KEY,
                AWS_REGION,
            )
            return {"statusCode": 200, "body": json.dumps({"status": "uploaded", "s3_key": s3_key})}
        else:
            return {"statusCode": 200, "body": json.dumps({"status": "provider_not_found"})}

    except Exception as e:
        print(f"Error processing note: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
