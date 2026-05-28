import os
import json
import base64
import urllib.request
import urllib.error

# Read manually from .env
api_key = None
from_email = None

with open(".env", "r") as f:
    for line in f:
        if line.startswith("RESEND_API_KEY="):
            api_key = line.split("=", 1)[1].strip()
        elif line.startswith("RESEND_FROM="):
            from_email = line.split("=", 1)[1].strip()

print("API Key:", api_key)
print("From Email:", from_email)

to_email = "albin.kairatechnologies@gmail.com"
subject = "KairaFlow Test OTP (Standalone with User-Agent)"
html_content = "<h1>123456</h1><p>Test OTP content from standalone script with User-Agent</p>"

url = "https://api.resend.com/emails"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

payload = {
    "from": from_email,
    "to": [to_email],
    "subject": subject,
    "html": html_content
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers=headers,
    method="POST"
)

try:
    print("Sending request to Resend API...")
    with urllib.request.urlopen(req, timeout=15) as response:
        res_body = response.read().decode("utf-8")
        print(f"Resend success: {res_body}")
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"Resend HTTP Error {e.code}: {err_body}")
except Exception as e:
    print(f"Resend Connection Error: {e}")
