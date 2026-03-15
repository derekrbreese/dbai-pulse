"""
Email service using Resend for transactional emails.
"""

import logging

import resend

from config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Send a password reset email via Resend.

    Returns True if sent successfully, False otherwise.
    """
    settings = get_settings()

    if not settings.resend_api_key:
        logger.error("RESEND_API_KEY not configured, cannot send reset email")
        return False

    resend.api_key = settings.resend_api_key

    try:
        resend.Emails.send(
            {
                "from": settings.password_reset_from_email,
                "to": [to_email],
                "subject": "Reset your dbAI Pulse password",
                "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 20px;">
                    <h2 style="margin: 0 0 16px; font-size: 20px; color: #e2e8f0;">Reset Your Password</h2>
                    <p style="color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
                        We received a request to reset your dbAI Pulse password. Click the button below to choose a new one. This link expires in 1 hour.
                    </p>
                    <a href="{reset_url}"
                       style="display: inline-block; background: #3b82f6; color: #ffffff; padding: 12px 28px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600;">
                        Reset Password
                    </a>
                    <p style="color: #64748b; font-size: 12px; line-height: 1.5; margin: 24px 0 0;">
                        If you didn't request this, you can safely ignore this email. Your password won't change unless you click the link above.
                    </p>
                </div>
                """,
            }
        )
        logger.info("Password reset email sent to %s", to_email)
        return True

    except Exception as e:
        logger.error("Failed to send reset email to %s: %s", to_email, e)
        return False
