import os
import json
import base64
import urllib.request
import urllib.error

def send_email(to_email: str, subject: str, html_content: str, attachment_bytes: bytes = None, attachment_name: str = None) -> bool:
    """
    Sends an email using the Resend REST API.
    Returns True if successful, otherwise raises or returns False.
    """
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM", "onboarding@resend.dev")

    if not api_key:
        print("ERROR: RESEND_API_KEY is not set in environment.")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Resend API payload
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    if attachment_bytes and attachment_name:
        encoded_content = base64.b64encode(attachment_bytes).decode("utf-8")
        payload["attachments"] = [
            {
                "filename": attachment_name,
                "content": encoded_content
            }
        ]

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            print(f"Resend success: {res_body}")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"Resend HTTP Error {e.code}: {err_body}")
        raise Exception(f"Resend API error: {err_body}")
    except Exception as e:
        print(f"Resend Connection Error: {e}")
        raise e
