import os
from dotenv import load_dotenv
load_dotenv()

from app.utils.mail import send_email

try:
    print("Testing send_email to albin.kairatechnologies@gmail.com...")
    res = send_email(
        to_email="albin.kairatechnologies@gmail.com",
        subject="KairaFlow Test OTP",
        html_content="<h1>123456</h1><p>Test OTP content</p>"
    )
    print("Result:", res)
except Exception as e:
    print("Error:", e)
