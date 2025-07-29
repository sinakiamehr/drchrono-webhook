# api/webhook.py

import os
import requests
import boto3
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
    """
    Refreshes the DrChrono access token using the refresh token.
    Returns the new access token, or raises an exception on failure.
    """
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
    # Optionally update the environment variable in memory for future requests
    os.environ["DRCHRONO_ACCESS_TOKEN"] = new_token
    print("🔄 Refreshed DrChrono access token.")
    return new_token

def fetch_note_metadata(note_id, access_token):
    """
    Fetches note metadata from DrChrono API, with automatic token refresh on 401.
    """
    DRCHRONO_API_BASE = os.environ.get("DRCHRONO_API_BASE", "https://drchrono.com/api/")
    url = f"{DRCHRONO_API_BASE}clinical_notes/{note_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        # Token expired, refresh and retry
        new_token = refresh_access_token()
        headers = {"Authorization": f"Bearer {new_token}"}
        resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def handler(request):
    # DrChrono and provider config
    PROVIDER_STRING = os.environ.get("PROVIDER_STRING", "Dr. Michael Stone")

    # S3 config
    S3_BUCKET = os.environ.get("S3_BUCKET", "clinical-registry-bucket")
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_FOLDER = "chrono-webhook"

    if request.method != "POST":
        return ("Only POST allowed", 405)

    data = request.json
    note_id = data.get("id") or data.get("clinical_note") or data.get("object_id")
    if not note_id:
        return ({"error": "No note ID in webhook payload"}, 400)

    try:
        # Fetch note metadata (with auto token refresh)
        access_token = os.environ.get("DRCHRONO_ACCESS_TOKEN")
        note = fetch_note_metadata(note_id, access_token)
        pdf_url = note.get("pdf")
        if not pdf_url:
            return ({"status": "no_pdf"}, 200)

        # Download PDF
        resp = requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
        pdf_bytes = resp.content

        # Check provider string
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
            return ({"status": "uploaded", "s3_key": s3_key}, 200)
        else:
            return ({"status": "provider_not_found"}, 200)

    except Exception as e:
        print(f"Error processing note: {e}")
        return ({"error": str(e)}, 500)
