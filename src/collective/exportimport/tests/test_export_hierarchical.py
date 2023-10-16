# -*- coding: utf-8 -*-
from plone import api
from plone.app.testing import login, SITE_OWNER_NAME, SITE_OWNER_PASSWORD
from collective.exportimport import config
from collective.exportimport.testing import (  # noqa: E501,
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,
)

import os
import shutil
import tempfile
import unittest
import transaction


try:
    from plone.testing import zope

    OLD_ZOPE_TESTBROWSER = False
except ImportError:
    # BBB for plone.testing 4
    from plone.testing import z2 as zope
    from ZPublisher.HTTPResponse import HTTPResponse

    OLD_ZOPE_TESTBROWSER = True


DATA = []


def write(self, data):
    """Override for HTTPResponse.write.

    In Zope 2 (Plone 4.3-5.1) in tests, when we export content to download it,
    the resulting browser.contents is empty, instead of containing json.
    This is an ugly hack to capture the data that should be available.
    I tried a few other ways, but failed.
    """
    self._orig_write(data)
    DATA.append(data)


class TestHierarchicalExport(unittest.TestCase):
    """Test that we can export."""

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

    def setUp(self):
        if OLD_ZOPE_TESTBROWSER:
            # patch HTTPResponse so we can get an attachment
            HTTPResponse._orig_write = HTTPResponse.write
            HTTPResponse.write = write

    def tearDown(self):
        if OLD_ZOPE_TESTBROWSER:
            # undo patch
            HTTPResponse.write = HTTPResponse._orig_write

    def create_demo_content(self):
        """Create a portal structure which we can test against.
        Plone (portal root)
        |-- folder1
        |   |-- doc1
        |   |-- folder2_1
        |       |-- doc3
        |-- folder2
            |-- doc2
        """
        portal = self.layer["portal"]
        folder1 = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        doc1 = api.content.create(
            container=folder1, type="Document", id="doc1", title="Document 1"
        )
        folder1._setProperty("default_page", "doc1")

        folder2 = api.content.create(
            container=portal, type="Folder", id="folder2", title="Folder 2"
        )
        folder2_1 = api.content.create(
            container=folder1, type="Folder", id="folder2-1", title="Folder 2.1"
        )
        doc2 = api.content.create(
            container=folder2, type="Document", id="doc2", title="Document 2"
        )
        doc3 = api.content.create(
            container=folder2_1, type="Document", id="doc3", title="Document 3"
        )

    def open_page(self, page):
        """Create a testbrowser, open a page, return the browser."""
        browser = zope.Browser(self.layer["app"])
        browser.handleErrors = False
        browser.addHeader(
            "Authorization",
            "Basic {0}:{1}".format(SITE_OWNER_NAME, SITE_OWNER_PASSWORD),
        )
        url = "/".join([self.layer["portal"].absolute_url(), page])
        browser.open(url)
        return browser

    def test_export_content_page(self):
        # Simply test that some text is on the page.
        browser = self.open_page("@@export_content")
        self.assertIn("Generate a file for each item (as filesytem tree)", browser.contents)

    def test_export_all_content_to_server(self):
        """Test complete hierarchical export to server"""

        # 1. Create Content
        # 2. Enter to the page
        # 3. Select proper select
        # 4. Select proper checkbox
        # 5. Set central original_central_directory
        # 6. Submit form
        # 7. Check base directories
        # 8. Check exported tree contains content
        # 9. Finally, remove exported directory

        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        fti = self.layer["portal"].portal_types["Plone Site"]

        login(app, SITE_OWNER_NAME)
        self.create_demo_content()

        transaction.commit()

        # Go to export_content view
        browser = self.open_page("@@export_content")

        # Now export all.
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("Document", portal_type.options)
        self.assertIn("Folder", portal_type.options)

        portal_type.value = ["Folder", "Document"]
        fti = self.layer["portal"].portal_types["Plone Site"]
        if "DexterityFTI" in repr(fti):
            # In Plone 6 the portal is exportable
            self.assertIn("Plone Site", portal_type.options)
            portal_type.value = ["Folder", "Document"]

        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True

        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit(name="submit")

            msg = "Exported 6 items (Folder, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # check paths
            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "content")
            self.assertTrue(os.path.exists(path))

            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "removed_items")
            self.assertTrue(os.path.exists(path))

            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "content",
                "folder1",
                "2_doc1.json")
            self.assertTrue(os.path.exists(path))

        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_export_partial_content_to_server(self):
        """Test complete hierarchical export to server"""

        # 1. Create Content
        # 2. Enter to the page
        # 3. Select proper content
        # 4. Select proper checkbox
        # 5. Set central original_central_directory
        # 6. Submit form
        # 7. Check base directories
        # 8. Check exported tree contains content
        # 9. Finally, remove exported directory

        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        fti = self.layer["portal"].portal_types["Plone Site"]

        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Go to export_content view
        browser = self.open_page("@@export_content")

        # Check content types and export folders.
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("Document", portal_type.options)
        self.assertIn("Folder", portal_type.options)

        portal_type.value = ["Folder"]

        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True

        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit(name="submit")

            msg = "Exported 3 items (Folder) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # check paths
            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "content")
            self.assertTrue(os.path.exists(path))

            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "removed_items")
            self.assertTrue(os.path.exists(path))

            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "content",
                "folder1")
            self.assertTrue(os.path.exists(path))

            path = os.path.join(
                config.CENTRAL_DIRECTORY,
                "exported_tree",
                portal.getId(),
                "content",
                "folder1",
                "2_doc1.json")
            self.assertFalse(os.path.exists(path))

        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory
