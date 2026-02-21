# browser_tab.py

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from adblocker import AdBlocker


class BrowserTab(QWebEngineView):
    """Browser tab with shared profile + toggleable adblock."""

    _shared_adblocker: AdBlocker | None = None
    _shared_profile: QWebEngineProfile | None = None

    def __init__(self, url: str, storage_path: str) -> None:
        super().__init__()

        if BrowserTab._shared_profile is None:
            BrowserTab._shared_profile = QWebEngineProfile(
                storage_path
            )

        if BrowserTab._shared_adblocker is None:
            BrowserTab._shared_adblocker = AdBlocker()
            BrowserTab._shared_profile.setUrlRequestInterceptor(
                BrowserTab._shared_adblocker
            )

        self.setPage(BrowserTab._shared_profile.newPage())
        self.load(QUrl(url))

    @classmethod
    def reset_profile(cls) -> None:
        cls._shared_profile = None
        cls._shared_adblocker = None

    @classmethod
    def set_adblock_enabled(cls, enabled: bool) -> None:
        if cls._shared_adblocker:
            cls._shared_adblocker.set_enabled(enabled)
