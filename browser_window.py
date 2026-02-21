# browser_window.py

import json
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from adblocker import AdBlocker
from browser_tab import BrowserTab
from database import BrowserDatabase
from download_manager import DownloadItemWidget
from profiles import ProfileManager


class BrowserWindow(QMainWindow):
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

        self.user_scripts: list[str] = []
        self.tab_groups: dict[BrowserTab, str] = {}
        self.adblock_enabled = True

        self.web_profile: QWebEngineProfile | None = None
        self.adblocker: AdBlocker | None = None

        self.setWindowTitle("SuperBrowser")
        self.resize(1440, 920)
        self._apply_modern_theme()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._show_tab_context_menu)
        self.setCentralWidget(self.tabs)

        self._create_download_panel()
        self._create_devtools_panel()
        self._create_navbar()
        self._create_bookmark_bar()
        self._create_menu_bar()

        self._load_extensions()
        self._rebuild_web_profile()

        restored_tabs = self.db.load_session() if not self.incognito_mode else []
        if restored_tabs:
            for url in restored_tabs[:10]:
                self.add_new_tab(url)
        else:
            self.add_new_tab("newtab://home")

    def _apply_modern_theme(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f4f7fc"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#111827"))
        self.setPalette(palette)

        self.setStyleSheet(
            """
            QMainWindow { background: #f4f7fc; }
            QToolBar {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-left: none;
                border-right: none;
                spacing: 8px;
                padding: 8px;
            }
            QToolButton {
                background: #f3f6ff;
                border: 1px solid #dbe3f2;
                border-radius: 12px;
                padding: 7px 12px;
                color: #0f172a;
            }
            QToolButton:hover { background: #e6eeff; }
            QLineEdit {
                border: 1px solid #d1d9ea;
                border-radius: 16px;
                padding: 9px 14px;
                background: #ffffff;
                min-width: 520px;
                color: #0f172a;
            }
            QComboBox, QPushButton {
                border: 1px solid #d1d9ea;
                border-radius: 12px;
                padding: 7px 12px;
                background: #ffffff;
                color: #0f172a;
            }
            QTabWidget::pane {
                border: 1px solid #dbe3f2;
                border-radius: 14px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #e9effb;
                border: 1px solid #dbe3f2;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 14px;
                margin-right: 4px;
            }
            QTabBar::tab:selected { background: #ffffff; }
            """
        )

    def _create_navbar(self) -> None:
        navbar = QToolBar("Navigation")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, navbar)

        for name, callback in [
            ("←", lambda: self.current_browser() and self.current_browser().back()),
            ("→", lambda: self.current_browser() and self.current_browser().forward()),
            ("⟳", lambda: self.current_browser() and self.current_browser().reload()),
            ("Home", lambda: self._navigate_to("newtab://home")),
        ]:
            action = QAction(name, self)
            action.triggered.connect(callback)
            navbar.addAction(action)

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

        self.incognito_btn = QPushButton("Incognito Off")
        self.incognito_btn.clicked.connect(self._toggle_incognito_mode)
        navbar.addWidget(self.incognito_btn)

        new_tab_action = QAction("+", self)
        new_tab_action.triggered.connect(lambda: self.add_new_tab("newtab://home"))
        navbar.addAction(new_tab_action)

    def _create_bookmark_bar(self) -> None:
        self.bookmark_bar = QToolBar("Bookmarks")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.bookmark_bar)
        self._refresh_bookmark_bar()

    def _create_menu_bar(self) -> None:
        tools_menu = self.menuBar().addMenu("Tools")

        items = [
            ("Add Bookmark", self._add_current_bookmark),
            ("Bookmark Manager", self._open_bookmark_manager),
            ("Split View", self._open_split_view),
            ("Reader Mode", self._enable_reader_mode),
            ("Translate Page", self._translate_current_page),
            ("Save Password", self._save_password),
            ("Autofill Password", self._autofill_password),
            ("Sync Export", self._export_sync_data),
            ("Sync Import", self._import_sync_data),
            ("Reload Extensions", self._load_extensions),
            ("Toggle DevTools", self.toggle_devtools),
        ]

        for label, fn in items:
            action = QAction(label, self)
            action.triggered.connect(fn)
            tools_menu.addAction(action)

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
            QMessageBox.warning(self, "Invalid", "Profile name cannot be empty.")
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
        self._reset_state_for_new_session()

    def _toggle_incognito_mode(self) -> None:
        self.incognito_mode = not self.incognito_mode
        self.incognito_btn.setText("Incognito On" if self.incognito_mode else "Incognito Off")
        self.profile_switcher.setEnabled(not self.incognito_mode)
        self.add_profile_btn.setEnabled(not self.incognito_mode)
        self._reset_state_for_new_session()

    def _reset_state_for_new_session(self) -> None:
        self._clear_all_tabs()
        self.tab_groups.clear()
        self._rebuild_web_profile()
        self._refresh_bookmark_bar()
        self.add_new_tab("newtab://home")

    def _clear_all_tabs(self) -> None:
        while self.tabs.count() > 0:
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if widget is not None:
                widget.deleteLater()

    def _rebuild_web_profile(self) -> None:
        if self.web_profile is not None:
            self.web_profile.deleteLater()
            self.web_profile = None

        if self.incognito_mode:
            self.web_profile = QWebEngineProfile(self)
        else:
            storage = str(self.profile_manager.storage_path)
            profile_name = f"profile-{self.current_profile}"
            self.web_profile = QWebEngineProfile(profile_name, self)
            self.web_profile.setPersistentStoragePath(storage)
            self.web_profile.setCachePath(str(self.profile_manager.storage_path / "cache"))

        self.adblocker = AdBlocker()
        self.adblocker.set_enabled(self.adblock_enabled)
        self.web_profile.setUrlRequestInterceptor(self.adblocker)

    def add_new_tab(self, url: str | None = None) -> None:
        target = url if isinstance(url, str) else "newtab://home"
        if self.web_profile is None:
            self._rebuild_web_profile()

        browser = BrowserTab(self.web_profile, "about:blank")
        if target == "newtab://home":
            browser.show_new_tab_page(self._new_tab_html())
        else:
            browser.mark_as_web_page()
            browser.load(QUrl(target))

        browser.urlChanged.connect(lambda _url, b=browser: self._on_tab_url_changed(b))
        browser.loadFinished.connect(lambda _ok, b=browser: self._on_page_loaded(b))
        browser.page().profile().downloadRequested.connect(self.handle_download)

        browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        browser.customContextMenuRequested.connect(
            lambda pos, b=browser: self._show_page_context_menu(b, pos)
        )

        idx = self.tabs.addTab(browser, "New Tab")
        self.tabs.setCurrentIndex(idx)

    def _new_tab_html(self) -> str:
        mode = "Incognito" if self.incognito_mode else f"Profile: {self.current_profile}"
        return f"""
        <html>
        <head>
          <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin:0; background:linear-gradient(135deg,#f8fbff,#eef4ff); color:#0f172a; }}
            .wrap {{ max-width:900px; margin:90px auto; text-align:center; }}
            .badge {{ display:inline-block; background:#0f172a; color:#fff; border-radius:999px; padding:9px 16px; font-size:13px; }}
            h1 {{ font-size:56px; margin:18px 0 10px; }}
            p {{ color:#475569; font-size:18px; }}
            .grid {{ margin-top:28px; display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; }}
            .card {{ background:#fff; border:1px solid #dbe3f2; border-radius:14px; padding:18px; box-shadow:0 10px 24px rgba(15,23,42,.06); }}
            a {{ text-decoration:none; color:#1d4ed8; font-weight:600; }}
          </style>
        </head>
        <body>
          <div class='wrap'>
            <span class='badge'>{mode}</span>
            <h1>SuperBrowser</h1>
            <p>Modern UI, profile switching, tab groups, and private mode.</p>
            <div class='grid'>
              <div class='card'><a href='https://www.google.com'>Google</a></div>
              <div class='card'><a href='https://github.com'>GitHub</a></div>
              <div class='card'><a href='https://news.ycombinator.com'>Hacker News</a></div>
              <div class='card'><a href='https://www.youtube.com'>YouTube</a></div>
            </div>
          </div>
        </body>
        </html>
        """

    def current_browser(self) -> BrowserTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, BrowserTab) else None

    def close_tab(self, index: int) -> None:
        if self.tabs.count() <= 1:
            QMessageBox.information(self, "Info", "Cannot close the last tab.")
            return

        widget = self.tabs.widget(index)
        if isinstance(widget, BrowserTab):
            self.tab_groups.pop(widget, None)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()

    def _handle_url_entered(self) -> None:
        self._navigate_to(self.url_bar.text().strip())

    def _navigate_to(self, text: str) -> None:
        browser = self.current_browser()
        if browser is None:
            return

        if text in {"newtab", "home", "newtab://home"}:
            browser.show_new_tab_page(self._new_tab_html())
            self.url_bar.setText("newtab://home")
            return

        if not text.startswith("http://") and not text.startswith("https://"):
            text = f"https://www.google.com/search?q={quote_plus(text)}"

        browser.mark_as_web_page()
        browser.load(QUrl(text))

    def _on_tab_url_changed(self, browser: BrowserTab) -> None:
        if browser != self.current_browser():
            return
        self.url_bar.setText("newtab://home" if browser.is_new_tab_page else browser.url().toString())

    def _on_current_tab_changed(self, _index: int) -> None:
        browser = self.current_browser()
        if browser is None:
            self.url_bar.clear()
            return
        self.url_bar.setText("newtab://home" if browser.is_new_tab_page else browser.url().toString())

    def _on_page_loaded(self, browser: BrowserTab) -> None:
        title = browser.page().title() or "New Tab"
        url = browser.url().toString()

        if not browser.is_new_tab_page and not self.incognito_mode and url.startswith("http"):
            self.db.add_history(url, title)

        idx = self.tabs.indexOf(browser)
        if idx == -1:
            return

        group = self.tab_groups.get(browser)
        tab_title = f"[{group}] {title}" if group else title
        self.tabs.setTabText(idx, tab_title)
        self.tabs.tabBar().setTabTextColor(idx, QColor(self.GROUP_COLORS.get(group, "#1f2937")))

        self._run_user_scripts(browser)

    def _show_tab_context_menu(self, pos) -> None:
        idx = self.tabs.tabBar().tabAt(pos)
        if idx < 0:
            return

        browser = self.tabs.widget(idx)
        if not isinstance(browser, BrowserTab):
            return

        menu = QMenu(self)
        group_menu = menu.addMenu("Add to Group")
        for group_name in self.GROUP_COLORS:
            action = QAction(group_name, self)
            action.triggered.connect(
                lambda _checked, b=browser, g=group_name: self._set_tab_group(b, g)
            )
            group_menu.addAction(action)

        clear_action = QAction("Remove from Group", self)
        clear_action.triggered.connect(lambda: self._set_tab_group(browser, None))
        menu.addAction(clear_action)
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def _set_tab_group(self, browser: BrowserTab, group: str | None) -> None:
        if group:
            self.tab_groups[browser] = group
        else:
            self.tab_groups.pop(browser, None)
        self._on_page_loaded(browser)

    def _show_page_context_menu(self, browser: BrowserTab, pos) -> None:
        menu = QMenu(self)
        inspect_action = QAction("Inspect Element", self)
        inspect_action.triggered.connect(lambda: self._inspect_element(browser))
        menu.addAction(inspect_action)
        menu.exec(browser.mapToGlobal(pos))

    def _refresh_bookmark_bar(self) -> None:
        self.bookmark_bar.clear()
        for _, title, url, folder, _, _ in self.db.get_bookmarks()[:12]:
            action = QAction(f"{folder}: {title}", self)
            action.triggered.connect(lambda _checked, target=url: self._navigate_to(target))
            self.bookmark_bar.addAction(action)

    def _add_current_bookmark(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return
        if browser.is_new_tab_page:
            QMessageBox.information(self, "Info", "Open a website before bookmarking.")
            return

        folder, ok = QInputDialog.getText(self, "Bookmark Folder", "Folder:", text="Favorites")
        if not ok:
            return
        self.db.add_bookmark(
            browser.page().title() or "Untitled",
            browser.url().toString(),
            folder.strip() or "Favorites",
        )
        self._refresh_bookmark_bar()

    def _open_bookmark_manager(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmark Manager")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Title", "URL"])
        tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        layout.addWidget(tree)

        grouped: dict[str, list[tuple]] = {}
        for row in self.db.get_bookmarks():
            grouped.setdefault(row[3], []).append(row)

        for folder, items in grouped.items():
            folder_item = QTreeWidgetItem([folder, ""])
            tree.addTopLevelItem(folder_item)
            for _, title, url, *_ in items:
                folder_item.addChild(QTreeWidgetItem([title, url]))

        buttons = QHBoxLayout()
        export_btn = QPushButton("Export")
        import_btn = QPushButton("Import")
        save_btn = QPushButton("Save")
        buttons.addWidget(export_btn)
        buttons.addWidget(import_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        export_btn.clicked.connect(self._export_bookmarks)
        import_btn.clicked.connect(self._import_bookmarks)

        def save_changes() -> None:
            bookmarks = []
            for i in range(tree.topLevelItemCount()):
                folder_item = tree.topLevelItem(i)
                folder = folder_item.text(0)
                for j in range(folder_item.childCount()):
                    child = folder_item.child(j)
                    bookmarks.append(
                        {
                            "title": child.text(0),
                            "url": child.text(1),
                            "folder": folder,
                            "position": j,
                        }
                    )
            self.db.replace_bookmarks(bookmarks)
            self._refresh_bookmark_bar()
            dialog.accept()

        save_btn.clicked.connect(save_changes)
        dialog.exec()

    def _export_bookmarks(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Bookmarks", "bookmarks.json")
        if not path:
            return

        payload = [
            {"title": t, "url": u, "folder": f, "position": p, "created_at": c}
            for _, t, u, f, p, c in self.db.get_bookmarks()
        ]
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _import_bookmarks(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Bookmarks", "", "JSON Files (*.json)")
        if not path:
            return

        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Import failed", "Invalid JSON file.")
            return

        if isinstance(payload, list):
            self.db.replace_bookmarks(payload)
            self._refresh_bookmark_bar()

    def _open_split_view(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return

        target = "https://www.google.com" if browser.is_new_tab_page else browser.url().toString()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = BrowserTab(self.web_profile, target)
        right = BrowserTab(self.web_profile, target)
        splitter.addWidget(left)
        splitter.addWidget(right)

        idx = self.tabs.addTab(splitter, "Split View")
        self.tabs.setCurrentIndex(idx)

    def _enable_reader_mode(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return
        browser.page().runJavaScript(
            """
            document.querySelectorAll('header, footer, nav, aside, iframe, .ads, [role="banner"], [role="navigation"]').forEach(e => e.remove());
            document.body.style.maxWidth = '900px';
            document.body.style.margin = '40px auto';
            document.body.style.fontSize = '20px';
            document.body.style.lineHeight = '1.75';
            """
        )

    def _translate_current_page(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return
        url = browser.url().toString()
        if not url.startswith("http"):
            return
        browser.mark_as_web_page()
        browser.load(QUrl(f"https://translate.google.com/translate?u={quote_plus(url)}"))

    def _save_password(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return

        site = urlparse(browser.url().toString()).netloc
        if not site:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Save Password")
        form = QFormLayout(dialog)

        user_input = QLineEdit()
        pass_input = QLineEdit()
        pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Site", QLineEdit(site))
        form.addRow("Username", user_input)
        form.addRow("Password", pass_input)

        save_btn = QPushButton("Save")
        form.addRow(save_btn)

        def persist() -> None:
            if user_input.text().strip() and pass_input.text():
                self.db.add_password(site, user_input.text().strip(), pass_input.text())
                dialog.accept()

        save_btn.clicked.connect(persist)
        dialog.exec()

    def _autofill_password(self) -> None:
        browser = self.current_browser()
        if browser is None:
            return

        site = urlparse(browser.url().toString()).netloc
        creds = self.db.get_password(site)
        if not creds:
            QMessageBox.information(self, "Autofill", "No saved credentials for this site.")
            return

        username, password = creds
        browser.page().runJavaScript(
            f"""
            const user = document.querySelector('input[type="email"], input[name*="user"], input[name*="email"], input[type="text"]');
            const pass = document.querySelector('input[type="password"]');
            if (user) user.value = {json.dumps(username)};
            if (pass) pass.value = {json.dumps(password)};
            """
        )

    def _export_sync_data(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Sync Export", "sync-data.json")
        if not path:
            return

        payload = {
            "profile": self.current_profile,
            "bookmarks": [
                {"title": t, "url": u, "folder": f, "position": p, "created_at": c}
                for _, t, u, f, p, c in self.db.get_bookmarks()
            ],
            "session": self.db.load_session(),
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _import_sync_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sync Import", "", "JSON Files (*.json)")
        if not path:
            return

        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Sync", "Invalid sync file.")
            return

        self.db.replace_bookmarks(payload.get("bookmarks", []))
        self.db.save_session(payload.get("session", []))
        self._refresh_bookmark_bar()

    def _load_extensions(self) -> None:
        self.user_scripts = []

        extensions_root = Path("extensions")
        user_scripts = extensions_root / "userscripts"
        manifests = extensions_root / "manifests"
        user_scripts.mkdir(parents=True, exist_ok=True)
        manifests.mkdir(parents=True, exist_ok=True)

        for script in user_scripts.glob("*.js"):
            self.user_scripts.append(script.read_text(encoding="utf-8"))

        manifest_count = len(list(manifests.glob("*/manifest.json")))
        self.statusBar().showMessage(
            f"Extensions loaded: {len(self.user_scripts)} userscripts, {manifest_count} manifests",
            5000,
        )

    def _run_user_scripts(self, browser: BrowserTab) -> None:
        for script in self.user_scripts:
            browser.page().runJavaScript(script)

    def closeEvent(self, event) -> None:
        if not self.incognito_mode:
            urls: list[str] = []
            for idx in range(self.tabs.count()):
                widget = self.tabs.widget(idx)
                if isinstance(widget, BrowserTab) and not widget.is_new_tab_page:
                    current_url = widget.url().toString()
                    if current_url:
                        urls.append(current_url)
            self.db.save_session(urls)
        super().closeEvent(event)

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

        self.download_layout.addWidget(DownloadItemWidget(download))
        self.download_dock.show()
