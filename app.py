# app.py

from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # DrChrono verification: echo back the msg parameter
        msg = request.args.get("msg")
        if msg:
            return msg, 200
        return "Missing msg parameter", 400
    # Handle POST requests (webhook events) here
    return "OK", 200

if __name__ == "__main__":
    app.run()
