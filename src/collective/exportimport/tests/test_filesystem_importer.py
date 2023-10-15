import unittest
import os
import json
import shutil
from collective.exportimport.filesystem_importer import (
    FileSystemContentImporter
)
from collective.exportimport.testing import COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

try:
    from plone.testing import zope

    OLD_ZOPE_TESTBROWSER = False
except ImportError:
    # BBB for plone.testing 4
    from plone.testing import z2 as zope
    from ZPublisher.HTTPResponse import HTTPResponse

    OLD_ZOPE_TESTBROWSER = True


def write(self, data):
    """Override for HTTPResponse.write.

    In Zope 2 (Plone 4.3-5.1) in tests, when we export content to download it,
    the resulting browser.contents is empty, instead of containing json.
    This is an ugly hack to capture the data that should be available.
    I tried a few other ways, but failed.
    """
    self._orig_write(data)
    DATA.append(data)


class TestFileSystemContentImporter(unittest.TestCase):

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

    def setUp(self):
        # Set up a temporary directory for testing
        self.temp_dir = 'temp_test_directory'
        os.makedirs(self.temp_dir, exist_ok=True)

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_parents(self):
        portal = self.layer["portal"]
        importer = FileSystemContentImporter(portal, self.temp_dir)

        # Test with a parent dictionary
        parent = {"@id": "/test/parent/item"}
        parent_path = importer.get_parents(parent)
        self.assertEqual(parent_path, "test/parent/item")

        # Test with no parent dictionary
        parent_path = importer.get_parents(None)
        self.assertEqual(parent_path, "")

    def test_delete_old_if_moved(self):
        portal = self.layer["portal"]
        importer = FileSystemContentImporter(portal, self.temp_dir)
        UID = "test_uid"

        # Create a JSON file for an item with the test UID
        item = {"UID": UID}
        json_file_path = os.path.join(
            self.temp_dir,
            'removed_items',
            '1_test_item.json'
        )
        os.makedirs(os.path.join(
                self.temp_dir,
                'removed_items'
            ),
            exist_ok=True
        )
        with open(json_file_path, "w") as f:
            json.dump(item, f, sort_keys=True, indent=4)

        # Check if the file exists
        self.assertTrue(os.path.exists(json_file_path))

        # Call the method to delete the old object
        importer.delete_old_if_moved(UID)

    def test_process_deleted(self):
        portal = self.layer["portal"]
        importer = FileSystemContentImporter(portal, self.temp_dir)

        # Create a JSON file for a deleted item
        data = """{
    "@id": "http://localhost:8080/Plone/intranet",
    "@type": "Document",
    "UID": "32eb39c7b2aa422f98d7dc7245fdf1f7",
    "allow_discussion": false,
    "blocks": {
        "51b461f2-fd67-42c4-9f14-fa27dc033d38": {
            "@type": "title"
        },
        "5eb1ec97-42a9-4d6b-b1f3-942359b1048c": {
            "@type": "slate"
        }
    },
    "blocks_layout": {
        "items": [
            "51b461f2-fd67-42c4-9f14-fa27dc033d38",
            "5eb1ec97-42a9-4d6b-b1f3-942359b1048c"
        ]
    },
    "contributors": [],
    "created": "2023-10-03T14:31:19+00:00",
    "creators": [
        "admin"
    ],
    "description": "",
    "effective": null,
    "exclude_from_nav": false,
    "expires": null,
    "id": "intranet",
    "is_folderish": true,
    "language": "es",
    "layout": "document_view",
    "lock": {
        "locked": false,
        "stealable": true
    },
    "modified": "2023-10-03T14:31:19+00:00",
    "parent": {
        "@id": "http://localhost:8080/Plone",
        "@type": "Plone Site",
        "UID": "88f83b6e449a4cc6a4b688e17fbb4421",
        "description": "",
        "title": "Sitio",
        "type_title": "Sitio Plone"
    },
    "preview_caption": null,
    "preview_image": null,
    "review_state": "private",
    "rights": "",
    "subjects": [],
    "title": "Intranet",
    "type_title": "P\u00e1gina",
    "version": "current",
    "workflow_history": {
        "simple_publication_workflow": [
            {
                "action": null,
                "actor": "admin",
                "comments": "",
                "review_state": "private",
                "time": "2023-10-03T14:31:19+00:00"
            }
        ]
    },
    "working_copy": null,
    "working_copy_of": null
}
"""

        item = json.loads(data)
        json_file_path = os.path.join(
            self.temp_dir,
            'removed_items',
            '1_deleted_item.json'
        )
        os.makedirs(os.path.join(
                self.temp_dir,
                'removed_items'
            ),
            exist_ok=True
        )

        with open(json_file_path, "w") as f:
            json.dump(item, f, sort_keys=True, indent=4)

        # Check if the file exists
        self.assertTrue(os.path.exists(json_file_path))

        # Call the method to process deleted items
        message = importer.process_deleted()

        # Check if the file was removed
        self.assertTrue("Deleted 0 items" in message)
