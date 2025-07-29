# DrChrono Webhook Handler

This application handles webhooks from DrChrono's EHR system, processes clinical notes, and stores relevant PDFs in AWS S3.

## Files

### app.py
- Flask application serving as the webhook endpoint
- Routes `/api/webhook` for DrChrono webhook events
- Handles both GET (verification) and POST (webhook events)
- Processes requests and passes them to `webhook_handler.py`
- Returns appropriate responses with correct content types

### webhook_handler.py
- Contains core business logic for processing webhooks
- Functions:
  - `verify_signature`: Validates DrChrono webhook signatures
  - `refresh_token`: Handles OAuth token refresh for DrChrono API
  - `fetch_note`: Retrieves clinical note details from DrChrono API
  - `provider_in_pdf`: Checks if a provider's name appears in a PDF
  - `upload_pdf`: Stores PDFs in AWS S3 bucket
  - `process_webhook`: Main entry point that orchestrates the workflow

### requirements.txt
- Lists Python dependencies:
  - Flask (web framework)
  - requests (HTTP client)
  - boto3 (AWS SDK)
  - PyPDF2 (PDF processing)
  - python-dotenv (environment variables)
  - gunicorn (production WSGI server)

## Environment Variables
Required `.env` variables:
- `DRCHRONO_WEBHOOK_SECRET`: Webhook verification secret
- `DRCHRONO_CLIENT_ID`, `DRCHRONO_CLIENT_SECRET`: OAuth credentials
- `DRCHRONO_ACCESS_TOKEN`, `DRCHRONO_REFRESH_TOKEN`: API tokens
- `PROVIDER_STRING`: Provider name to match in PDFs
- AWS credentials (`MY_AWS_ACCESS_KEY_ID`, `MY_AWS_SECRET_ACCESS_KEY`)
- `S3_BUCKET`: Target bucket for PDF storage

## Deployment on Render
1. Connect your GitHub repository to Render
2. Set all required environment variables
3. Specify `gunicorn app:app` as the start command
4. The webhook URL will be `https://your-service.onrender.com/api/webhook`

## Project Structure

```
drchrono-webhook/
├── .env.example       # Template for environment variables
├── .gitignore        # Git ignore rules
├── LICENSE           # Proprietary license
├── README.md         # Project documentation
├── app.py            # Flask web application
├── requirements.txt  # Python dependencies
└── webhook_handler.py # Core business logic
```

## Security

- All files are uploaded to a private S3 bucket folder
- IAM user has only `s3:PutObject` permission for the target folder
- No sensitive credentials are committed to the repository
- Webhook requests are verified using HMAC signatures

## Setup & Deployment

### AWS Setup

1. Create an S3 bucket (e.g., `s3bucket`)
2. Add a folder (prefix) `s3bucket/webhook-folder`
3. Create an IAM user with only `s3:PutObject` permission for `s3bucket/webhook-folder/*.pdf`

### Environment Variables

1. Copy `.env.example` to `.env` and fill in your credentials
2. Set these same variables in your Render project dashboard

## Webhook Flow
1. DrChrono sends POST request with signed payload
2. App verifies signature using shared secret
3. For clinical note events:
   - Fetches note details from DrChrono API
   - Downloads associated PDF
   - Checks if provider name appears in PDF
   - If match found, uploads to S3
4. Returns JSON response with status

## Verification

DrChrono requires GET verification with `msg` parameter:
- Returns HMAC-SHA256 of msg using webhook secret
- Required for initial webhook setup

## License

This project is proprietary. All rights reserved.

