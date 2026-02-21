# profiles.py

from pathlib import Path


class ProfileManager:
    """Handles Chrome-style profile isolation."""

    BASE_DIR = Path("profiles")

    def __init__(self, profile_name: str = "default") -> None:
        self.profile_name = profile_name
        self.profile_path = self.BASE_DIR / profile_name
        self.profile_path.mkdir(parents=True, exist_ok=True)

    @property
    def storage_path(self) -> Path:
        return self.profile_path

    @property
    def database_path(self) -> Path:
        return self.profile_path / "browser.db"