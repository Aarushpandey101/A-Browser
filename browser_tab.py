# browser_tab.py

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView


class BrowserTab(QWebEngineView):
    """Single browser tab bound to a specific QWebEngineProfile."""

    def __init__(self, profile: QWebEngineProfile, url: str = "about:blank") -> None:
        super().__init__()
        self._is_new_tab_page = False
        self.setPage(QWebEnginePage(profile, self))
        self.load(QUrl(url))

    def show_new_tab_page(self, html: str) -> None:
        self._is_new_tab_page = True
        self.setHtml(html, QUrl("https://newtab.local/"))

    def mark_as_web_page(self) -> None:
        self._is_new_tab_page = False

    @property
    def is_new_tab_page(self) -> bool:
        return self._is_new_tab_page
