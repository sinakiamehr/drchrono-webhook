"""
Vercel Serverless Function: DrChrono Clinical Note Webhook Handler (with S3 upload to chrono-webhook/ folder)

Receives POST requests from DrChrono when a clinical note is locked,
fetches the note's PDF, checks for a provider string, and uploads the PDF to
the 'chrono-webhook/' folder in the 'clinical-registry-bucket' S3 bucket if matched.
"""

import os
import requests
import boto3
from PyPDF2 import PdfReader
from io import BytesIO

def pdf_contains_provider(pdf_bytes, provider_string):
    """
    Checks if the first page of a PDF contains the provider identification string.
    """
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
    """
    Uploads the PDF bytes to the specified S3 bucket and key.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region,
    )
    s3.put_object(Bucket=bucket, Key=key, Body=pdf_bytes)
    print(f"✅ Uploaded to S3: s3://{bucket}/{key}")

def handler(request):
    """
    Vercel serverless function entry point.
    Handles POST requests from DrChrono webhooks, fetches note metadata and PDF,
    checks for provider string, and uploads matching PDFs to S3.
    """
    # DrChrono and provider config
    DRCHRONO_API_BASE = os.environ.get("DRCHRONO_API_BASE", "https://drchrono.com/api/")
    DRCHRONO_ACCESS_TOKEN = os.environ.get("DRCHRONO_ACCESS_TOKEN")
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
        # Fetch note metadata
        url = f"{DRCHRONO_API_BASE}clinical_notes/{note_id}"
        headers = {"Authorization": f"Bearer {DRCHRONO_ACCESS_TOKEN}"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        note = resp.json()
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
