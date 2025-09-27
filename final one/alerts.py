import streamlit as st
import smtplib
from email.mime.text import MIMEText

def send_email(to_email: str, subject: str, body: str):
    """
    Uses secrets in .streamlit/secrets.toml:
      smtp_host, smtp_port, smtp_user, smtp_pass
    """
    try:
        host = st.secrets.get("smtp_host", "smtp.gmail.com")
        port = int(st.secrets.get("smtp_port", 465))
        user = st.secrets["smtp_user"]
        pwd  = st.secrets["smtp_pass"]

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_email

        with smtplib.SMTP_SSL(host, port) as s:
            s.login(user, pwd)
            s.send_message(msg)
        return True, "Email sent."
    except Exception as e:
        return False, f"Email failed: {e}"

# (Optional) SMS via Twilio if you want later:
# from twilio.rest import Client
# def send_sms(to_phone: str, message: str):
#     sid = st.secrets["twilio_sid"]
#     token = st.secrets["twilio_token"]
#     from_phone = st.secrets["twilio_from"]
#     client = Client(sid, token)
#     client.messages.create(to=to_phone, from_=from_phone, body=message)
