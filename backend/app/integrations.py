"""Optional authorized messaging integrations.

Implementations must verify official webhooks and only process messages that
the user explicitly sends to the configured business account or bot. No
private inbox or group scraping is supported. No adapter is instantiated by
default; configure credentials through deployment secrets before enabling one.
"""
from typing import Protocol

def build_safety_response(result: dict) -> str:
    """Create a short educational reply; never recommend trades or products."""
    risk = result.get('risk', 'UNKNOWN')
    explanation = result.get('explanation', 'We could not determine whether this message is genuine.')
    steps = result.get('verification_steps') or [
        'Pause and verify the sender through an official contact channel you find independently.',
        'Never share passwords, PINs, OTPs, or recovery phrases.',
    ]
    lines = [f"RakshakAI safety check: {risk} risk indicators.", str(explanation)[:500], 'Safer steps:']
    lines.extend(f'• {str(step)[:240]}' for step in steps[:3])
    lines.append('This is general safety information, not investment or trading advice. A low-risk result does not prove a message is safe.')
    return '\n'.join(lines)

class WhatsAppAdapter(Protocol):
    async def verifyWebhook(self, request) -> bool: ...
    async def receiveAuthorizedMessage(self, payload: dict) -> dict: ...
    async def sendSafetyResponse(self, recipient: str, response: str) -> None: ...
class TelegramAdapter(Protocol):
    async def verifyWebhook(self, request) -> bool: ...
    async def receiveAuthorizedMessage(self, payload: dict) -> dict: ...
    async def sendSafetyResponse(self, chat_id: str, response: str) -> None: ...
# Provider adapters are intentionally absent and integrations remain disabled.
