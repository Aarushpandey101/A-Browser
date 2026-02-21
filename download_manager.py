# download_manager.py

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
)
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest


class DownloadItemWidget(QWidget):
    """Represents a single download with progress bar."""

    def __init__(self, download: QWebEngineDownloadRequest) -> None:
        super().__init__()

        self.download = download

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label = QLabel(download.downloadFileName())
        self.progress = QProgressBar()

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress)

        self.download.downloadProgress.connect(self.update_progress)
        self.download.finished.connect(self.finish_download)

    def update_progress(self, received: int, total: int) -> None:
        if total > 0:
            percent = int((received / total) * 100)
            self.progress.setValue(percent)

    def finish_download(self) -> None:
        self.progress.setValue(100)
        self.label.setText(f"{self.download.downloadFileName()} (Completed)")