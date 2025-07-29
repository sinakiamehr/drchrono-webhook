# local_webhook.py

from flask import Flask, request
from webhook_handler import process_webhook

app = Flask(__name__)

@app.route("/api/webhook", methods=["GET", "POST"])
def webhook():
    event = {
        "httpMethod": request.method,
        "headers": dict(request.headers),
        "body": request.data.decode("utf-8"),
        "queryStringParameters": dict(request.args) if request.args else {},
        "queryString": request.query_string.decode("utf-8") if request.query_string else ""
    }
    result = process_webhook(event)
    # For DrChrono verification, always return application/json if GET and msg present
    if request.method == "GET" and "msg" in request.args:
        return (result["body"], result["statusCode"], {"Content-Type": "application/json"})
    # If the body is empty, return plain text (for POST verification event)
    if result["body"] == "":
        return ("", result["statusCode"], {"Content-Type": "text/plain"})
    # For all other responses, default to JSON
    return (result["body"], result["statusCode"], {"Content-Type": "application/json"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)