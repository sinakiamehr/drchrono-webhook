from api.webhook import handler

# Correct test event structure
event = {
    "httpMethod": "POST",
    "headers": {"X-Drchrono-Signature": "test_signature"},
    "body": "{\"patient\":123}"
}

response = handler(event, None)
print(response)