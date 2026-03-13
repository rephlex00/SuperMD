from abc import ABC, abstractmethod
from time import sleep, monotonic

from supermd.supernotelib import Notebook


class CooldownState:
    """Enforces a minimum delay between consecutive API calls."""

    def __init__(self, cooldown: float):
        self.cooldown = cooldown
        self._last_call: float | None = None

    def wait(self, progress_bar=None) -> None:
        if self.cooldown <= 0 or self._last_call is None:
            return
        step = 0.1
        remaining = self.cooldown - (monotonic() - self._last_call)
        while remaining > 0:
            if progress_bar:
                progress_bar.set_description(f"Cooldown: {remaining:.1f}s")
            sleep(min(step, remaining))
            remaining -= step

    def mark(self) -> None:
        self._last_call = monotonic()


class ImageExtractor(ABC):
    @abstractmethod
    def extract_images(self, filename: str, output_path: str) -> list[str]:
        pass

    @abstractmethod
    def get_notebook(self, filename: str) -> Notebook | None:
        pass
