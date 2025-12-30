import io
import logging
import os
import sqlite3
import sys

import supernotelib as sn
from PIL import Image
from typing_extensions import override

from sn2md.types import ImageExtractor

logger = logging.getLogger(__name__)

TILE_PIXELS = 128
STRIDE = 4096
# Magic number for the upper left tile in an SPD file
START_INDEX = 7976857


def tid_to_row_col(tid):
    offset = tid - START_INDEX
    col = offset % STRIDE
    row = offset // STRIDE
    # If the column value is in the upper half of the STRIDE range, it represents
    # a negative coordinate. This is a common way to handle signed values.
    if col >= STRIDE / 2:
        logger.warning("Negative column detected for TID %d: %d", tid, col)
        col -= STRIDE
        row += 1  # Adjust row to account for the negative column
    return row, col

def find_content_bounding_box(tile_dict: list[dict]) -> tuple[int, int, int, int]:
    """Calculates the bounding box (min_x, min_y, max_x, max_y) for all tiles."""
    min_x, min_y = sys.maxsize, sys.maxsize
    max_x, max_y = 0, 0
    has_tiles = False

    for tile_data in tile_dict:
        for tid in tile_data.keys():
            has_tiles = True
            row, col = tid_to_row_col(tid)
            x = row * TILE_PIXELS
            y = col * TILE_PIXELS
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + TILE_PIXELS)
            max_y = max(max_y, y + TILE_PIXELS)

    if not has_tiles:
        return 0, 0, 0, 0

    return min_x, min_y, max_x, max_y


def sqlite_read_config(cursor: sqlite3.Cursor, name: str, default_value: str) -> str:
    _ = cursor.execute("SELECT value FROM config WHERE name=?;", (name,))
    val = cursor.fetchone()
    logger.debug("config %s: %s", name, val)
    if not val:
        logger.warning("SPD file does not contain %s, ignoring", name)
        return default_value
    else:
        return val[0].decode("utf-8")


def read_tiles_data(spd_file_path: str) -> tuple[list[dict], int, int]:
    conn = sqlite3.connect(spd_file_path)
    cursor = conn.cursor()

    def get_config_data(cursor: sqlite3.Cursor, query: str, err_message: str) -> list:
        _ = cursor.execute(query)
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise ValueError(err_message)
        return result

    # Verify that the file has config tables (Dropbox syncs might not contain them on an initial sync)
    _ = get_config_data(
        cursor,
        "PRAGMA table_info(config);",
        "SPD file does not contain config table, ignoring"
    )

    # Check the format version - only version 2 is supported at present
    version_row = get_config_data(
        cursor,
        "SELECT value FROM config WHERE name='fmt_ver';",
        "SPD file does not contain format version in config table"
    )
    version = version_row[0].decode("utf-8")
    if version != "2":
        conn.close()
        raise ValueError(f"Unsupported SPD format version: {version}")

    layers_row = get_config_data(
        cursor,
        "select value from config where name='ls';",
        "SPD file does not contain layers in config table"
    )
    layers = [v for v in layers_row[0].decode("utf-8").split("\n") if len(v) > 0]

    def is_not_visible(x: str) -> bool:
        return x.endswith("\x00")

    def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
        """Check if a table exists in the database."""
        _ = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        return cursor.fetchone() is not None

    tiles_data = []
    # Iterate over the layers from the top layer to the bottom layer
    max_layer = len(layers) - 1
    for i in range(max_layer, -1, -1):
        if is_not_visible(layers[max_layer - i]):
            logger.debug("Skipping layer %d because it is not visible", i)
            continue
        if not table_exists(cursor, f"surface_{i}"):
            logger.debug("Skipping layer %d because surface_%d not visible", i, i)
            continue
        # Fetch tiles, ordering them by tid.  Replace with the hardcoded `tids` list
        _ = cursor.execute(f"SELECT tid, tile FROM surface_{i} ORDER BY tid ASC;")
        tile_dict = {tid: tile_data for tid, tile_data in cursor.fetchall()}
        tiles_data.append(tile_dict)

    width = int(float(sqlite_read_config(cursor, "surface.width", "0")))
    height = int(float(sqlite_read_config(cursor, "surface.height", "0")))

    conn.close()

    return tiles_data, width, height


def _make_full_image(
    tiles_data: list[dict],
    max_x: int,
    max_y: int,
    min_x: int,
    min_y: int,
    width: int,
    height: int,
) -> tuple[Image.Image, tuple[int, int]]:
    # Calculate the dimensions of the actual drawn content
    content_width = max_x - min_x
    content_height = max_y - min_y

    # The final canvas should be big enough for the metadata OR the content, whichever is larger.
    canvas_width = max(width, content_width)
    canvas_height = max(height, content_height)
    canvas_x_y = (canvas_width, canvas_height)
    logger.debug("output size: %s", canvas_x_y)

    for v in tiles_data:
        for tid in v.keys():
            logger.debug("Tile ID %d: %s", tid, tid_to_row_col(tid))
    MAX_DIMENSION = 50000  # 50k pixels, a very generous limit
    if content_width > MAX_DIMENSION or content_height > MAX_DIMENSION:
        raise ValueError(
            f"""Content dimensions ({content_width}x{content_height}) are excessively large.
            The .spd file may be corrupt."""
        )


    full_image = Image.new("RGBA", canvas_x_y)

    # Calculate the offset needed to center the content on the canvas
    offset_x = (canvas_width - content_width) // 2
    offset_y = (canvas_height - content_height) // 2

    for tile_dict in reversed(tiles_data):
        for tid in tile_dict.keys():
            tile_data = tile_dict[tid]
            tile = Image.open(io.BytesIO(tile_data)).convert("RGBA")

            # ensure that whatever tile we read in is the right size
            assert tile.size == (TILE_PIXELS, TILE_PIXELS)

            row, col = tid_to_row_col(tid)

            # Get the tile's absolute position on the infinite grid
            absolute_x = row * TILE_PIXELS
            absolute_y = col * TILE_PIXELS

            # Translate to a relative position (so content starts at 0,0) and then add centering offset
            paste_x = (absolute_x - min_x) + offset_x
            paste_y = (absolute_y - min_y) + offset_y

            # Blend the tile image with the full image
            # We create a temporary transparent image of the final size to paste the tile into,
            # which is a safe way to composite layers with alpha blending.
            tile_image = Image.new("RGBA", canvas_x_y)
            tile_image.paste(tile, (paste_x, paste_y))
            full_image = Image.alpha_composite(full_image, tile_image)

    return full_image, canvas_x_y

def _make_blank_image(width: int, height: int) -> tuple[Image.Image, tuple[int, int]]:
    # Fallback for completely empty files
    canvas_width = width or (TILE_PIXELS * 12 * 2)
    canvas_height = height or (TILE_PIXELS * 16 * 2)
    x_y = (canvas_width, canvas_height)
    return Image.new("RGBA", x_y), x_y

def spd_to_png(spd_file_path: str, output_path: str) -> str:
    tiles_data, meta_width, meta_height = read_tiles_data(spd_file_path)
    logger.debug("Number of layers: %d", len(tiles_data))

    min_x, min_y, max_x, max_y = find_content_bounding_box(tiles_data)
    logger.debug("Bounding box: min_x=%d, min_y=%d, max_x=%d, max_y=%d", min_x, min_y, max_x, max_y)

    # If there are no tiles, create a blank image based on metadata size
    if (min_x, min_y, max_x, max_y) == (0, 0, 0, 0):
        full_image, x_y = _make_blank_image(meta_width, meta_height)
    else:
        full_image, x_y = _make_full_image(
            tiles_data,
            max_x,
            max_y,
            min_x,
            min_y,
            meta_width,
            meta_height
        )

    # Create a white background and paste the final composited image onto it
    full_image_with_white_bg = Image.new("RGB", x_y, (255, 255, 255))
    full_image_with_white_bg.paste(full_image, (0, 0), full_image)

    image_path = (
        output_path
        + "/"
        + os.path.splitext(os.path.basename(spd_file_path))[0]
        + ".png"
    )
    full_image_with_white_bg.save(image_path)

    return image_path

class AtelierExtractor(ImageExtractor):
    @override
    def extract_images(self, filename: str, output_path: str) -> list[str]:
        return [spd_to_png(filename, output_path)]

    @override
    def get_notebook(self, filename: str) -> sn.Notebook | None:
        return None
