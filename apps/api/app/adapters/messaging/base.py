"""Provider-agnostic messaging contract.

Every notification provider (Telegram, Bale, Eitaa, SMS.ir, or a future one)
implements this small interface. Delivery policy only depends on the error class,
never on the provider:

* ``TemporaryChannelError`` - the provider rejected the request without sending
  (429 / 5xx). Safe to retry with backoff.
* ``PermanentChannelError`` - bad recipient, blocked bot, unconfigured channel.
  Retrying cannot help.
* ``UnknownChannelError`` - timeout or transport failure after the request may
  have reached the provider. The result is unknown: never report success and
  never auto-retry, to avoid duplicate messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ChannelError(Exception):
    """Base class for channel adapters."""


class TemporaryChannelError(ChannelError):
    def __init__(self, message: str, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)


class PermanentChannelError(ChannelError):
    pass


class UnknownChannelError(ChannelError):
    """The request may or may not have been delivered."""


class ChannelNotConfigured(PermanentChannelError):
    def __init__(self, channel: str) -> None:
        super().__init__(f"channel_not_configured:{channel}")


@dataclass(frozen=True)
class DeliveryResult:
    #: Provider message id when the provider returns one (string for portability).
    message_id: str | None
    #: True when the message was simulated and must never be shown as delivered.
    is_mock: bool = False


class ChannelAdapter(Protocol):
    """One outbound provider account (a central bot or API key)."""

    channel: str

    @property
    def configured(self) -> bool: ...

    @property
    def mode(self) -> str: ...

    def send(
        self,
        recipient: str,
        text: str,
        keyboard: dict | None = None,
    ) -> DeliveryResult: ...

    def send_plain(self, recipient: str, text: str) -> DeliveryResult:
        """Send a plain-text message (no markup, no keyboard)."""
        ...
