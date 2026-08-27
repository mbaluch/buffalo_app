import logging

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=False,
            start_tls=settings.smtp_tls,
        )
    except Exception:
        logger.exception("Failed to send email to %s", to)


async def send_welcome_email(to: str, username: str, temp_password: str) -> None:
    body = f"""
    <p>Welcome to Búvoli! Your account has been created.</p>
    <p><strong>Username:</strong> {username}</p>
    <p><strong>Temporary password:</strong> {temp_password}</p>
    <p>Please log in and change your password immediately.</p>
    """
    await send_email(to, "Welcome to Búvoli — your account details", body)


async def send_appointment_created(to: str, animal_name: str, appt_type: str, scheduled_date: str) -> None:
    body = f"""
    <p>A new <strong>{appt_type}</strong> appointment has been scheduled.</p>
    <p><strong>Animal:</strong> {animal_name}</p>
    <p><strong>Date:</strong> {scheduled_date}</p>
    <p>Please log in to Búvoli for details.</p>
    """
    await send_email(to, f"Búvoli — New {appt_type} appointment for {animal_name}", body)


async def send_appointment_status_changed(to: str, animal_name: str, appt_type: str, new_status: str) -> None:
    body = f"""
    <p>The <strong>{appt_type}</strong> appointment for <strong>{animal_name}</strong> has been updated to <strong>{new_status}</strong>.</p>
    <p>Please log in to Búvoli for details.</p>
    """
    await send_email(to, f"Búvoli — Appointment status changed: {new_status}", body)


async def send_pregnancy_confirmed(to: str, cow_name: str, expected_calving: str) -> None:
    body = f"""
    <p>Pregnancy confirmed for <strong>{cow_name}</strong>.</p>
    <p><strong>Expected calving date:</strong> {expected_calving}</p>
    """
    await send_email(to, f"Búvoli — Pregnancy confirmed: {cow_name}", body)


async def send_cow_recovery_complete(to: str, cow_name: str) -> None:
    body = f"""
    <p><strong>{cow_name}</strong> has completed the post-calving recovery period and is now available for breeding.</p>
    """
    await send_email(to, f"Búvoli — Recovery complete: {cow_name}", body)
