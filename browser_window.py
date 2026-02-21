# browser_window.py

from pathlib import Path
from urllib.parse import quote_plus

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from browser_tab import BrowserTab
from database import BrowserDatabase
from download_manager import DownloadItemWidget
from profiles import ProfileManager


class BrowserWindow(QMainWindow):
    """Main browser window with profile switcher, tab groups, modern UI and incognito."""

    GROUP_COLORS = {
        "Work": "#4f46e5",
        "Study": "#0ea5e9",
        "Shopping": "#f97316",
        "Media": "#14b8a6",
        "Personal": "#a855f7",
    }

    def __init__(self) -> None:
        super().__init__()

        self.current_profile = "default"
        self.incognito_mode = False
        self.profile_manager = ProfileManager(self.current_profile)
        self.db = BrowserDatabase(str(self.profile_manager.database_path))
        self.tab_groups: dict[BrowserTab, str] = {}

        self.setWindowTitle("SuperBrowser")
        self.resize(1380, 900)
        self._apply_modern_theme()

        self.adblock_enabled = True

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._update_url_bar)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._show_tab_context_menu)
        self.setCentralWidget(self.tabs)

        self._create_download_panel()
        self._create_devtools_panel()
        self._create_navbar()

        self.add_new_tab("newtab://home")

    def _apply_modern_theme(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 247, 251))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(33, 37, 41))
        palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(33, 37, 41))
        self.setPalette(palette)

        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7fb; }
            QToolBar {
                background: #ffffff;
                border: none;
                spacing: 6px;
                padding: 8px;
            }
            QToolButton {
                background: #eef2ff;
                border: 1px solid #dde3f0;
                border-radius: 12px;
                padding: 6px 10px;
            }
            QToolButton:hover { background: #dbeafe; }
            QLineEdit {
                border: 1px solid #d7deed;
                border-radius: 16px;
                padding: 8px 12px;
                background: #ffffff;
                min-width: 380px;
            }
            QComboBox {
                border: 1px solid #d7deed;
                border-radius: 12px;
                padding: 5px 8px;
                background: #ffffff;
                min-width: 130px;
            }
            QPushButton {
                border: 1px solid #d7deed;
                border-radius: 12px;
                padding: 6px 10px;
                background: #ffffff;
            }
            QPushButton:hover { background: #eef2ff; }
            QTabWidget::pane {
                border: 1px solid #d7deed;
                border-radius: 14px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #e9edf7;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 7px 12px;
                margin-right: 4px;
            }
            QTabBar::tab:selected { background: #ffffff; }
            """
        )

    def _create_navbar(self) -> None:
        navbar = QToolBar()
        self.addToolBar(navbar)

        back_btn = QAction("←", self)
        back_btn.triggered.connect(lambda: self.current_browser() and self.current_browser().back())
        navbar.addAction(back_btn)

        forward_btn = QAction("→", self)
        forward_btn.triggered.connect(lambda: self.current_browser() and self.current_browser().forward())
        navbar.addAction(forward_btn)

        reload_btn = QAction("⟳", self)
        reload_btn.triggered.connect(lambda: self.current_browser() and self.current_browser().reload())
        navbar.addAction(reload_btn)

        home_btn = QAction("Home", self)
        home_btn.triggered.connect(lambda: self._navigate_to("newtab://home"))
        navbar.addAction(home_btn)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search Google or type a URL")
        self.url_bar.returnPressed.connect(self._handle_url_entered)
        navbar.addWidget(self.url_bar)

        self.profile_switcher = QComboBox()
        self._refresh_profiles()
        self.profile_switcher.currentTextChanged.connect(self._switch_profile)
        navbar.addWidget(self.profile_switcher)

        self.add_profile_btn = QPushButton("+ Profile")
        self.add_profile_btn.clicked.connect(self._create_profile)
        navbar.addWidget(self.add_profile_btn)

        self.incognito_btn = QPushButton("Incognito: OFF")
        self.incognito_btn.clicked.connect(self._toggle_incognito_mode)
        navbar.addWidget(self.incognito_btn)

        new_tab_btn = QAction("+", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab("newtab://home"))
        navbar.addAction(new_tab_btn)

        self.adblock_btn = QAction("AdBlock: ON", self)
        self.adblock_btn.triggered.connect(self.toggle_adblock)
        navbar.addAction(self.adblock_btn)

        self.devtools_btn = QAction("DevTools", self)
        self.devtools_btn.triggered.connect(self.toggle_devtools)
        navbar.addAction(self.devtools_btn)

    def _refresh_profiles(self) -> None:
        base = Path(ProfileManager.BASE_DIR)
        base.mkdir(parents=True, exist_ok=True)
        profiles = sorted([p.name for p in base.iterdir() if p.is_dir()])
        if "default" not in profiles:
            profiles.insert(0, "default")

        self.profile_switcher.blockSignals(True)
        self.profile_switcher.clear()
        self.profile_switcher.addItems(profiles)
        self.profile_switcher.setCurrentText(self.current_profile)
        self.profile_switcher.blockSignals(False)

    def _create_profile(self) -> None:
        profile_name, ok = QInputDialog.getText(self, "Create Profile", "Profile name:")
        if not ok:
            return

        profile_name = profile_name.strip()
        if not profile_name:
            QMessageBox.warning(self, "Invalid Profile", "Profile name cannot be empty.")
            return

        ProfileManager(profile_name)
        self._refresh_profiles()
        self._switch_profile(profile_name)

    def _switch_profile(self, profile_name: str) -> None:
        if not profile_name or profile_name == self.current_profile:
            return

        self.current_profile = profile_name
        self.profile_manager = ProfileManager(profile_name)
        self.db = BrowserDatabase(str(self.profile_manager.database_path))

        BrowserTab.reset_profile()
        self.tab_groups.clear()
        self.tabs.clear()
        self.add_new_tab("newtab://home")

    def _toggle_incognito_mode(self) -> None:
        self.incognito_mode = not self.incognito_mode
        self.incognito_btn.setText(f"Incognito: {'ON' if self.incognito_mode else 'OFF'}")
        self.profile_switcher.setEnabled(not self.incognito_mode)
        self.add_profile_btn.setEnabled(not self.incognito_mode)

        BrowserTab.reset_profile()
        self.tab_groups.clear()
        self.tabs.clear()
        self.add_new_tab("newtab://home")

    def add_new_tab(self, url: str | None = None) -> None:
        target = url if isinstance(url, str) else "newtab://home"
        browser_url = "about:blank" if target == "newtab://home" else target

        browser = BrowserTab(
            browser_url,
            str(self.profile_manager.storage_path),
            incognito=self.incognito_mode,
        )

        if target == "newtab://home":
            browser.setHtml(self._new_tab_html())

        browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        browser.customContextMenuRequested.connect(lambda pos: self._show_context_menu(browser, pos))

        index = self.tabs.addTab(browser, "New Tab")
        self.tabs.setCurrentIndex(index)

        browser.urlChanged.connect(self._update_url_bar)
        browser.loadFinished.connect(lambda _: self._on_page_loaded(browser))
        browser.page().profile().downloadRequested.connect(self.handle_download)

    def _new_tab_html(self) -> str:
        mode_label = "Incognito" if self.incognito_mode else f"Profile: {self.current_profile}"
        sub_text = "No browsing history will be saved in this mode." if self.incognito_mode else "Fast browsing with profiles, grouped tabs, adblock and developer tools."
        return f"""
        <html>
        <head>
            <style>
                body {{font-family: Arial, sans-serif; background: linear-gradient(135deg, #f6f8ff, #eefafc); color: #111827; margin:0;}}
                .wrap {{max-width: 760px; margin: 80px auto; text-align: center;}}
                .badge {{display:inline-block; background:#1f2937; color:#fff; border-radius:999px; padding:8px 14px; font-size:13px;}}
                h1 {{font-size: 52px; margin: 16px 0 8px;}}
                p {{color: #4b5563;}}
                .grid {{display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; margin-top: 24px;}}
                .card {{background:#fff; border-radius:16px; padding:18px; box-shadow: 0 8px 24px rgba(0,0,0,0.06);}}
                a {{text-decoration:none; color:#1d4ed8; font-weight:bold;}}
            </style>
        </head>
        <body>
            <div class="wrap">
                <span class="badge">{mode_label}</span>
                <h1>SuperBrowser</h1>
                <p>{sub_text}</p>
                <div class="grid">
                    <div class="card"><a href="https://www.google.com">Google</a></div>
                    <div class="card"><a href="https://github.com">GitHub</a></div>
                    <div class="card"><a href="https://news.ycombinator.com">Hacker News</a></div>
                    <div class="card"><a href="https://www.youtube.com">YouTube</a></div>
                </div>
            </div>
        </body>
        </html>
        """

    def close_tab(self, index: int) -> None:
        if self.tabs.count() <= 1:
            QMessageBox.warning(self, "Warning", "Cannot close last tab.")
            return

        browser = self.tabs.widget(index)
        if isinstance(browser, BrowserTab):
            self.tab_groups.pop(browser, None)
        self.tabs.removeTab(index)

    def current_browser(self) -> BrowserTab | None:
        browser = self.tabs.currentWidget()
        return browser if isinstance(browser, BrowserTab) else None

    def _handle_url_entered(self) -> None:
        self._navigate_to(self.url_bar.text().strip())

    def _navigate_to(self, url: str) -> None:
        browser = self.current_browser()
        if browser is None:
            return

        if url in {"newtab", "newtab://home", "home"}:
            browser.setHtml(self._new_tab_html())
            return

        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://www.google.com/search?q={quote_plus(url)}"

        browser.load(QUrl(url))

    def _update_url_bar(self) -> None:
        browser = self.current_browser()
        self.url_bar.setText(browser.url().toString() if browser else "")

    def _on_page_loaded(self, browser: BrowserTab) -> None:
        title = browser.page().title() or "New Tab"
        url = browser.url().toString()

        if not self.incognito_mode and url.startswith("http"):
            self.db.add_history(url, title)

        index = self.tabs.indexOf(browser)
        if index == -1:
            return

        group = self.tab_groups.get(browser)
        self.tabs.setTabText(index, f"[{group}] {title}" if group else title)
        self._paint_group(index, group)

    def _show_tab_context_menu(self, pos) -> None:
        index = self.tabs.tabBar().tabAt(pos)
        if index < 0:
            return

        browser = self.tabs.widget(index)
        if not isinstance(browser, BrowserTab):
            return

        menu = QMenu(self)
        group_menu = menu.addMenu("Add to Group")
        for group_name in self.GROUP_COLORS:
            action = QAction(group_name, self)
            action.triggered.connect(
                lambda _checked, b=browser, g=group_name: self._assign_tab_group(b, g)
            )
            group_menu.addAction(action)

        clear_action = QAction("Remove from Group", self)
        clear_action.triggered.connect(lambda: self._assign_tab_group(browser, None))
        menu.addAction(clear_action)
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def _assign_tab_group(self, browser: BrowserTab, group_name: str | None) -> None:
        if group_name:
            self.tab_groups[browser] = group_name
        else:
            self.tab_groups.pop(browser, None)
        self._on_page_loaded(browser)

    def _paint_group(self, index: int, group: str | None) -> None:
        color = QColor(self.GROUP_COLORS[group]) if group else QColor("#1f2937")
        self.tabs.tabBar().setTabTextColor(index, color)

    def toggle_adblock(self) -> None:
        self.adblock_enabled = not self.adblock_enabled
        BrowserTab.set_adblock_enabled(self.adblock_enabled)
        state = "ON" if self.adblock_enabled else "OFF"
        self.adblock_btn.setText(f"AdBlock: {state}")
        if self.current_browser():
            self.current_browser().reload()

    def _create_devtools_panel(self) -> None:
        self.devtools_dock = QDockWidget("DevTools", self)
        self.devtools_view = QWebEngineView()
        self.devtools_dock.setWidget(self.devtools_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.devtools_dock)
        self.devtools_dock.hide()

    def toggle_devtools(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return

        if self.devtools_dock.isVisible():
            self.devtools_dock.hide()
            return

        browser.page().setDevToolsPage(self.devtools_view.page())
        self.devtools_dock.show()

    def _show_context_menu(self, browser: BrowserTab, pos) -> None:
        menu = QMenu()
        inspect_action = QAction("Inspect Element", self)
        inspect_action.triggered.connect(lambda: self._inspect_element(browser))
        menu.addAction(inspect_action)
        menu.exec(browser.mapToGlobal(pos))

    def _inspect_element(self, browser: BrowserTab) -> None:
        self.devtools_dock.show()
        browser.page().setDevToolsPage(self.devtools_view.page())

    def _create_download_panel(self) -> None:
        self.download_dock = QDockWidget("Downloads", self)
        self.download_container = QWidget()
        self.download_layout = QVBoxLayout()
        self.download_container.setLayout(self.download_layout)
        self.download_dock.setWidget(self.download_container)

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.download_dock)
        self.download_dock.hide()

    def handle_download(self, download) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save File", download.downloadFileName())
        if not path:
            download.cancel()
            return

        separator = "\\" if "\\" in path else "/"
        directory, filename = path.rsplit(separator, 1)

        download.setDownloadDirectory(directory)
        download.setDownloadFileName(filename)
        download.accept()

        item = DownloadItemWidget(download)
        self.download_layout.addWidget(item)
        self.download_dock.show()
