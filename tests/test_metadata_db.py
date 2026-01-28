
import unittest
import tempfile
import shutil
import os
import sqlite3
from sn2md.metadata_db import MetadataManager

class TestMetadataManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = MetadataManager(self.test_dir)

    def tearDown(self):
        self.manager.close()
        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        entries = self.manager.get_all_entries()
        self.assertEqual(len(entries), 0)

    def test_upsert_and_get(self):
        self.manager.upsert_entry(
            input_note_filename="test.note",
            output_markdown_filename="test.md",
            expected_path="test.md",
            actual_file_path="/abs/path/test.md",
            input_file_hash="hash1",
            output_file_hash="hash2",
            is_locked=False,
            image_files="[]"
        )

        entry = self.manager.get_entry_by_input("test.note")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.input_note_filename, "test.note")
        self.assertEqual(entry.actual_file_path, "/abs/path/test.md")
        self.assertEqual(entry.input_file_hash, "hash1")

    def test_update(self):
        self.manager.upsert_entry(
            input_note_filename="test.note",
            output_markdown_filename="test.md",
            expected_path="test.md",
            actual_file_path="/abs/path/test.md",
            input_file_hash="hash1",
            output_file_hash="hash2",
            is_locked=False,
            image_files="[]"
        )
        
        self.manager.upsert_entry(
            input_note_filename="test.note",
            output_markdown_filename="test.md",
            expected_path="test.md",
            actual_file_path="/abs/path/test.md",
            input_file_hash="hash1_new",
            output_file_hash="hash2_new",
            is_locked=True,
            image_files="[img1]"
        )

        entry = self.manager.get_entry_by_input("test.note")
        self.assertEqual(entry.input_file_hash, "hash1_new")
        self.assertTrue(entry.is_locked)

    def test_delete_all(self):
        self.manager.upsert_entry(
            input_note_filename="test.note",
            output_markdown_filename="test.md",
            expected_path="test.md",
            actual_file_path="/abs/path/test.md",
            input_file_hash="hash1",
            output_file_hash="hash2",
            is_locked=False,
            image_files="[]"
        )
        self.manager.delete_all()
        entries = self.manager.get_all_entries()
        self.assertEqual(len(entries), 0)

if __name__ == "__main__":
    unittest.main()
