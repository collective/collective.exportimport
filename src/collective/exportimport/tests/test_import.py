# -*- coding: utf-8 -*-
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,  # noqa: E501,,
)
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing import z2

import json
import six
import transaction
import unittest


# TODO: change this to skip the tests on Plone 5.1 and lower.
# Python 2 on 5.2 should be fine, but currently it gives an error when
# importing the modified date:
# ValueError: 'z' is a bad directive in format '%Y-%m-%dT%H:%M:%S%z'
@unittest.skipIf(six.PY2, "Import is only supported on Python 3 for the moment")
class TestImport(unittest.TestCase):
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
        upload.add_file(raw_data, "application/json", "documents.json")
        browser.getForm(action="@@import_content").submit()
        # Note: when we upload the data with filename foo.json,
        # the status message will be "Imported 1 foo".
        self.assertIn("Imported 1 documents", browser.contents)

        # The document should be back.
        self.assertIn("doc1", portal.contentIds())
        new_doc = portal["doc1"]
        self.assertEqual(new_doc.Title(), "Document 1")
