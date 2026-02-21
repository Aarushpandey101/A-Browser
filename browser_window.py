# browser_window.py

from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QToolBar,
    QLineEdit,
    QMessageBox,
    QAction,
    QFileDialog,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QMenu,
)
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView

from browser_tab import BrowserTab
from database import BrowserDatabase
from download_manager import DownloadItemWidget
from profiles import ProfileManager


class BrowserWindow(QMainWindow):
    """Main browser window with advanced features."""

    def __init__(self) -> None:
        super().__init__()

        # Profile + DB
        self.profile_manager = ProfileManager("default")
        self.db = BrowserDatabase(str(self.profile_manager.database_path))

        self.setWindowTitle("SuperBrowser")
        self.resize(1300, 850)

        self._apply_dark_theme()

        self.adblock_enabled = True

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._update_url_bar)
        self.setCentralWidget(self.tabs)

        # Panels
        self._create_download_panel()
        self._create_devtools_panel()

        # Navbar
        self._create_navbar()

        # First tab
        self.add_new_tab()

    # ---------------- THEME ---------------- #

    def _apply_dark_theme(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        self.setPalette(palette)

    # ---------------- NAVBAR ---------------- #

    def _create_navbar(self) -> None:
        navbar = QToolBar()
        self.addToolBar(navbar)

        back_btn = QAction("←", self)
        back_btn.triggered.connect(lambda: self.current_browser().back())
        navbar.addAction(back_btn)

        forward_btn = QAction("→", self)
        forward_btn.triggered.connect(lambda: self.current_browser().forward())
        navbar.addAction(forward_btn)

        reload_btn = QAction("⟳", self)
        reload_btn.triggered.connect(lambda: self.current_browser().reload())
        navbar.addAction(reload_btn)

        home_btn = QAction("Home", self)
        home_btn.triggered.connect(
            lambda: self._navigate_to("https://www.google.com")
        )
        navbar.addAction(home_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self._handle_url_entered)
        navbar.addWidget(self.url_bar)

        new_tab_btn = QAction("+", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab())
        navbar.addAction(new_tab_btn)

        # AdBlock toggle
        self.adblock_btn = QAction("AdBlock: ON", self)
        self.adblock_btn.triggered.connect(self.toggle_adblock)
        navbar.addAction(self.adblock_btn)

        # DevTools toggle
        self.devtools_btn = QAction("DevTools", self)
        self.devtools_btn.triggered.connect(self.toggle_devtools)
        navbar.addAction(self.devtools_btn)

    # ---------------- TABS ---------------- #

    def add_new_tab(self, url: str | None = None) -> None:
        if not isinstance(url, str):
            url = "https://www.google.com"

        browser = BrowserTab(
            url,
            str(self.profile_manager.storage_path),
        )

        browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        browser.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(browser, pos)
        )

        index = self.tabs.addTab(browser, "New Tab")
        self.tabs.setCurrentIndex(index)

        browser.urlChanged.connect(self._update_url_bar)
        browser.loadFinished.connect(
            lambda _: self._on_page_loaded(browser)
        )
        browser.page().profile().downloadRequested.connect(
            self.handle_download
        )

    def close_tab(self, index: int) -> None:
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            QMessageBox.warning(self, "Warning", "Cannot close last tab.")

    def current_browser(self) -> BrowserTab:
        return self.tabs.currentWidget()

    # ---------------- NAVIGATION ---------------- #

    def _handle_url_entered(self) -> None:
        url = self.url_bar.text().strip()
        self._navigate_to(url)

    def _navigate_to(self, url: str) -> None:
        if not url.startswith("http"):
            url = f"https://{url}"
        self.current_browser().load(QUrl(url))

    def _update_url_bar(self) -> None:
        browser = self.current_browser()
        if browser:
            self.url_bar.setText(browser.url().toString())

    def _on_page_loaded(self, browser: BrowserTab) -> None:
        title = browser.page().title()
        url = browser.url().toString()

        if url.startswith("http"):
            self.db.add_history(url, title)

        index = self.tabs.indexOf(browser)
        if index != -1:
            self.tabs.setTabText(index, title)

    # ---------------- ADBLOCK ---------------- #

    def toggle_adblock(self) -> None:
        from browser_tab import BrowserTab

        self.adblock_enabled = not self.adblock_enabled
        BrowserTab.set_adblock_enabled(self.adblock_enabled)

        state = "ON" if self.adblock_enabled else "OFF"
        self.adblock_btn.setText(f"AdBlock: {state}")

        self.current_browser().reload()

    # ---------------- DEVTOOLS ---------------- #

    def _create_devtools_panel(self) -> None:
        self.devtools_dock = QDockWidget("DevTools", self)
        self.devtools_view = QWebEngineView()
        self.devtools_dock.setWidget(self.devtools_view)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.devtools_dock,
        )
        self.devtools_dock.hide()

    def toggle_devtools(self) -> None:
        browser = self.current_browser()
        if not browser:
            return

        if self.devtools_dock.isVisible():
            self.devtools_dock.hide()
        else:
            browser.page().setDevToolsPage(
                self.devtools_view.page()
            )
            self.devtools_dock.show()

    def _show_context_menu(self, browser, pos) -> None:
        menu = QMenu()

        inspect_action = QAction("Inspect Element", self)
        inspect_action.triggered.connect(
            lambda: self._inspect_element(browser)
        )

        menu.addAction(inspect_action)
        menu.exec(browser.mapToGlobal(pos))

    def _inspect_element(self, browser) -> None:
        self.devtools_dock.show()
        browser.page().setDevToolsPage(
            self.devtools_view.page()
        )

    # ---------------- DOWNLOADS ---------------- #

    def _create_download_panel(self) -> None:
        self.download_dock = QDockWidget("Downloads", self)
        self.download_container = QWidget()
        self.download_layout = QVBoxLayout()
        self.download_container.setLayout(self.download_layout)
        self.download_dock.setWidget(self.download_container)

        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self.download_dock,
        )
        self.download_dock.hide()

    def handle_download(self, download) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            download.downloadFileName(),
        )

        if not path:
            download.cancel()
            return

        if "\\" in path:
            directory, filename = path.rsplit("\\", 1)
        else:
            directory, filename = path.rsplit("/", 1)

        download.setDownloadDirectory(directory)
        download.setDownloadFileName(filename)
        download.accept()

        item = DownloadItemWidget(download)
        self.download_layout.addWidget(item)
        self.download_dock.show()