# browser_tab.py

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView

from adblocker import AdBlocker


class BrowserTab(QWebEngineView):
    """Browser tab with shared profile + toggleable adblock."""

    _shared_adblocker: AdBlocker | None = None
    _shared_profile: QWebEngineProfile | None = None
    _profile_key: tuple[str, bool] | None = None

    def __init__(self, url: str, storage_path: str, incognito: bool = False) -> None:
        super().__init__()
        self._ensure_profile(storage_path, incognito)
        self.setPage(BrowserTab._shared_profile.newPage())
        self.load(QUrl(url))

    @classmethod
    def _ensure_profile(cls, storage_path: str, incognito: bool) -> None:
        profile_key = (storage_path, incognito)
        if cls._shared_profile is not None and cls._profile_key == profile_key:
            return

        cls.reset_profile()

        if incognito:
            cls._shared_profile = QWebEngineProfile()
        else:
            cls._shared_profile = QWebEngineProfile(storage_path)
            cls._shared_profile.setPersistentStoragePath(storage_path)
            cls._shared_profile.setCachePath(f"{storage_path}/cache")

        cls._shared_adblocker = AdBlocker()
        cls._shared_profile.setUrlRequestInterceptor(cls._shared_adblocker)
        cls._profile_key = profile_key

    @classmethod
    def reset_profile(cls) -> None:
        cls._shared_profile = None
        cls._shared_adblocker = None
        cls._profile_key = None

    @classmethod
    def set_adblock_enabled(cls, enabled: bool) -> None:
        if cls._shared_adblocker:
            cls._shared_adblocker.set_enabled(enabled)
