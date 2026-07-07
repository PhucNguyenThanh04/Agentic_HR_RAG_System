from fastapi_mail import FastMail, MessageSchema, MessageType
from src.core.configs.settings import settings


async def send_email(to: str, subject: str, body: str):
    message = MessageSchema(
        recipients=[to],
        subject=subject,
        body=body,
        subtype=MessageType.plain
    )

    fm = FastMail(settings.email_config)
    await fm.send_message(message)
