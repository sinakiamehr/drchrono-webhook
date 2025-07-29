"""
DrChrono Webhook Endpoint

This Flask application serves as the webhook endpoint for DrChrono EHR system.
It handles both GET (verification) and POST (webhook events) requests,
validates incoming requests, and processes them through the webhook handler.
"""

from flask import Flask, request
from webhook_handler import process_webhook

app = Flask(__name__)

@app.route("/api/webhook", methods=["GET", "POST"])
def webhook():
    """
    Webhook endpoint handler for DrChrono events.
    
    Processes both GET (verification) and POST (webhook events) requests:
    - GET requests with 'msg' parameter are used for webhook verification
    - POST requests contain actual webhook payloads from DrChrono
    
    Returns:
        Tuple: (response_body, status_code, headers) formatted appropriately
               for the request type and content
    """
    # Format event data for the webhook handler
    event = {
        "httpMethod": request.method,
        "headers": dict(request.headers),
        "body": request.data.decode("utf-8"),
        "queryStringParameters": dict(request.args) if request.args else {},
        "queryString": request.query_string.decode("utf-8") if request.query_string else ""
    }
    
    # Process the event through the webhook handler
    result = process_webhook(event)
    
    # Handle different response types based on request method and content
    if request.method == "GET" and "msg" in request.args:
        # DrChrono verification requires JSON response
        return (result["body"], result["statusCode"], {"Content-Type": "application/json"})
    elif result["body"] == "":
        # Empty body responses (verification events) return plain text
        return ("", result["statusCode"], {"Content-Type": "text/plain"})
    else:
        # All other responses default to JSON
        return (result["body"], result["statusCode"], {"Content-Type": "application/json"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)