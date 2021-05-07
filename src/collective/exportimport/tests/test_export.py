# -*- coding: utf-8 -*-
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,  # noqa: E501,
)
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing import z2

import json
import transaction
import unittest


class TestExport(unittest.TestCase):
    """Test that we can export."""

    layer = COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING

    def open_page(self, page):
        """Create a testbrowser, open a page, return the browser."""
        browser = z2.Browser(self.layer["app"])
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

    def test_export_members(self):
        browser = self.open_page("@@export_members")
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
        data = json.loads(browser.contents)
        self.assertListEqual(data, [])

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
        data = json.loads(browser.contents)
        self.assertListEqual(
            data,
            [{'default_page': 'doc1', 'uuid': folder1.UID()}],
        )
