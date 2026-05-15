"""
Pydantic models for WhatsApp Cloud API webhook payloads.

These models parse the incoming webhook JSON from Meta's WhatsApp Cloud API.
Only the fields we actually use are modelled — everything else is ignored.
"""

from typing import Optional
from pydantic import BaseModel, Field


class WhatsAppProfile(BaseModel):
    name: str


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str


class WhatsAppText(BaseModel):
    body: str


class WhatsAppInteractiveButtonReply(BaseModel):
    id: str
    title: str


class WhatsAppInteractiveListReply(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class WhatsAppInteractive(BaseModel):
    type: str
    button_reply: Optional[WhatsAppInteractiveButtonReply] = None
    list_reply: Optional[WhatsAppInteractiveListReply] = None


class WhatsAppMessage(BaseModel):
    """A single inbound message from a user."""
    sender: str = Field(alias="from")  # "from" is a Python keyword
    id: str
    timestamp: str
    type: str
    text: Optional[WhatsAppText] = None
    interactive: Optional[WhatsAppInteractive] = None

    model_config = {"populate_by_name": True}

    def get_text(self) -> Optional[str]:
        """Extract user's text from any supported message type."""
        if self.type == "text" and self.text:
            return self.text.body
        if self.type == "interactive" and self.interactive:
            if self.interactive.button_reply:
                return self.interactive.button_reply.title
            if self.interactive.list_reply:
                return self.interactive.list_reply.title
        return None


class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[list[WhatsAppContact]] = None
    messages: Optional[list[WhatsAppMessage]] = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Top-level webhook payload from Meta."""
    object: str
    entry: list[WhatsAppEntry]


def parse_webhook(data: dict) -> Optional[tuple[str, str, str]]:
    """
    Parse incoming webhook payload.

    Returns: (phone_number, message_text, message_id) or None if not a user message.
    """
    try:
        payload = WhatsAppWebhookPayload(**data)

        if payload.object != "whatsapp_business_account":
            return None

        for entry in payload.entry:
            for change in entry.changes:
                value = change.value
                if value.messages:
                    for msg in value.messages:
                        text = msg.get_text()
                        if text:
                            return (msg.sender, text, msg.id)
        return None
    except Exception:
        return None
