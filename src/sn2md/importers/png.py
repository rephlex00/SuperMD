import os
import shutil
from supernotelib import Notebook
from sn2md.types import ImageExtractor


class PNGExtractor(ImageExtractor):
    def extract_images(self, filename: str, output_path: str) -> list[str]:
        file_name = os.path.join(output_path, os.path.basename(filename))
        shutil.copy(filename, file_name)
        return [file_name]

    def get_notebook(self, filename: str) -> Notebook | None:
        # TODO: this is correct, but really we're talking about metadata of this specific extractor type - for notebooks its one thing, for PDFs its another...
        return None
