import unittest
import tempfile
import os
import json
import shutil
from collective.exportimport import config
from collective.exportimport.filesystem_exporter import FileSystemContentExporter
from collective.exportimport.testing import COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING


class TestFileSystemContentExporter(unittest.TestCase):
    """Test the FileSystemContentExport class"""

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

    def setUp(self):
        # Set up a temporary directory for testing
        self.temp_dir = 'temp_test_directory'
        os.makedirs(self.temp_dir, exist_ok=True)

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save(self):

        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            exporter = FileSystemContentExporter()
            item = {
                "id": "test_item",
                "parent": {"@id": "/test_parent"},
                "is_folderish": False
                # Add other required fields as needed
            }

            exporter.save(1, item)

            # Check if the file was created in the correct location
            file_path = os.path.join(
                config.CENTRAL_DIRECTORY,
                'exported_tree',
                'plone',
                'content',
                'test_parent',
                '1_test_item.json')
            self.assertTrue(os.path.exists(file_path))

            # Check if the contents of the saved file are correct
            with open(file_path, 'r') as f:
                saved_item = json.load(f)
                self.assertEqual(saved_item, item)
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory
