# DrChrono Webhook PDF Uploader

A secure, serverless webhook handler that automatically receives clinical note notifications from DrChrono, validates provider identity, and uploads matching PDFs to a protected S3 bucket.

## Overview

This repository contains a minimal, production-ready Vercel serverless function that acts as a webhook endpoint for DrChrono’s “clinical note locked” event. When triggered, the function:

- Fetches the clinical note metadata and PDF from DrChrono.
- Checks the PDF’s first page for a specified provider identification string.
- Uploads matching PDFs directly to a private folder in your AWS S3 bucket.

All sensitive credentials are managed via environment variables, and the AWS IAM user is configured with the least-privilege permissions to ensure maximum security.

## Relationship to Clinical Registry Automation

This webhook service is designed as a secure, cloud-native intake point for the broader [clinical_registry_automation](../clinical_registry_automation) project. By capturing and storing relevant clinical note PDFs in real time, it provides a reliable data source for downstream automation, NLP, and structured data extraction workflows managed in the main project.

## Project Structure

```
drchrono-webhook/
├── api/
│   └── webhook.py           # Vercel serverless function for webhook handling
├── requirements.txt         # Python dependencies
├── vercel.json              # Vercel configuration (Python runtime)
├── .env.example             # Template for environment variables
└── .gitignore               # Git ignore rules
```

## Setup & Deployment

1. **AWS Setup**:  
   - Create an S3 bucket (e.g., `s3bucket`).
   - Add a folder (prefix) `s3bucket/webhook-folder`.
   - Create an IAM user with only `s3:PutObject` permission for `s3bucket/webhook-folder/*.pdf`.

2. **Environment Variables**:  
   Copy `.env.example` to `.env` and fill in your credentials.  
   Set these same variables in your Vercel project dashboard for production.

3. **Deploy to Vercel**:  
   - Push this repo to GitHub/GitLab/Bitbucket.
   - Import as a new project on [Vercel](https://vercel.com/).
   - Deploy and obtain your public endpoint URL.

4. **Configure DrChrono Webhook**:  
   - Register your Vercel endpoint URL in DrChrono’s developer dashboard for the “clinical note locked” webhook event.

## Security

- All files are uploaded to a private S3 bucket folder.
- Vercel’s IAM user can only upload (not view or delete) PDFs.
- No sensitive credentials are committed to the repository.

## License

This project is proprietary. All rights reserved.

