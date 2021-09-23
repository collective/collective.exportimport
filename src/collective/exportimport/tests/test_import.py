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
from plone.namedfile.file import NamedImage
from plone.namedfile.file import NamedBlobImage
from Products.CMFPlone.tests import dummy

import json
import os
import shutil
import tempfile
import transaction
import unittest

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


class TestImport(unittest.TestCase):
    """Test that we can export."""

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

    def create_demo_content(self):
        """Create a portal structure which we can test against.
        Plone (portal root)
        |-- image
        |-- blog
        |-- about
        |   |-- team
        |   `-- contact
        `-- events
        """
        portal = self.layer["portal"]

        self.blog = api.content.create(
            container=portal,
            type="Link",
            id="blog",
            title=u"Blog",
        )
        self.about = api.content.create(
            container=portal,
            type="Folder",
            id="about",
            title=u"About",
        )
        self.events = api.content.create(
            container=portal,
            type="Folder",
            id="events",
            title=u"Events",
        )
        self.team = api.content.create(
            container=self.about,
            type="Document",
            id="team",
            title=u"Team",
        )
        self.contact = api.content.create(
            container=self.about,
            type="Document",
            id="contact",
            title=u"Contact",
        )
        self.image = api.content.create(
            container=portal,
            type="Image",
            title=u"Image",
            id="image",
            image=NamedImage(dummy.Image(), "image/gif", u"test.gif"),
        )

    def remove_demo_content(self):
        """remove what was create in create_demo_content
        Plone (portal root)
        |-- image
        |-- blog
        |-- about
        |   |-- team
        |   `-- contact
        `-- events

        """
        portal = self.layer["portal"]
        api.content.delete(portal["image"])
        api.content.delete(portal["blog"])
        api.content.delete(portal["about"])
        api.content.delete(portal["events"])

    def setUp(self):
        # Set a client home for our import directory.
        # Usually this is buildout-dir/var/instance.
        # In tests it is somewhere in an egg, which is not helpful.
        cfg = getConfiguration()
        self.orig_clienthome = cfg.clienthome
        self.new_clienthome = tempfile.mkdtemp(suffix=".clienthome")
        os.mkdir(os.path.join(self.new_clienthome, "import"))
        cfg.clienthome = self.new_clienthome
        if OLD_ZOPE_TESTBROWSER:
            # patch HTTPResponse so we can get an attachment
            HTTPResponse._orig_write = HTTPResponse.write
            HTTPResponse.write = write

    def tearDown(self):
        cfg = getConfiguration()
        cfg.clienthome = self.orig_clienthome
        shutil.rmtree(self.new_clienthome)
        if OLD_ZOPE_TESTBROWSER:
            # undo patch
            HTTPResponse.write = HTTPResponse._orig_write

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
        doc_uid = doc.UID()
        transaction.commit()

        # Now export it.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = ["Document"]
        browser.getForm(action="@@export_content").submit(name="submit")

        # We should have gotten json.
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

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
        self.assertEqual(new_doc.UID(), doc_uid)

        # See what happens when we import it a second time.
        original_ids = portal.contentIds()
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # A second document should be there.
        new_ids = [docid for docid in portal.contentIds() if docid not in original_ids]
        self.assertEqual(len(new_ids), 1)
        doc2 = portal[new_ids[0]]
        # doc2 is the same as the original
        self.assertEqual(doc2.Title(), "Document 1")
        self.assertEqual(doc2.portal_type, "Document")
        # except for the UID
        self.assertNotEqual(doc2.UID(), doc_uid)

    def test_import_content_with_missing_folder(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        folder = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        api.content.create(
            container=folder, type="Document", id="doc1", title="Document 1"
        )
        transaction.commit()

        # Now export the document.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = ["Document"]
        browser.getForm(action="@@export_content").submit(name="submit")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

        # Remove both the folder and document.
        api.content.delete(folder)
        transaction.commit()
        self.assertNotIn("folder1", portal.contentIds())

        # Now import the document.
        # The missing folder structure should be created.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # The folder should be back.
        self.assertIn("folder1", portal.contentIds())
        new_folder = portal["folder1"]
        # The auto generated folder will have its id as title
        self.assertEqual(new_folder.Title(), "folder1")
        # The document should be back.
        self.assertIn("doc1", new_folder.contentIds())
        new_doc = new_folder["doc1"]
        self.assertEqual(new_doc.Title(), "Document 1")
        self.assertEqual(new_doc.portal_type, "Document")

    def test_import_content_from_other_plone_site(self):
        # When we import nohost/nl/folder/page into
        # nohost/plone, we should not get an 'nl' container.

        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        folder = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        api.content.create(
            container=folder, type="Document", id="doc1", title="Document 1"
        )
        transaction.commit()

        # Now export the document.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = ["Document"]
        browser.getForm(action="@@export_content").submit(name="submit")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

        # Edit the raw data to pretend this was from a Plone Site
        # with id 'nl' instead of 'plone'.
        raw_data = raw_data.replace(b"/plone", b"/nl")

        # Remove both the folder and document.
        api.content.delete(folder)
        transaction.commit()
        self.assertNotIn("folder1", portal.contentIds())

        # Now import the document.
        # The missing folder structure should be created.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # The folder should be back.
        self.assertIn("folder1", portal.contentIds())
        new_folder = portal["folder1"]
        # The auto generated folder will have its id as title
        self.assertEqual(new_folder.Title(), "folder1")
        # The document should be back.
        self.assertIn("doc1", new_folder.contentIds())
        new_doc = new_folder["doc1"]
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
        browser.getForm(action="@@export_content").submit(name="submit")

        self.assertIn("Exported 1 items (Document) as Document.json", browser.contents)
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

    def test_import_content_from_central_directory(self):
        from collective.exportimport import config
        import tempfile

        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        transaction.commit()

        # Save the original, so we can restore it at the end of the test.
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()

            # Now export the content to a file in this directory.
            browser = self.open_page("@@export_content")
            browser.getControl(name="portal_type").value = ["Document"]
            browser.getControl("Save to file on server").click()
            browser.getForm(action="@@export_content").submit(name="submit")

            self.assertIn(
                "Exported 1 items (Document) as Document.json", browser.contents
            )
            self.assertIn(config.CENTRAL_DIRECTORY, browser.contents)

            # Move the exported file to the import directory.
            export_path = os.path.join(config.CENTRAL_DIRECTORY, "Document.json")
            self.assertTrue(os.path.isfile(export_path))

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

        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_import_contenttree(self):
        # First create some content to export.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        self.assertIn("events", portal.contentIds())
        self.assertIn("image", portal.contentIds())
        transaction.commit()

        # Now export the complete portal.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Image",
            "Link",
            "Document",
        ]
        browser.getForm(action="@@export_content").submit(name="submit")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]

        data = json.loads(contents)
        self.assertEqual(len(data), 6)

        # Remove the added content.
        self.remove_demo_content()
        transaction.commit()
        self.assertNotIn("events", portal.contentIds())

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(contents, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 6 items", browser.contents)

        # The content should be back.
        self.assertIn("events", portal.contentIds())
        self.assertEqual(portal["events"].portal_type, "Folder")
        self.assertEqual(portal["image"].image.data, dummy.Image().data)

    def _disabled_test_import_blob_path(self):
        # This test is disabled, because the demo storage
        # has no 'fshelper' from which we can ask the blob path.
        # First create a demo image to export.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        image_data = dummy.Image().read()
        self.image = api.content.create(
            container=portal,
            type="Image",
            title=u"Image",
            id="image",
            image=NamedBlobImage(image_data, "image/gif", u"test.gif"),
        )
        self.assertIn("image", portal.contentIds())
        transaction.commit()

        # Now export the complete portal.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Image",
        ]
        browser.getControl(name="include_blobs").value = [2]
        browser.getForm(action="@@export_content").submit(name="submit")
        contents = browser.contents
        if not browser.contents:
            # Note: the test would error here, because nothing is exported:
            # the error is swallowed.
            contents = DATA[-1]

        data = json.loads(contents)
        self.assertEqual(len(data), 1)

        # Remove the added content.
        api.content.delete(portal["image"])
        transaction.commit()
        self.assertNotIn("image", portal.contentIds())

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(contents, "application/json", "Image.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # The image should be back.
        self.assertEqual(portal["image"].portal_type, "Image")
        self.assertEqual(portal["image"].image.data, dummy.Image().data)

    def test_import_defaultpages(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        folder1 = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        api.content.create(
            container=folder1, type="Document", id="doc1", title="Document 1"
        )
        folder1._setProperty("default_page", "doc1")
        transaction.commit()

        # Export it.
        browser = self.open_page("@@export_defaultpages")
        browser.getForm(action="@@export_defaultpages").submit(name="form.submitted")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

        # Now remove the default page setting.
        folder1._delProperty("default_page")
        transaction.commit()
        self.assertFalse(folder1.getProperty("default_page"))

        # Now import it.
        browser = self.open_page("@@import_defaultpages")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "defaultpages.json")
        browser.getForm(action="@@import_defaultpages").submit(name="form.submitted")
        self.assertIn("Changed 1 default page", browser.contents)

        # The default page should be back.
        self.assertEqual(folder1.getProperty("default_page"), "doc1")

        # Set a different default page.
        api.content.create(
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
        api.content.create(
            container=folder1, type="Document", id="doc1", title="Document 1"
        )
        api.content.create(
            container=folder1, type="Document", id="doc2", title="Document 2"
        )
        api.content.create(
            container=folder1, type="Document", id="doc3", title="Document 3"
        )
        transaction.commit()

        # Export.
        browser = self.open_page("@@export_ordering")
        browser.getForm(action="@@export_ordering").submit(name="form.submitted")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

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
