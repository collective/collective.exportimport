# -*- coding: utf-8 -*-
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,
)  # noqa: E501
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing import z2

import json
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
        # browser.getControl(name="portal_type").value = ["Document"]

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
