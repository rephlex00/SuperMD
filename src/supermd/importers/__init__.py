from supermd.types import ImageExtractor
from supermd.importers.note import NotebookExtractor
from supermd.importers.pdf import PDFExtractor
from supermd.importers.png import PNGExtractor
from supermd.importers.atelier import AtelierExtractor

SUPPORTED_EXTENSIONS = (".note", ".pdf", ".png", ".spd")

_EXTRACTOR_MAP = {
    ".note": NotebookExtractor,
    ".pdf": PDFExtractor,
    ".png": PNGExtractor,
    ".spd": AtelierExtractor,
}


def get_extractor(filename: str) -> ImageExtractor | None:
    """Return the appropriate extractor for a file, or None if unsupported."""
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    cls = _EXTRACTOR_MAP.get(ext)
    return cls() if cls else None
