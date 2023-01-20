# -*- coding: utf-8 -*-
from App.config import getConfiguration
from collective.exportimport import config
from collective.exportimport.testing import COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING
from DateTime import DateTime
from OFS.interfaces import IOrderedContainer
from plone import api
from plone.app.redirector.interfaces import IRedirectionStorage
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.textfield.value import RichTextValue
from plone.namedfile.file import NamedBlobImage
from plone.namedfile.file import NamedImage
from Products.CMFPlone.interfaces.constrains import ENABLED
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes
from Products.CMFPlone.tests import dummy
from time import sleep
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility
from zope.lifecycleevent import modified

import json
import os
import shutil
import six
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
        self.assertIn("import redirects", lower_contents)

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

        # When we import it a second time is is ignored by default.
        original_ids = portal.contentIds()
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 0 items in 0 seconds", browser.contents)

        # Now we ignore it
        original_ids = portal.contentIds()
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getControl(name="handle_existing_content").value = ["3"]
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items", browser.contents)

        # A second document should be there.
        new_ids = [docid for docid in portal.contentIds() if docid not in original_ids]
        self.assertEqual(len(new_ids), 1)
        self.assertEqual(len(portal.contentIds()), 2)
        doc2 = portal[new_ids[0]]
        # doc2 is the same as the original
        self.assertEqual(doc2.Title(), "Document 1")
        self.assertEqual(doc2.portal_type, "Document")
        # except for the UID
        self.assertNotEqual(doc2.UID(), doc_uid)

    def test_import_content_update(self):
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

        # When we import and update it with some changed data.
        data = json.loads(raw_data)
        data[0]["title"] = "A different title"
        data[0].pop("description")
        changed_raw_data = json.dumps(data)

        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(changed_raw_data.encode(), "application/json", "Document.json")
        browser.getControl(name="handle_existing_content").value = ["2"]  # update!
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items in 0 seconds", browser.contents)

        # new_doc now has a updated title
        new_doc = portal["doc1"]
        self.assertEqual(len(portal.contentIds()), 1)
        self.assertEqual(new_doc.Title(), "A different title")
        self.assertEqual(new_doc.portal_type, "Document")
        # The UID is still the same
        self.assertEqual(new_doc.UID(), doc_uid)

    def test_import_content_replace(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc = api.content.create(
            container=portal,
            type="Document",
            id="doc1",
            title="Document 1",
            description="A Description",
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
        self.assertEqual(new_doc.Description(), "A Description")
        self.assertEqual(new_doc.portal_type, "Document")
        self.assertEqual(new_doc.UID(), doc_uid)

        # When we import and replace it with different data.
        data = json.loads(raw_data)
        data[0]["title"] = "A different title"
        data[0].pop("description")
        changed_raw_data = json.dumps(data)

        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(changed_raw_data.encode(), "application/json", "Document.json")
        browser.getControl(name="handle_existing_content").value = ["1"]  # replace!
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 1 items in 0 seconds", browser.contents)

        # still only one item
        self.assertEqual(len(portal.contentIds()), 1)
        # new_doc now has a updated title
        new_doc = portal["doc1"]
        self.assertEqual(new_doc.Title(), "A different title")
        # description is new (=empty)
        self.assertEqual(new_doc.Description(), "")
        self.assertEqual(new_doc.portal_type, "Document")
        # The UID is still the same
        self.assertEqual(new_doc.UID(), doc_uid)

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

    def test_import_content_from_server_file_and_return_json(self):
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

        # Now import it programatically and return state as JSON
        import_view = portal.restrictedTraverse("@@import_content")
        self.layer["request"].form["form.submitted"] = True
        return_json = json.loads(
            import_view(
                server_file="Document.json",
                return_json=True,
            )
        )
        self.assertEqual("success", return_json["state"])
        self.assertIn("Imported 1 items", return_json["msg"])

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
        # uuid of parents is exported
        self.assertEqual(data[1]["parent"]["UID"], portal["about"].UID())

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

    def test_import_imports_but_ignores_constrains(self):
        """Constrains are exported and imported but not checked during import"""
        # First create some content to export.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        self.assertIn("events", portal.contentIds())
        self.assertIn("image", portal.contentIds())

        # create a collection in self.about
        api.content.create(
            container=self.about,
            type="Collection",
            id="collection",
            title=u"Collection",
        )
        # constrain self.about to only allow documents
        constrains = ISelectableConstrainTypes(self.about)
        constrains.setConstrainTypesMode(ENABLED)
        constrains.setLocallyAllowedTypes(["Document"])
        constrains.setImmediatelyAddableTypes(["Document"])
        from plone.api.exc import InvalidParameterError

        with self.assertRaises(InvalidParameterError):
            api.content.create(
                container=self.about,
                type="Collection",
                id="collection2",
                title=u"Collection 2",
            )
        transaction.commit()

        # Now export the complete portal.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Image",
            "Link",
            "Document",
            "Collection",
        ]
        browser.getForm(action="@@export_content").submit(name="submit")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]

        data = json.loads(contents)
        self.assertEqual(len(data), 7)

        # Remove the added content.
        self.remove_demo_content()
        transaction.commit()
        self.assertNotIn("events", portal.contentIds())

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(contents, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 7 items", browser.contents)

        # The collection is imported despite the constrain
        constrains = ISelectableConstrainTypes(portal["about"])
        self.assertEqual(constrains.getConstrainTypesMode(), ENABLED)
        self.assertEqual(constrains.getLocallyAllowedTypes(), ["Document"])
        self.assertEqual(constrains.getLocallyAllowedTypes(), ["Document"])
        self.assertEqual(portal["about"]["collection"].portal_type, "Collection")
        with self.assertRaises(InvalidParameterError):
            api.content.create(
                container=portal["about"],
                type="Collection",
                id="collection2",
                title=u"Collection 2",
            )

    def test_import_workflow_history(self):
        """workflow_history is imported last"""
        # First create some content to export.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        # modify a document
        api.content.transition(to_state="published", obj=self.team)
        history = self.team.workflow_history["simple_publication_workflow"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["action"], "publish")
        publish_time = history[1]["time"]
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

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(contents, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 6 items", browser.contents)

        team = portal["about"]["team"]
        history = team.workflow_history["simple_publication_workflow"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["action"], "publish")
        self.assertEqual(
            history[1]["time"].asdatetime(),
            publish_time.asdatetime().replace(microsecond=0),
        )

        api.content.transition(transition="retract", obj=team)
        self.assertEqual(len(team.workflow_history["simple_publication_workflow"]), 3)

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

    def test_import_defaultpage_for_site(self):
        # Check that the sample format uses the expected string
        browser = self.open_page("@@import_defaultpages")
        self.assertIn('"uuid": "{}",'.format(config.SITE_ROOT), browser.contents)

        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        portal._setProperty("default_page", "doc1")
        transaction.commit()

        # Export it.
        browser = self.open_page("@@export_defaultpages")
        browser.getForm(action="@@export_defaultpages").submit(name="form.submitted")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

        # Now remove the default page setting.
        portal._delProperty("default_page")
        transaction.commit()
        self.assertFalse(portal.getProperty("default_page"))

        # Now import it.
        browser = self.open_page("@@import_defaultpages")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "defaultpages.json")
        browser.getForm(action="@@import_defaultpages").submit(name="form.submitted")
        self.assertIn("Changed 1 default page", browser.contents)

        # The default page should be back.
        self.assertEqual(portal.getProperty("default_page"), "doc1")

        # Set a different default page.
        api.content.create(
            container=portal, type="Document", id="doc2", title="Document 2"
        )
        portal._updateProperty("default_page", "doc2")
        transaction.commit()

        # Import again.
        browser = self.open_page("@@import_defaultpages")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "defaultpages.json")
        browser.getForm(action="@@import_defaultpages").submit()

        # The default page should be back.
        self.assertEqual(portal.getProperty("default_page"), "doc1")

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

    def test_import_localroles(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        folder = api.content.create(
            container=portal, type="Folder", id="folder", title="Folder"
        )
        folder.__ac_local_roles_block__ = 1
        doc1 = api.content.create(
            container=portal, type="Document", id="doc1", title="Document"
        )
        doc2 = api.content.create(
            container=folder, type="Document", id="doc2", title="Document"
        )
        api.user.create(
            username="peter",
            email="peter@example.org",
            password="verysecret",
            roles=("Member",),
        )
        api.user.create(
            username="jane",
            email="jane@example.org",
            password="veryverysecret",
            roles=("Member",),
        )
        api.user.grant_roles(username="peter", obj=doc1, roles=["Reviewer"])
        api.user.grant_roles(username="peter", obj=doc2, roles=["Owner"])
        api.user.grant_roles(username="jane", obj=portal, roles=["Reviewer", "Editor"])
        transaction.commit()

        # Export.
        browser = self.open_page("@@export_localroles")
        browser.getForm(action="@@export_localroles").submit(name="form.submitted")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

        data = json.loads(raw_data)
        self.assertEqual(data[0]["block"], 1)
        self.assertEqual(data[0]["localroles"], {"admin": ["Owner"]})
        self.assertEqual(
            data[1]["localroles"], {"admin": ["Owner"], "peter": ["Owner"]}
        )
        self.assertEqual(
            data[2]["localroles"], {"admin": ["Owner"], "peter": ["Reviewer"]}
        )
        self.assertNotIn("block", data[1])
        self.assertNotIn("block", data[2])

        # remove local roles
        del folder.__ac_local_roles_block__
        api.user.revoke_roles(username="peter", obj=doc1, roles=["Reviewer"])
        api.user.revoke_roles(username="peter", obj=doc2, roles=["Owner"])
        self.assertEqual(doc1.__ac_local_roles__, {"admin": ["Owner"]})
        api.user.revoke_roles(username="jane", obj=portal, roles=["Reviewer", "Editor"])
        self.assertEqual(doc1.__ac_local_roles__, {"admin": ["Owner"]})
        folder.reindexObjectSecurity()
        doc1.reindexObjectSecurity()
        doc2.reindexObjectSecurity()
        portal.reindexObjectSecurity()

        self.assertEqual(
            portal.__ac_local_roles__,
            {"admin": ["Owner"]},
        )

        self.assertFalse(
            api.user.has_permission(
                "Review portal content", username="jane", obj=portal
            )
        )
        self.assertFalse(
            api.user.has_permission(
                "Modify portal content", username="jane", obj=portal
            )
        )

        # Import and check.
        browser = self.open_page("@@import_localroles")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "localroles.json")
        browser.getForm(action="@@import_localroles").submit()

        # The documents have the original local roles again.
        self.assertEqual(folder.__ac_local_roles_block__, 1)
        self.assertEqual(
            doc1.__ac_local_roles__, {"admin": ["Owner"], "peter": ["Reviewer"]}
        )

        self.assertTrue("Owner" in doc1.__ac_local_roles__["admin"])
        self.assertTrue("Reviewer" in doc1.__ac_local_roles__["peter"])

        self.assertTrue("Owner" in portal.__ac_local_roles__["admin"])
        self.assertTrue("Reviewer" in portal.__ac_local_roles__["jane"])
        self.assertTrue("Editor" in portal.__ac_local_roles__["jane"])

        # remove annotations on request as they are used to cache local roles
        # previous access to local roles has populated the cache
        #
        # Need to understand why IAnnotations(portal.REQUEST).clear() does not work
        # in zope.annotation <= 3.5.0
        # IAnnotations(self.layer["request"]).clear()
        portal.REQUEST.__annotations__.clear()

        # permissions are reindexed
        self.assertTrue(
            api.user.has_permission("Review portal content", username="peter", obj=doc1)
        )
        self.assertFalse(
            api.user.has_permission("Modify portal content", username="peter", obj=doc1)
        )
        self.assertFalse(
            api.user.has_permission("Review portal content", username="peter", obj=doc2)
        )
        self.assertTrue(
            api.user.has_permission("Modify portal content", username="peter", obj=doc2)
        )
        self.assertTrue(
            api.user.has_permission(
                "Modify portal content", username="jane", obj=portal
            )
        )
        self.assertTrue(
            api.user.has_permission(
                "Review portal content", username="jane", obj=portal
            )
        )

    def test_import_richtext_with_html_entities(self):
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        old_text = "<pre>Code example: &lt;h2&gt;Heading 2&lt;/h2&gt; example</pre>"
        doc = api.content.create(
            container=portal,
            type="Document",
            id="doc1",
            title="Document 1",
            text=RichTextValue(old_text, "text/html", "text/x-html-safe"),
        )
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

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()

        new_doc = portal["doc1"]
        # the text should be the same
        self.assertEqual(new_doc.text.raw, old_text)

    def test_import_redirects(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        api.content.rename(obj=portal["doc1"], new_id="doc1-moved")
        api.content.create(
            container=portal, type="Document", id="doc2", title="Document 2"
        )
        api.content.rename(obj=portal["doc2"], new_id="doc2-moved")
        transaction.commit()

        # redirects are stored
        storage = getUtility(IRedirectionStorage, context=portal)
        self.assertTrue(storage.has_path("/plone/doc1"))
        self.assertTrue(storage.has_path("/plone/doc2"))
        self.assertEqual(storage.get("/plone/doc1"), "/plone/doc1-moved")
        self.assertEqual(storage.get("/plone/doc2"), "/plone/doc2-moved")

        # Export it.
        browser = self.open_page("@@export_redirects")
        browser.getForm(action="@@export_redirects").submit(name="form.submitted")
        raw_data = browser.contents
        if not browser.contents:
            raw_data = DATA[-1]

        self.assertTrue(raw_data)

        # Now remove the redirects
        storage = getUtility(IRedirectionStorage, context=portal)
        storage.remove("/plone/doc1")
        storage.remove("/plone/doc2")
        transaction.commit()

        # redirects are gone
        storage = getUtility(IRedirectionStorage, context=portal)
        self.assertFalse(storage.has_path("/plone/doc1"))
        self.assertFalse(storage.has_path("/plone/doc2"))

        # Now import it.
        browser = self.open_page("@@import_redirects")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(raw_data, "application/json", "redirects.json")
        browser.getForm(action="@@import_redirects").submit(name="form.submitted")
        self.assertIn("Redirects imported", browser.contents)

        # redirects are back
        storage = getUtility(IRedirectionStorage, context=portal)
        self.assertTrue(storage.has_path("/plone/doc1"))
        self.assertTrue(storage.has_path("/plone/doc2"))
        self.assertEqual(storage.get("/plone/doc1"), "/plone/doc1-moved")
        self.assertEqual(storage.get("/plone/doc2"), "/plone/doc2-moved")

    def test_import_versions(self):
        app = self.layer["app"]
        portal = self.layer["portal"]
        request = self.layer["request"]
        login(app, SITE_OWNER_NAME)
        if six.PY2:
            # in Plone 4.3 this is somehow not set...
            IAnnotations(request)[
                "plone.app.versioningbehavior-changeNote"
            ] = u"initial_version_changeNote"
        doc1 = api.content.create(
            container=portal,
            type="Document",
            id="doc1",
            title=u"Document 1",
            description=u"A Description",
        )
        folder1 = api.content.create(
            container=portal,
            type="Folder",
            id="folder1",
            title=u"Folder 1",
        )
        doc2 = api.content.create(
            container=folder1,
            type="Document",
            id="doc2",
            title=u"Document 2",
            description=u"A Description",
        )
        modified(doc1)
        modified(folder1)
        modified(doc2)

        doc1.title = u"Document 1 with changed title"
        modified(doc1)
        doc2.title = u"Document 2 with changed title"
        IAnnotations(request)["plone.app.versioningbehavior-changeNote"] = u"Föö bar"
        modified(doc2)

        doc2.description = u"New description in revision 3"
        IAnnotations(request)["plone.app.versioningbehavior-changeNote"] = u"I am new!"
        modified(doc2)
        folder1.title = u"Folder 1 with changed title"
        modified(folder1)

        transaction.commit()

        repo_tool = api.portal.get_tool("portal_repository")
        oldest = repo_tool.getHistory(doc2)._retrieve(
            doc2, 0, preserve=[], countPurged=False
        )
        self.assertEqual(oldest.object.title, u"Document 2")

        # Now export complete portal.
        browser = self.open_page("@@export_content")
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        portal_type.value = ["Folder", "Document"]

        depth = browser.getControl(name="depth")
        self.assertEqual(depth.value, ["-1"])

        revisions = browser.getControl(label="Include revisions")
        self.assertEqual(revisions.selected, False)
        revisions.selected = True

        try:
            # Plone 5.2
            browser.getControl("Export").click()
            contents = browser.contents
        except LookupError:
            # Plone 5.1 and lower
            browser.getForm(index=1).submit()
            if not browser.contents:
                contents = DATA[-1]

        # We should have gotten json.
        data = json.loads(contents)
        self.assertEqual(len(data), 3)

        # Remove the added content.
        api.content.delete(doc1)
        api.content.delete(doc2)
        api.content.delete(folder1)

        transaction.commit()
        self.assertNotIn("doc1", portal.contentIds())
        self.assertNotIn("folder1", portal.contentIds())

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(contents, "application/json", "plone.json")
        form = browser.getForm(action="@@import_content")
        self.assertFalse(form.getControl("Import all old revisions").selected)
        form.getControl("Import all old revisions").selected = True
        form.submit()
        self.assertIn("Imported 3 items", browser.contents)

        # The content should be back.
        self.assertIn("doc1", portal.contentIds())
        self.assertEqual(portal["folder1"].portal_type, "Folder")
        doc2 = portal["folder1"]["doc2"]
        self.assertEqual(doc2.title, u"Document 2 with changed title")
        self.assertEqual(doc2.description, u"New description in revision 3")

        history = repo_tool.getHistoryMetadata(doc2)
        self.assertEqual(history.getLength(countPurged=True), 4)

        if six.PY2:
            # In 5.1 and 5.0 on py2 this test sometimes fails in gh-actions, locally they pass. Duh!
            return

        history_meta = history.retrieve(2)
        self.assertEqual(
            history_meta["metadata"]["sys_metadata"]["comment"], u"Föö bar"
        )

        oldest = repo_tool.getHistory(doc2)._retrieve(
            doc2, 0, preserve=[], countPurged=False
        )
        self.assertEqual(oldest.object.title, u"Document 2")

        repo_tool.revert(portal["folder1"]["doc2"], 0)
        doc2 = portal["folder1"]["doc2"]
        self.assertEqual(doc2.title, u"Document 2")
        self.assertEqual(doc2.description, u"A Description")

    def test_reset_dates(self):
        """Reset original modification and creation dates"""
        # First create some content to export.
        app = self.layer["app"]
        portal = self.layer["portal"]
        request = self.layer["request"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()
        old_creation_date = dateify(self.team.creation_date)
        old_modification_date = dateify(self.team.modification_date)

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

        # Remove the added content.
        self.remove_demo_content()
        transaction.commit()

        # Now import it.
        browser = self.open_page("@@import_content")
        upload = browser.getControl(name="jsonfile")
        upload.add_file(contents, "application/json", "Document.json")
        browser.getForm(action="@@import_content").submit()
        self.assertIn("Imported 6 items", browser.contents)

        team = portal["about"]["team"].aq_base

        # change modification and creation date
        old = team.modification_date
        sleep(1)
        team.creation_date = DateTime()
        team.reindexObject()
        new = team.modification_date
        self.assertNotEqual(old, new)

        creation_date_migrated = dateify(team.creation_date_migrated)
        modification_date_migrated = dateify(team.modification_date_migrated)
        self.assertEqual(old_creation_date, creation_date_migrated)
        self.assertEqual(old_modification_date, modification_date_migrated)

        new_creation_date = dateify(team.creation_date)
        new_modification_date = dateify(team.modification_date)
        self.assertNotEqual(old_creation_date, new_creation_date)
        self.assertNotEqual(old_modification_date, new_modification_date)

        # reset the dates
        request.form["form.submitted"] = True
        view = api.content.get_view("reset_dates", portal, request)
        view()

        # now all dates should be the same as before the export
        reset_creation_date = dateify(team.creation_date)
        reset_modification_date = dateify(team.modification_date)
        self.assertEqual(old_creation_date, reset_creation_date)
        self.assertEqual(old_modification_date, reset_modification_date)
        # the _migrated attributes are gone
        self.assertIsNone(getattr(team, "creation_date_migrated", None))
        self.assertIsNone(getattr(team, "cmodification_date_migrated", None))

        # check if index and metadata are correct
        catalog = api.portal.get_tool("portal_catalog")
        brain = api.content.find(UID=team.UID())[0]
        indexdata = catalog.getIndexDataForRID(brain.getRID())
        metadata = catalog.getMetadataForRID(brain.getRID())
        # metadata is correct
        self.assertEqual(dateify(metadata["modified"]), reset_modification_date)
        # index data is correct
        convert = catalog._catalog.indexes["modified"]._convert
        self.assertEqual(indexdata["modified"], convert(reset_modification_date))


def dateify(value):
    return value.asdatetime().replace(microsecond=0)
