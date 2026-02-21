# browser_window.py

import json
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QPalette
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
    QListWidget,
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
        self.tab_groups: dict[BrowserTab, str] = {}
        self.user_scripts: list[str] = []

        self.setWindowTitle("SuperBrowser")
        self.resize(1420, 900)
        self._apply_modern_theme()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._update_url_bar)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._show_tab_context_menu)
        self.setCentralWidget(self.tabs)

        self._create_download_panel()
        self._create_devtools_panel()
        self._create_navbar()
        self._create_bookmark_bar()
        self._create_menu_bar()

        self._load_extensions()
        restored_tabs = self.db.load_session()
        if restored_tabs:
            for url in restored_tabs[:10]:
                self.add_new_tab(url)
        else:
            self.add_new_tab("newtab://home")

    def _apply_modern_theme(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 247, 251))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(33, 37, 41))
        self.setPalette(palette)
        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7fb; }
            QToolBar { background: #ffffff; border: none; spacing: 6px; padding: 8px; }
            QToolButton { background: #eef2ff; border: 1px solid #dde3f0; border-radius: 12px; padding: 6px 10px; }
            QToolButton:hover { background: #dbeafe; }
            QLineEdit { border: 1px solid #d7deed; border-radius: 16px; padding: 8px 12px; background: #ffffff; min-width: 380px; }
            QPushButton, QComboBox { border: 1px solid #d7deed; border-radius: 12px; padding: 6px 10px; background: #ffffff; }
            QTabWidget::pane { border: 1px solid #d7deed; border-radius: 14px; background: #ffffff; }
            QTabBar::tab { background: #e9edf7; border-top-left-radius: 10px; border-top-right-radius: 10px; padding: 7px 12px; margin-right: 4px; }
            QTabBar::tab:selected { background: #ffffff; }
            """
        )

    def _create_navbar(self) -> None:
        navbar = QToolBar()
        self.addToolBar(navbar)

        actions = [
            ("←", lambda: self.current_browser() and self.current_browser().back()),
            ("→", lambda: self.current_browser() and self.current_browser().forward()),
            ("⟳", lambda: self.current_browser() and self.current_browser().reload()),
            ("Home", lambda: self._navigate_to("newtab://home")),
        ]
        for name, fn in actions:
            action = QAction(name, self)
            action.triggered.connect(fn)
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

        self.incognito_btn = QPushButton("Incognito: OFF")
        self.incognito_btn.clicked.connect(self._toggle_incognito_mode)
        navbar.addWidget(self.incognito_btn)

        new_tab_btn = QAction("+", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab("newtab://home"))
        navbar.addAction(new_tab_btn)

        self.vertical_tabs_btn = QPushButton("Vertical Tabs: OFF")
        self.vertical_tabs_btn.clicked.connect(self._toggle_vertical_tabs)
        navbar.addWidget(self.vertical_tabs_btn)

    def _create_bookmark_bar(self) -> None:
        self.bookmark_bar = QToolBar("Bookmarks")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.bookmark_bar)
        self._refresh_bookmark_bar()

    def _create_menu_bar(self) -> None:
        tools_menu = self.menuBar().addMenu("Tools")

        bookmark_manager = QAction("Bookmark Manager", self)
        bookmark_manager.triggered.connect(self._open_bookmark_manager)
        tools_menu.addAction(bookmark_manager)

        add_bookmark = QAction("Add Bookmark", self)
        add_bookmark.triggered.connect(self._add_current_bookmark)
        tools_menu.addAction(add_bookmark)

        tools_menu.addSeparator()

        split_view = QAction("Split View", self)
        split_view.triggered.connect(self._open_split_view)
        tools_menu.addAction(split_view)

        reader_mode = QAction("Reader Mode", self)
        reader_mode.triggered.connect(self._enable_reader_mode)
        tools_menu.addAction(reader_mode)

        translate_page = QAction("Translate Page", self)
        translate_page.triggered.connect(self._translate_current_page)
        tools_menu.addAction(translate_page)

        tools_menu.addSeparator()

        save_password = QAction("Save Password", self)
        save_password.triggered.connect(self._save_password)
        tools_menu.addAction(save_password)

        autofill_password = QAction("Autofill Password", self)
        autofill_password.triggered.connect(self._autofill_password)
        tools_menu.addAction(autofill_password)

        tools_menu.addSeparator()

        export_sync = QAction("Sync Export", self)
        export_sync.triggered.connect(self._export_sync_data)
        tools_menu.addAction(export_sync)

        import_sync = QAction("Sync Import", self)
        import_sync.triggered.connect(self._import_sync_data)
        tools_menu.addAction(import_sync)

        extension_menu = self.menuBar().addMenu("Extensions")
        reload_extensions = QAction("Reload Extensions", self)
        reload_extensions.triggered.connect(self._load_extensions)
        extension_menu.addAction(reload_extensions)

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
        self._reset_browser_state()

    def _toggle_incognito_mode(self) -> None:
        self.incognito_mode = not self.incognito_mode
        self.incognito_btn.setText(f"Incognito: {'ON' if self.incognito_mode else 'OFF'}")
        self.profile_switcher.setEnabled(not self.incognito_mode)
        self.add_profile_btn.setEnabled(not self.incognito_mode)
        self._reset_browser_state()

    def _toggle_vertical_tabs(self) -> None:
        vertical = self.tabs.tabPosition() != QTabWidget.TabPosition.West
        self.tabs.setTabPosition(QTabWidget.TabPosition.West if vertical else QTabWidget.TabPosition.North)
        self.vertical_tabs_btn.setText(f"Vertical Tabs: {'ON' if vertical else 'OFF'}")

    def _reset_browser_state(self) -> None:
        BrowserTab.reset_profile()
        self.tab_groups.clear()
        self.tabs.clear()
        self._refresh_bookmark_bar()
        self.add_new_tab("newtab://home")

    def add_new_tab(self, url: str | None = None) -> None:
        target = url if isinstance(url, str) else "newtab://home"
        browser_url = "about:blank" if target == "newtab://home" else target
        browser = BrowserTab(browser_url, str(self.profile_manager.storage_path), self.incognito_mode)

        if target == "newtab://home":
            browser.setHtml(self._new_tab_html())

        browser.urlChanged.connect(self._update_url_bar)
        browser.loadFinished.connect(lambda _: self._on_page_loaded(browser))
        browser.page().profile().downloadRequested.connect(self.handle_download)
        browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        browser.customContextMenuRequested.connect(lambda pos: self._show_context_menu(browser, pos))

        idx = self.tabs.addTab(browser, "New Tab")
        self.tabs.setCurrentIndex(idx)

    def _new_tab_html(self) -> str:
        status = "Incognito" if self.incognito_mode else f"Profile: {self.current_profile}"
        return f"""
        <html><body style='font-family:Arial;background:linear-gradient(135deg,#f6f8ff,#eefafc);'>
            <div style='max-width:760px;margin:70px auto;text-align:center;'>
                <span style='background:#111827;color:#fff;padding:8px 14px;border-radius:999px'>{status}</span>
                <h1 style='font-size:52px'>SuperBrowser</h1>
                <p>Custom New Tab with fast links and modern browser tools.</p>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>
                    <a href='https://google.com'>Google</a><a href='https://github.com'>GitHub</a>
                    <a href='https://news.ycombinator.com'>Hacker News</a><a href='https://youtube.com'>YouTube</a>
                </div>
            </div>
        </body></html>
        """

    def current_browser(self) -> BrowserTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, BrowserTab) else None

    def close_tab(self, index: int) -> None:
        if self.tabs.count() <= 1:
            return
        browser = self.tabs.widget(index)
        if isinstance(browser, BrowserTab):
            self.tab_groups.pop(browser, None)
        self.tabs.removeTab(index)

    def _handle_url_entered(self) -> None:
        self._navigate_to(self.url_bar.text().strip())

    def _navigate_to(self, text: str) -> None:
        browser = self.current_browser()
        if not browser:
            return
        if text in {"home", "newtab", "newtab://home"}:
            browser.setHtml(self._new_tab_html())
            return
        if not text.startswith("http://") and not text.startswith("https://"):
            text = f"https://www.google.com/search?q={quote_plus(text)}"
        browser.load(QUrl(text))

    def _update_url_bar(self) -> None:
        browser = self.current_browser()
        self.url_bar.setText(browser.url().toString() if browser else "")

    def _on_page_loaded(self, browser: BrowserTab) -> None:
        title = browser.page().title() or "New Tab"
        url = browser.url().toString()
        if not self.incognito_mode and url.startswith("http"):
            self.db.add_history(url, title)
        index = self.tabs.indexOf(browser)
        if index < 0:
            return
        group = self.tab_groups.get(browser)
        self.tabs.setTabText(index, f"[{group}] {title}" if group else title)
        self.tabs.tabBar().setTabTextColor(index, QColor(self.GROUP_COLORS.get(group, "#1f2937")))
        self._run_user_scripts(browser)

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
            action.triggered.connect(lambda _checked, b=browser, g=group_name: self._assign_tab_group(b, g))
            group_menu.addAction(action)
        clear_action = QAction("Remove from Group", self)
        clear_action.triggered.connect(lambda: self._assign_tab_group(browser, None))
        menu.addAction(clear_action)
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def _assign_tab_group(self, browser: BrowserTab, group: str | None) -> None:
        if group:
            self.tab_groups[browser] = group
        else:
            self.tab_groups.pop(browser, None)
        self._on_page_loaded(browser)

    def _refresh_bookmark_bar(self) -> None:
        self.bookmark_bar.clear()
        for _, title, url, folder, _, _ in self.db.get_bookmarks()[:15]:
            action = QAction(f"{folder}: {title}", self)
            action.triggered.connect(lambda _checked, target=url: self._navigate_to(target))
            self.bookmark_bar.addAction(action)

    def _add_current_bookmark(self) -> None:
        browser = self.current_browser()
        if not browser:
            return
        folder, ok = QInputDialog.getText(self, "Bookmark Folder", "Folder:", text="Favorites")
        if not ok:
            return
        self.db.add_bookmark(browser.page().title() or "Untitled", browser.url().toString(), folder.strip() or "Favorites")
        self._refresh_bookmark_bar()

    def _open_bookmark_manager(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmark Manager")
        layout = QVBoxLayout(dialog)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Title", "URL"])
        tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        layout.addWidget(tree)
        grouped: dict[str, list[tuple]] = {}
        for row in self.db.get_bookmarks():
            grouped.setdefault(row[3], []).append(row)
        for folder, items in grouped.items():
            root = QTreeWidgetItem([folder, ""])
            tree.addTopLevelItem(root)
            for _, title, url, *_ in items:
                child = QTreeWidgetItem([title, url])
                root.addChild(child)
        button_row = QHBoxLayout()
        export_btn = QPushButton("Export")
        import_btn = QPushButton("Import")
        save_btn = QPushButton("Save")
        button_row.addWidget(export_btn)
        button_row.addWidget(import_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        export_btn.clicked.connect(self._export_bookmarks)
        import_btn.clicked.connect(self._import_bookmarks)

        def save_tree() -> None:
            out = []
            for i in range(tree.topLevelItemCount()):
                folder_item = tree.topLevelItem(i)
                folder = folder_item.text(0)
                for j in range(folder_item.childCount()):
                    child = folder_item.child(j)
                    out.append({"title": child.text(0), "url": child.text(1), "folder": folder, "position": j})
            self.db.replace_bookmarks(out)
            self._refresh_bookmark_bar()
            dialog.accept()

        save_btn.clicked.connect(save_tree)
        dialog.exec()

    def _export_bookmarks(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Bookmarks", "bookmarks.json")
        if not path:
            return
        bookmarks = [
            {"title": t, "url": u, "folder": f, "position": p, "created_at": c}
            for _, t, u, f, p, c in self.db.get_bookmarks()
        ]
        Path(path).write_text(json.dumps(bookmarks, indent=2), encoding="utf-8")

    def _import_bookmarks(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Bookmarks", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            bookmarks = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(bookmarks, list):
                self.db.replace_bookmarks(bookmarks)
                self._refresh_bookmark_bar()
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Import failed", "Invalid bookmark JSON.")

    def _open_split_view(self) -> None:
        browser = self.current_browser()
        if not browser:
            return
        target = browser.url().toString() or "https://google.com"
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = BrowserTab(target, str(self.profile_manager.storage_path), self.incognito_mode)
        right = BrowserTab(target, str(self.profile_manager.storage_path), self.incognito_mode)
        splitter.addWidget(left)
        splitter.addWidget(right)
        idx = self.tabs.addTab(splitter, "Split View")
        self.tabs.setCurrentIndex(idx)

    def _enable_reader_mode(self) -> None:
        browser = self.current_browser()
        if not browser:
            return
        script = """
        document.querySelectorAll('header, footer, nav, aside, iframe, .ads, [role="banner"], [role="navigation"]').forEach(e=>e.remove());
        document.body.style.maxWidth='900px';
        document.body.style.margin='40px auto';
        document.body.style.fontSize='20px';
        document.body.style.lineHeight='1.7';
        """
        browser.page().runJavaScript(script)

    def _translate_current_page(self) -> None:
        browser = self.current_browser()
        if not browser:
            return
        url = browser.url().toString()
        if not url.startswith("http"):
            return
        translated = f"https://translate.google.com/translate?u={quote_plus(url)}"
        browser.load(QUrl(translated))

    def _save_password(self) -> None:
        browser = self.current_browser()
        if not browser:
            return
        site = urlparse(browser.url().toString()).netloc
        dialog = QDialog(self)
        dialog.setWindowTitle("Save Password")
        form = QFormLayout(dialog)
        username = QLineEdit()
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Site", QLineEdit(site))
        form.addRow("Username", username)
        form.addRow("Password", password)
        save_btn = QPushButton("Save")
        form.addRow(save_btn)

        def persist() -> None:
            if username.text().strip() and password.text():
                self.db.add_password(site, username.text().strip(), password.text())
                dialog.accept()

        save_btn.clicked.connect(persist)
        dialog.exec()

    def _autofill_password(self) -> None:
        browser = self.current_browser()
        if not browser:
            return
        site = urlparse(browser.url().toString()).netloc
        creds = self.db.get_password(site)
        if not creds:
            QMessageBox.information(self, "Autofill", "No saved credentials for this site.")
            return
        username, password = creds
        script = f"""
        const user=document.querySelector('input[type="email"], input[name*="user"], input[name*="email"], input[type="text"]');
        const pass=document.querySelector('input[type="password"]');
        if(user) user.value={json.dumps(username)};
        if(pass) pass.value={json.dumps(password)};
        """
        browser.page().runJavaScript(script)

    def _export_sync_data(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Sync Export", "sync-data.json")
        if not path:
            return
        payload = {
            "bookmarks": [
                {"title": t, "url": u, "folder": f, "position": p, "created_at": c}
                for _, t, u, f, p, c in self.db.get_bookmarks()
            ],
            "session": self.db.load_session(),
            "profile": self.current_profile,
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
        ext_root = Path("extensions")
        user_script_dir = ext_root / "userscripts"
        manifest_dir = ext_root / "manifests"
        user_script_dir.mkdir(parents=True, exist_ok=True)
        manifest_dir.mkdir(parents=True, exist_ok=True)

        for script in user_script_dir.glob("*.js"):
            self.user_scripts.append(script.read_text(encoding="utf-8"))

        # lightweight manifest support: discover and show loaded count
        manifests = list(manifest_dir.glob("*/manifest.json"))
        self.statusBar().showMessage(
            f"Extensions loaded: {len(self.user_scripts)} user scripts, {len(manifests)} manifests",
            5000,
        )

    def _run_user_scripts(self, browser: BrowserTab) -> None:
        if not self.user_scripts:
            return
        for script in self.user_scripts:
            browser.page().runJavaScript(script)

    def closeEvent(self, event) -> None:
        if not self.incognito_mode:
            urls = []
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if isinstance(tab, BrowserTab):
                    url = tab.url().toString()
                    if url:
                        urls.append(url)
            self.db.save_session(urls)
        super().closeEvent(event)

    def _create_devtools_panel(self) -> None:
        self.devtools_dock = QDockWidget("DevTools", self)
        self.devtools_view = QWebEngineView()
        self.devtools_dock.setWidget(self.devtools_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.devtools_dock)
        self.devtools_dock.hide()

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
        self.download_layout.addWidget(DownloadItemWidget(download))
        self.download_dock.show()
