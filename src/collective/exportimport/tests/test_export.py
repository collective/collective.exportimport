# -*- coding: utf-8 -*-
from collective.exportimport.testing import COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING  # noqa: E501
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.testing import z2

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
