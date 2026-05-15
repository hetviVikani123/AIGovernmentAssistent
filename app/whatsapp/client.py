"""
WhatsApp Cloud API client — handles sending messages back to users.

Supports:
  - Plain text messages
  - Interactive button replies (up to 3 buttons)
  - Interactive list messages
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
_HEADERS = {
    "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


async def send_text_message(to: str, body: str) -> bool:
    """
    Send a plain text message to a WhatsApp user.

    Args:
        to: Recipient phone number (with country code, no +)
        body: Message text (supports WhatsApp markdown: *bold*, _italic_)

    Returns:
        True if sent successfully, False otherwise.
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }

    return await _send_request(payload)


async def send_button_message(
    to: str,
    body: str,
    buttons: list[dict],
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> bool:
    """
    Send an interactive button message (max 3 buttons).

    Args:
        to: Recipient phone number
        body: Message body text
        buttons: List of dicts with {"id": "btn_1", "title": "Option 1"}
        header: Optional header text
        footer: Optional footer text

    Returns:
        True if sent successfully.
    """
    button_objects = [
        {
            "type": "reply",
            "reply": {"id": btn["id"], "title": btn["title"][:20]},  # WhatsApp 20-char limit
        }
        for btn in buttons[:3]  # WhatsApp max 3 buttons
    ]

    interactive = {
        "type": "button",
        "body": {"text": body},
        "action": {"buttons": button_objects},
    }

    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }

    return await _send_request(payload)


async def send_list_message(
    to: str,
    body: str,
    button_text: str,
    sections: list[dict],
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> bool:
    """
    Send an interactive list message.

    Args:
        to: Recipient phone number
        body: Message body text
        button_text: Text on the list CTA button
        sections: List of sections, each with "title" and "rows"
                  rows: [{"id": "row_1", "title": "Option", "description": "..."}]
        header: Optional header text
        footer: Optional footer text

    Returns:
        True if sent successfully.
    """
    interactive = {
        "type": "list",
        "body": {"text": body},
        "action": {
            "button": button_text,
            "sections": sections,
        },
    }

    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }

    return await _send_request(payload)


async def mark_as_read(message_id: str) -> bool:
    """Mark a message as read (shows blue ticks)."""
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    return await _send_request(payload)


async def _send_request(payload: dict) -> bool:
    """Send a request to the WhatsApp Cloud API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _BASE_URL,
                json=payload,
                headers=_HEADERS,
            )

            if response.status_code == 200:
                logger.info("Message sent successfully: %s", response.json())
                return True
            else:
                logger.error(
                    "WhatsApp API error %d: %s",
                    response.status_code,
                    response.text,
                )
                return False

    except httpx.TimeoutException:
        logger.error("WhatsApp API timeout")
        return False
    except Exception as e:
        logger.error("WhatsApp API exception: %s", str(e))
        return False
