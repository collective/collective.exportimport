# -*- coding: utf-8 -*-
from collective.exportimport import config
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,  # noqa: E501,
)
from OFS.interfaces import IOrderedContainer
from plone import api
from plone.app.discussion.interfaces import IConversation
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from z3c.relationfield import RelationValue
from zope.annotation.interfaces import IAnnotations
from zope.component import createObject
from zope.component import getUtility
from zope.intid.interfaces import IIntIds
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


class TestExport(unittest.TestCase):
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
        self.assertIn("Export content", browser.contents)
        self.assertIn("Export relations", browser.contents)
        self.assertIn("Export translations", browser.contents)
        self.assertIn("Export members", browser.contents)
        self.assertIn("Export local roles", browser.contents)
        self.assertIn("Export default pages", browser.contents)
        self.assertIn("Export redirects", browser.contents)
        self.assertIn("Export object positions", browser.contents)
        # We cannot choose a portal_type, because there is no content to export.
        fti = self.layer["portal"].portal_types["Plone Site"]
        if "DexterityFTI" in repr(fti):
            # In Plone 6 the portal is exportable
            browser.getControl(name="portal_type")
        else:
            with self.assertRaises(LookupError):
                browser.getControl(name="portal_type")

    def test_export_content_document(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        transaction.commit()

        # Now export Documents.
        browser = self.open_page("@@export_content")
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("Document", portal_type.options)
        self.assertNotIn("Folder", portal_type.options)
        portal_type.value = ["Document"]
        try:
            # Plone 5.2
            browser.getForm(action="@@export_content").submit(name="submit")
        except LookupError:
            # Plone 5.1 and lower
            browser.getForm(index=1).submit()
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]

        # We should have gotten json.
        data = json.loads(contents)
        self.assertEqual(len(data), 1)

        # Check a few important keys.
        info = data[0]
        self.assertEqual(info["@id"], portal.absolute_url() + "/doc1")
        self.assertEqual(info["@type"], "Document")
        self.assertEqual(info["title"], doc.Title())

    def test_export_collection(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc = api.content.create(
            container=portal, type="Collection", id="collection1", title="Collection 1"
        )
        transaction.commit()

        # Now export content.
        browser = self.open_page("@@export_content")
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("Collection", portal_type.options)
        self.assertNotIn("Folder", portal_type.options)
        portal_type.value = ["Collection"]
        try:
            browser.getForm(action="@@export_content").submit(name="submit")
        except LookupError:
            # Plone 5.1 and lower
            browser.getForm(index=1).submit()
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]

        # We should have gotten json.
        data = json.loads(contents)
        self.assertEqual(len(data), 1)

        # Check a few important keys.
        info = data[0]
        self.assertEqual(info["@id"], portal.absolute_url() + "/collection1")
        self.assertEqual(info["@type"], "Collection")
        self.assertEqual(info["title"], doc.Title())

    def test_export_tree(self):
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
        doc3 = api.content.create(
            container=folder1, type="Document", id="doc3", title="Document 3"
        )
        folder2 = api.content.create(
            container=portal, type="Folder", id="folder2", title="Folder 2"
        )
        api.content.create(
            container=folder2, type="Collection", id="collection1", title="Collection 1"
        )
        transaction.commit()

        # Now export complete portal.
        browser = self.open_page("@@export_content")
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("Collection", portal_type.options)
        self.assertNotIn("News Item", portal_type.options)
        portal_type.value = ["Folder", "Document", "Collection"]

        path = browser.getControl(label="Path")
        self.assertEqual(path.value, "/plone")

        depth = browser.getControl(name="depth")
        self.assertEqual(depth.value, ["-1"])

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
        self.assertEqual(len(data), 6)

        # Check a few important keys.
        info = data[0]
        self.assertEqual(info["@id"], portal.absolute_url() + "/folder1")
        self.assertEqual(info["@type"], "Folder")
        self.assertEqual(info["title"], folder1.Title())

        # Export one tree.
        browser = self.open_page("@@export_content")
        portal_type = browser.getControl(name="portal_type")
        portal_type.value = ["Folder", "Document", "Collection"]
        path = browser.getControl(label="Path")
        path.value = "/plone/folder1"
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
        self.assertEqual(len(data), 4)
        info = data[3]
        self.assertEqual(info["@id"], portal.absolute_url() + "/folder1/doc3")
        self.assertEqual(info["@type"], "Document")
        self.assertEqual(info["title"], doc3.Title())

        # Only one direct children.
        browser = self.open_page("@@export_content")
        portal_type = browser.getControl(name="portal_type")
        portal_type.value = ["Folder", "Document", "Collection"]
        path = browser.getControl(label="Path")
        path.value = "/plone"
        depth = browser.getControl(name="depth")
        depth.value = ["1"]
        try:
            # Plone 5.2
            browser.getControl("Export").click()
            contents = browser.contents
        except LookupError:
            # Plone 5.1 and lower
            browser.getForm(index=1).submit()
            if not browser.contents:
                contents = DATA[-1]

        data = json.loads(contents)
        self.assertEqual(len(data), 2)
        info = data[1]
        self.assertEqual(info["@id"], portal.absolute_url() + "/folder2")
        self.assertEqual(info["@type"], "Folder")
        self.assertEqual(info["title"], folder2.Title())

    def test_export_members(self):
        browser = self.open_page("@@export_members")
        browser.getForm(action="@@export_members").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertIn("groups", data.keys())
        self.assertIn("members", data.keys())

        # Check groups.
        groups = data["groups"]
        groupids = [group["groupid"] for group in groups]
        self.assertIn("Administrators", groupids)
        self.assertIn("Reviewers", groupids)
        self.assertIn("Site Administrators", groupids)

        # Check members.
        members = data["members"]
        membernames = [member["username"] for member in members]
        self.assertIn(TEST_USER_ID, membernames)
        for member in members:
            if member["username"] == TEST_USER_ID:
                self.assertTrue(member["roles"], ["Member"])

    def test_export_defaultpages_empty(self):
        browser = self.open_page("@@export_defaultpages")
        browser.getForm(action="@@export_defaultpages").submit(name="form.submitted")
        self.assertIn("No data to export for export_defaultpages", browser.contents)

    def test_export_defaultpages(self):
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

        browser = self.open_page("@@export_defaultpages")
        browser.getForm(action="@@export_defaultpages").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertListEqual(
            data,
            [
                {
                    "default_page": "doc1",
                    "uuid": folder1.UID(),
                    "default_page_uuid": doc1.UID(),
                }
            ],
        )

    def test_export_defaultpages_download_to_server(self):
        # First create some content. (same as above)
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

        browser = self.open_page("@@export_defaultpages")
        browser.getControl("Save to file on server").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_defaultpages").submit(
                name="form.submitted"
            )
            msg = "Exported to {}/export_defaultpages.json".format(
                config.CENTRAL_DIRECTORY
            )
            self.assertIn(msg, browser.contents)
            path = os.path.join(config.CENTRAL_DIRECTORY, "export_defaultpages.json")
            with open(path, "rb") as f:
                data = json.load(f)
                self.assertListEqual(
                    data,
                    [
                        {
                            "default_page": "doc1",
                            "uuid": folder1.UID(),
                            "default_page_uuid": doc1.UID(),
                        }
                    ],
                )
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_export_defaultpage_for_site(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc1 = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        portal._setProperty("default_page", "doc1")
        transaction.commit()

        browser = self.open_page("@@export_defaultpages")
        browser.getForm(action="@@export_defaultpages").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertListEqual(
            data,
            [
                {
                    "default_page": "doc1",
                    "uuid": config.SITE_ROOT,
                    "default_page_uuid": doc1.UID(),
                }
            ],
        )

    def test_export_relations(self):
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc1 = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        doc2 = api.content.create(
            container=portal, type="Document", id="doc2", title="Document 2"
        )
        intids = getUtility(IIntIds)
        doc1.relatedItems = [RelationValue(intids.getId(doc2))]
        modified(doc1)
        transaction.commit()

        browser = self.open_page("@@export_relations")
        browser.getForm(action="@@export_relations").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertListEqual(
            data,
            [
                {
                    u"to_uuid": doc2.UID(),
                    u"relationship": u"relatedItems",
                    u"from_uuid": doc1.UID(),
                }
            ],
        )

    def test_export_discussion(self):
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc1 = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        conversation = IConversation(doc1)
        comment = createObject("plone.Comment")
        comment.text = u"Comment text"
        conversation.addComment(comment)
        transaction.commit()

        browser = self.open_page("@@export_discussion")
        browser.getForm(action="@@export_discussion").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertEqual(data[0]["uuid"], doc1.UID())
        self.assertEqual(
            data[0]["conversation"]["items"][0]["text"]["data"], "Comment text"
        )

    def test_export_ordering(self):
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
        browser.getForm(action="@@export_ordering").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)

        # Turn the list into a dict for easier searching and comparing.
        data_uuid2order = {}
        for item in data:
            data_uuid2order[item["uuid"]] = item["order"]
        data_uuids = sorted(data_uuid2order.keys())

        # All content UIDs are in the export:
        content_uuids = sorted([item.UID() for item in (folder1, doc1, doc2, doc3)])
        self.assertListEqual(data_uuids, content_uuids)

        # All documents have the correct order:
        self.assertEqual(data_uuid2order[doc1.UID()], 0)
        self.assertEqual(data_uuid2order[doc2.UID()], 1)
        self.assertEqual(data_uuid2order[doc3.UID()], 2)

        # Reorder the documents.
        ordered = IOrderedContainer(folder1)
        ordered.moveObjectsToTop(["doc3"])
        transaction.commit()

        # Export and check.
        browser = self.open_page("@@export_ordering")
        browser.getForm(action="@@export_ordering").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        data_uuid2order = {}
        for item in data:
            data_uuid2order[item["uuid"]] = item["order"]
        self.assertEqual(data_uuid2order[doc3.UID()], 0)
        self.assertEqual(data_uuid2order[doc1.UID()], 1)
        self.assertEqual(data_uuid2order[doc2.UID()], 2)

    def test_export_redirects_empty(self):
        browser = self.open_page("@@export_redirects")
        browser.getForm(action="@@export_redirects").submit(name="form.submitted")
        self.assertIn("No data to export for export_redirects", browser.contents)

    def test_export_redirects(self):
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

        browser = self.open_page("@@export_redirects")
        browser.getForm(action="@@export_redirects").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertDictEqual(
            data,
            {
                u"/plone/doc1": u"/plone/doc1-moved",
                u"/plone/doc2": u"/plone/doc2-moved",
            },
        )

    def test_export_local_roles(self):
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        doc1 = api.content.create(
            container=portal, type="Document", id="doc1", title="Document 1"
        )
        doc2 = api.content.create(
            container=portal, type="Document", id="doc2", title="Document 2"
        )
        intids = getUtility(IIntIds)
        doc1.relatedItems = [RelationValue(intids.getId(doc2))]
        modified(doc1)
        transaction.commit()

        browser = self.open_page("@@export_localroles")
        browser.getForm(action="@@export_localroles").submit(name="form.submitted")
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]
        data = json.loads(contents)
        self.assertListEqual(
            data,
            [
                {"uuid": doc1.UID(), "localroles": {"admin": ["Owner"]}},
                {"uuid": doc2.UID(), "localroles": {"admin": ["Owner"]}},
                {"uuid": "<Portal>", "localroles": {"admin": ["Owner"]}},
            ],
        )

    def test_export_versions(self):
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
            title="Document 1",
            description="A Description",
        )
        folder1 = api.content.create(
            container=portal,
            type="Folder",
            id="folder1",
            title="Folder 1",
        )
        doc2 = api.content.create(
            container=folder1,
            type="Document",
            id="doc2",
            title="Document 2",
            description="A Description",
        )

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

        item = data[2]
        self.assertEqual(item["@id"], portal.absolute_url() + "/folder1/doc2")

        # check versions
        self.assertIn("exportimport.versions", item)
        versions = item["exportimport.versions"]
        self.assertEqual(len(versions), 2)

        # check first version
        self.assertEqual(versions["0"]["title"], u"Document 2")
        self.assertEqual(versions["0"]["description"], u"A Description")
        self.assertEqual(versions["0"]["changeNote"], u"initial_version_changeNote")

        # check version 2
        self.assertEqual(versions["1"]["title"], u"Document 2 with changed title")
        self.assertEqual(versions["1"]["description"], u"A Description")
        self.assertEqual(versions["1"]["changeNote"], u"Föö bar")

        # final/current version is the item itself
        self.assertEqual(item["title"], u"Document 2 with changed title")
        self.assertEqual(item["description"], u"New description in revision 3")
        self.assertEqual(item["changeNote"], u"I am new!")

    def test_export_blob_as_base64(self):
        # First create some content with blobs.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        from plone.namedfile.file import NamedBlobFile

        filepath = os.path.join(os.path.dirname(__file__), "file.pdf")
        with open(filepath, "rb") as f:
            file_data = f.read()
        file1 = api.content.create(
            container=portal,
            type="File",
            id="file1",
            title=u"File 1",
        )
        file1.file = NamedBlobFile(data=file_data, filename=u"file.pdf")
        transaction.commit()

        # Now export
        browser = self.open_page("@@export_content")
        self.assertEqual(browser.getControl(name="include_blobs").value, ["1"])
        browser.getControl(name="include_blobs").value = ["1"]
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("File", portal_type.options)
        portal_type.value = ["File"]
        try:
            # Plone 5.2
            browser.getForm(action="@@export_content").submit(name="submit")
        except LookupError:
            # Plone 5.1 and lower
            browser.getForm(index=1).submit()
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]

        # We should have gotten json.
        data = json.loads(contents)
        self.assertEqual(len(data), 1)

        # Check a few important keys.
        info = data[0]
        self.assertEqual(info["@id"], portal.absolute_url() + "/file1")
        self.assertEqual(info["@type"], "File")
        self.assertEqual(info["title"], file1.Title())
        self.assertEqual(info["file"]["content-type"], "application/pdf")
        self.assertEqual(info["file"]["filename"], "file.pdf")
        self.assertTrue(info["file"]["data"].startswith("JVBERi0xLjQKJcOkw7zDtsOf"))
        self.assertEqual(info["file"]["encoding"], "base64")

    def test_export_blob_as_download_urls(self):
        # First create some content with blobs.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        from plone.namedfile.file import NamedBlobFile

        filepath = os.path.join(os.path.dirname(__file__), "file.pdf")
        with open(filepath, "rb") as f:
            file_data = f.read()
        file1 = api.content.create(
            container=portal,
            type="File",
            id="file1",
            title=u"File 1",
        )
        file1.file = NamedBlobFile(data=file_data, filename=u"file.pdf")
        transaction.commit()

        # Now export
        browser = self.open_page("@@export_content")
        self.assertEqual(browser.getControl(name="include_blobs").value, ["1"])
        browser.getControl(name="include_blobs").value = ["0"]
        portal_type = browser.getControl(name="portal_type")
        self.assertEqual(portal_type.value, [])
        self.assertIn("File", portal_type.options)
        portal_type.value = ["File"]
        try:
            # Plone 5.2
            browser.getForm(action="@@export_content").submit(name="submit")
        except LookupError:
            # Plone 5.1 and lower
            browser.getForm(index=1).submit()
        contents = browser.contents
        if not browser.contents:
            contents = DATA[-1]

        # We should have gotten json.
        data = json.loads(contents)
        self.assertEqual(len(data), 1)

        # Check a few important keys.
        info = data[0]
        self.assertEqual(info["@id"], portal.absolute_url() + "/file1")
        self.assertEqual(info["@type"], "File")
        self.assertEqual(info["title"], file1.Title())
        self.assertEqual(info["file"]["content-type"], "application/pdf")
        self.assertEqual(info["file"]["filename"], "file.pdf")
        self.assertEqual(info["file"]["download"], "http://nohost/plone/file1/@@download/file")
        self.assertEqual(info["file"]["size"], 8561)
