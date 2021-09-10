# -*- coding: utf-8 -*-
from App.config import getConfiguration
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,  # noqa: E501,,
)
from OFS.interfaces import IOrderedContainer
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing import zope

import json
import os
import shutil
import sys
import tempfile
import transaction
import unittest


# TODO: change this to skip the tests on Plone 5.1 and lower.
# Python 2 on 5.2 should be fine, but currently it gives an error when
# importing the modified date:
# ValueError: 'z' is a bad directive in format '%Y-%m-%dT%H:%M:%S%z'
# Ah, and we have the same error on Python 3.6.
@unittest.skipIf(sys.version_info[:2] < (3, 7), "Import is only supported on Python 3.7+ for the moment")
class TestImport(unittest.TestCase):
    """Test that we can export."""

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

    def setUp(self):
        # Set a client home for our import directory.
        # Usually this is buildout-dir/var/instance.
        # In tests it is somewhere in an egg, which is not helpful.
        cfg = getConfiguration()
        self.orig_clienthome = cfg.clienthome
        self.new_clienthome = tempfile.mkdtemp(suffix=".clienthome")
        os.mkdir(os.path.join(self.new_clienthome, "import"))
        cfg.clienthome = self.new_clienthome

    def tearDown(self):
        cfg = getConfiguration()
        cfg.clienthome = self.orig_clienthome
        shutil.rmtree(self.new_clienthome)

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

    def test_import_content_page(self):
        # Simply test that some text is on the page.
        browser = self.open_page("@@import_content")
        # Let's compare lowercase.
        lower_contents = browser.contents.lower()
        self.assertIn("import content", lower_contents)
        self.assertIn("import relations", lower_contents)
        self.assertIn("import translations", lower_contents)
        self.assertIn("import members", lower_contents)
        self.assertIn("import local roles", lower_contents)
        self.assertIn("import default pages", lower_contents)
        self.assertIn("import object positions", lower_contents)

    def test_import_content_document(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        transaction.commit()

        # Now export it.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = ["Document"]
        browser.getControl("Export selected type").click()
        raw_data = browser.contents

        # Remove the added content.
        api.content.delete(doc)
        transaction.commit()
        self.assertNotIn("doc1", portal.contentIds())

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # The document should be back.
        self.assertIn("doc1", portal.contentIds())
        new_doc = portal["doc1"]
        self.assertEqual(new_doc.Title(), "Document 1")
        self.assertEqual(new_doc.portal_type, "Document")

    def test_import_content_from_server_file(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = ["Document"]
        browser.getControl("Save to file on server").click()
        browser.getControl("Export selected type").click()
        self.assertIn("Exported 1 Document as Document.json", browser.contents)
        self.assertIn(self.new_clienthome, browser.contents)

        # Move the exported file to the import directory.
        export_path = os.path.join(self.new_clienthome, "Document.json")
        import_path = os.path.join(self.new_clienthome, "import", "Document.json")
        self.assertTrue(os.path.isfile(export_path))
        self.assertFalse(os.path.exists(import_path))
        shutil.move(export_path, import_path)
        self.assertTrue(os.path.isfile(import_path))

        # Remove the added content.
        api.content.delete(doc)
        transaction.commit()
        self.assertNotIn("doc1", portal.contentIds())

        # Now import it.
        browser = self.open_page("@@import_content")
        server_file = browser.getControl(name="server_file")
        server_file.value = ["Document.json"]
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # The document should be back.
        self.assertIn("doc1", portal.contentIds())
        new_doc = portal["doc1"]
        self.assertEqual(new_doc.Title(), "Document 1")
        self.assertEqual(new_doc.portal_type, "Document")

    def test_import_defaultpages(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        folder1 = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        doc1 = api.content.create(
            container=folder1, type="Document", id="doc1", title="Document 1"
        )
        folder1._setProperty("default_page", "doc1")
        transaction.commit()

        # Export it.
        browser = self.open_page("@@export_defaultpages")
        browser.getForm(action="@@export_defaultpages").submit(name='form.submitted')
        raw_data = browser.contents

        # Now remove the default page setting.
        folder1._delProperty("default_page")
        transaction.commit()
        self.assertFalse(folder1.getProperty("default_page"))

        # Now import it.
        browser = self.open_page("@@import_defaultpages")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "defaultpages.json")
        browser.getForm(action="@@import_defaultpages").submit(name='form.submitted')
        self.assertIn("Changed 1 default page", browser.contents)

        # The default page should be back.
        self.assertEqual(folder1.getProperty("default_page"), "doc1")

        # Set a different default page.
        doc2 = api.content.create(
            container=folder1, type="Document", id="doc2", title="Document 2"
        )
        folder1._updateProperty("default_page", "doc2")
        transaction.commit()

        # Import again.
        browser = self.open_page("@@import_defaultpages")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "defaultpages.json")
        browser.getForm(action="@@import_defaultpages").submit()

        # The default page should be back.
        self.assertEqual(folder1.getProperty("default_page"), "doc1")

    def test_import_ordering(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        folder1 = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        doc1 = api.content.create(
            container=folder1, type="Document", id="doc1", title="Document 1"
        )
        doc2 = api.content.create(
            container=folder1, type="Document", id="doc2", title="Document 2"
        )
        doc3 = api.content.create(
            container=folder1, type="Document", id="doc3", title="Document 3"
        )
        transaction.commit()

        # Export.
        browser = self.open_page("@@export_ordering")
        browser.getForm(action="@@export_ordering").submit(name='form.submitted')
        raw_data = browser.contents

        # Reorder the documents.
        ordered = IOrderedContainer(folder1)
        ordered.moveObjectsToTop(["doc3"])
        transaction.commit()

        # Import and check.
        browser = self.open_page("@@import_ordering")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "ordering.json")
        browser.getForm(action="@@import_ordering").submit()
        self.assertIn("Imported 4 orders", browser.contents)
        # The documents have the original order again.
        self.assertEqual(ordered.getObjectPosition("doc1"), 0)
        self.assertEqual(ordered.getObjectPosition("doc2"), 1)
        self.assertEqual(ordered.getObjectPosition("doc3"), 2)
