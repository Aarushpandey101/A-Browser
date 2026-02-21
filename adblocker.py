# adblocker.py

from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt6.QtCore import QUrl


class AdBlocker(QWebEngineUrlRequestInterceptor):
    """Simple built-in toggleable ad blocker."""

    BLOCKED_KEYWORDS = [
        "doubleclick",
        "googlesyndication",
        "adservice",
        "adserver",
        "adsystem",
        "tracking",
        "analytics",
        "banner",
        "popup",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.enabled = True

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def interceptRequest(self, info) -> None:  # noqa
        if not self.enabled:
            return

        url: QUrl = info.requestUrl()
        url_str = url.toString().lower()

        if any(keyword in url_str for keyword in self.BLOCKED_KEYWORDS):
            info.block(True)