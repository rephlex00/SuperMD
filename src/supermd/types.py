from abc import ABC, abstractmethod

from supermd.supernotelib import Notebook


class ImageExtractor(ABC):
    @abstractmethod
    def extract_images(self, filename: str, output_path: str) -> list[str]:
        pass

    @abstractmethod
    def get_notebook(self, filename: str) -> Notebook | None:
        pass
