import sqlite3
import os
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)

class InputNotChangedError(Exception):
    """Raised when the input file has not changed since the last conversion."""
    pass


class OutputChangedError(Exception):
    """Raised when the output file has been modified since the last conversion."""
    pass

@dataclass
class MetadataEntry:
    id: int
    input_note_filename: str
    output_markdown_filename: str
    expected_path: str
    actual_file_path: Optional[str]
    input_file_hash: str
    output_file_hash: str
    is_locked: bool
    image_files: str  # JSON list of image files or comma-separated

class MetadataManager:
    def __init__(self, output_dir: str):
        self.meta_dir = os.path.join(output_dir, ".meta")
        self.db_path = os.path.join(self.meta_dir, "metadata")
        os.makedirs(self.meta_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._initialize_db()

    def _initialize_db(self):
        """Create the metadata table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_note_filename TEXT NOT NULL UNIQUE,
                output_markdown_filename TEXT NOT NULL,
                expected_path TEXT NOT NULL,
                actual_file_path TEXT,
                input_file_hash TEXT,
                output_file_hash TEXT,
                is_locked BOOLEAN DEFAULT 0,
                image_files TEXT
            )
        """)
        self.conn.commit()

    def get_entry_by_input(self, input_filename: str) -> Optional[MetadataEntry]:
        """Retrieve a metadata entry by input filename."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM metadata WHERE input_note_filename = ?", (input_filename,))
        row = cursor.fetchone()
        if row:
            return MetadataEntry(**dict(row))
        return None
    
    def get_all_entries(self) -> List[MetadataEntry]:
        """Retrieve all metadata entries."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM metadata")
        rows = cursor.fetchall()
        return [MetadataEntry(**dict(row)) for row in rows]

    def upsert_entry(
        self,
        input_note_filename: str,
        output_markdown_filename: str,
        expected_path: str,
        actual_file_path: Optional[str],
        input_file_hash: str,
        output_file_hash: str,
        is_locked: bool,
        image_files: str
    ):
        """Insert or update a metadata entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO metadata (
                input_note_filename,
                output_markdown_filename,
                expected_path,
                actual_file_path,
                input_file_hash,
                output_file_hash,
                is_locked,
                image_files
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(input_note_filename) DO UPDATE SET
                output_markdown_filename=excluded.output_markdown_filename,
                expected_path=excluded.expected_path,
                actual_file_path=excluded.actual_file_path,
                input_file_hash=excluded.input_file_hash,
                output_file_hash=excluded.output_file_hash,
                is_locked=excluded.is_locked,
                image_files=excluded.image_files
        """, (
            input_note_filename,
            output_markdown_filename,
            expected_path,
            actual_file_path,
            input_file_hash,
            output_file_hash,
            is_locked,
            image_files
        ))
        self.conn.commit()

    def delete_all(self):
        """Delete all entries (does not remove the DB file itself)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM metadata")
        self.conn.commit()
    
    def close(self):
        self.conn.close()

    @staticmethod
    def remove_db(output_dir: str):
        """Remove the database file."""
        meta_dir = os.path.join(output_dir, ".meta")
        db_path = os.path.join(meta_dir, "metadata")
        if os.path.exists(db_path):
            os.remove(db_path)
