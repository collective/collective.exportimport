# -*- coding: utf-8 -*-
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,  # noqa: E501,
)
from OFS.interfaces import IOrderedContainer
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing import zope

import json
import transaction
import unittest


class TestExport(unittest.TestCase):
    """Test that we can export."""

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

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
        self.assertIn("Export content using plone.restapi", browser.contents)
        self.assertIn("Export relations", browser.contents)
        self.assertIn("Export translations", browser.contents)
        self.assertIn("Export members", browser.contents)
        self.assertIn("Export local roles", browser.contents)
        self.assertIn("Export default pages", browser.contents)
        self.assertIn("Export object positions", browser.contents)
        # We cannot choose a portal_type, because there is no content to export.
        self.assertEqual(browser.getControl(name="portal_type").options, [""])

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
        self.assertEqual(portal_type.value, [""])
        self.assertIn("Document", portal_type.options)
        self.assertNotIn("Folder", portal_type.options)
        portal_type.value = ["Document"]
        browser.getControl("Export selected type").click()

        # We should have gotten json.
        data = json.loads(browser.contents)
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
        self.assertEqual(portal_type.value, [""])
        self.assertIn("Collection", portal_type.options)
        self.assertNotIn("Folder", portal_type.options)
        portal_type.value = ["Collection"]
        browser.getControl("Export selected type").click()

        # We should have gotten json.
        data = json.loads(browser.contents)
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
        doc1 = api.content.create(
            container=folder1, type="Document", id="doc1", title="Document 1"
        )
        doc2 = api.content.create(
            container=folder1, type="Document", id="doc2", title="Document 2"
        )
        doc3 = api.content.create(
            container=folder1, type="Document", id="doc3", title="Document 3"
        )
        folder2 = api.content.create(
            container=portal, type="Folder", id="folder2", title="Folder 2"
        )
        collection = api.content.create(
            container=folder2, type="Collection", id="collection1", title="Collection 1"
        )
        transaction.commit()

        # Now export complete portal.
        browser = self.open_page("@@export_contenttree")
        portal_types_to_export = browser.getControl(name="portal_types_to_export:list")
        self.assertEqual(portal_types_to_export.value, [])
        self.assertIn("Collection", portal_types_to_export.options)
        self.assertNotIn("News Item", portal_types_to_export.options)
        portal_types_to_export.value = ["Folder", "Document", "Collection"]

        path = browser.getControl(label="Path")
        self.assertEqual(path.value, "/plone")

        depth = browser.getControl(name="depth")
        self.assertEqual(depth.value, ["-1"])

        browser.getControl("Export tree").click()

        # We should have gotten json.
        data = json.loads(browser.contents)
        self.assertEqual(len(data), 6)

        # Check a few important keys.
        info = data[0]
        self.assertEqual(info["@id"], portal.absolute_url() + "/folder1")
        self.assertEqual(info["@type"], "Folder")
        self.assertEqual(info["title"], folder1.Title())

        # Export one tree.
        browser = self.open_page("@@export_contenttree")
        portal_types_to_export = browser.getControl(name="portal_types_to_export:list")
        portal_types_to_export.value = ["Folder", "Document", "Collection"]
        path = browser.getControl(label="Path")
        path.value = "/plone/folder1"
        browser.getControl("Export tree").click()

        # We should have gotten json.
        data = json.loads(browser.contents)
        self.assertEqual(len(data), 4)
        info = data[3]
        self.assertEqual(info["@id"], portal.absolute_url() + "/folder1/doc3")
        self.assertEqual(info["@type"], "Document")
        self.assertEqual(info["title"], doc3.Title())

        # Only one direct children.
        browser = self.open_page("@@export_contenttree")
        portal_types_to_export = browser.getControl(name="portal_types_to_export:list")
        portal_types_to_export.value = ["Folder", "Document", "Collection"]
        path = browser.getControl(label="Path")
        path.value = "/plone"
        depth = browser.getControl(name="depth")
        depth.value = ["1"]
        browser.getControl("Export tree").click()

        data = json.loads(browser.contents)
        self.assertEqual(len(data), 2)
        info = data[1]
        self.assertEqual(info["@id"], portal.absolute_url() + "/folder2")
        self.assertEqual(info["@type"], "Folder")
        self.assertEqual(info["title"], folder2.Title())


    def test_export_members(self):
        browser = self.open_page("@@export_members")
        browser.getForm(action='@@export_members').submit(name='form.submitted')
        data = json.loads(browser.contents)
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
        browser.getForm(action='@@export_defaultpages').submit(name='form.submitted')
        data = json.loads(browser.contents)
        self.assertListEqual(data, [])

    def test_export_defaultpages(self):
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        request = self.layer["request"]
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
        browser.getForm(action='@@export_defaultpages').submit(name='form.submitted')
        data = json.loads(browser.contents)
        self.assertListEqual(
            data,
            [{'default_page': 'doc1', 'uuid': folder1.UID()}],
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
        browser.getForm(action='@@export_ordering').submit(name='form.submitted')
        data = json.loads(browser.contents)

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
        browser.getForm(action='@@export_ordering').submit(name='form.submitted')
        data = json.loads(browser.contents)
        data_uuid2order = {}
        for item in data:
            data_uuid2order[item["uuid"]] = item["order"]
        self.assertEqual(data_uuid2order[doc3.UID()], 0)
        self.assertEqual(data_uuid2order[doc1.UID()], 1)
        self.assertEqual(data_uuid2order[doc2.UID()], 2)
