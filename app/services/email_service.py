import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_name = settings.EMAIL_FROM_NAME
        self.from_address = settings.EMAIL_FROM_ADDRESS
        self.frontend_url = settings.FRONTEND_URL

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email"""
        if not self.smtp_user or not self.smtp_password:
            logger.warning("Email service not configured, skipping email send")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_address}>"
            message["To"] = to_email

            # Add text part
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)

            # Add HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(
                    self.from_address,
                    to_email,
                    message.as_string()
                )

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    async def send_verification_email(
        self,
        to_email: str,
        first_name: str,
        otp_code: str
    ) -> bool:
        """Send email verification OTP code"""
        subject = "Verify your SoulTalk email"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .otp-code {{
                    display: inline-block;
                    padding: 16px 32px;
                    background-color: #4F46E5;
                    color: white;
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Welcome to SoulTalk, {first_name}!</h2>
                <p>Thank you for signing up. Use the following code to verify your email address:</p>
                <div class="otp-code">{otp_code}</div>
                <p>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
                <div class="footer">
                    <p>If you didn't create an account with SoulTalk, you can safely ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Welcome to SoulTalk, {first_name}!

        Thank you for signing up. Use the following code to verify your email address:

        {otp_code}

        This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.

        If you didn't create an account with SoulTalk, you can safely ignore this email.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_password_reset_email(
        self,
        to_email: str,
        first_name: str,
        token: str
    ) -> bool:
        """Send password reset email"""
        reset_url = f"{settings.BACKEND_PUBLIC_URL}/api/auth/reset-password/{token}/open"

        subject = "Reset your SoulTalk password"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #4F46E5;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 20px 0;
                }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Password Reset Request</h2>
                <p>Hi {first_name},</p>
                <p>We received a request to reset your password. Click the button below to set a new password:</p>
                <a href="{reset_url}" class="button">Reset Password</a>
                <p>Or copy and paste this link in your browser:</p>
                <p><a href="{reset_url}">{reset_url}</a></p>
                <p>This link will expire in {settings.PASSWORD_RESET_EXPIRE_HOURS} hour(s).</p>
                <div class="footer">
                    <p>If you didn't request a password reset, you can safely ignore this email. Your password won't be changed.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Password Reset Request

        Hi {first_name},

        We received a request to reset your password. Visit this link to set a new password:
        {reset_url}

        This link will expire in {settings.PASSWORD_RESET_EXPIRE_HOURS} hour(s).

        If you didn't request a password reset, you can safely ignore this email. Your password won't be changed.
        """

        return await self.send_email(to_email, subject, html_content, text_content)


email_service = EmailService()
