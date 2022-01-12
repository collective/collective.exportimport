# -*- coding: utf-8 -*-
from collective.exportimport.fix_html import html_fixer
from collective.exportimport.testing import COLLECTIVE_EXPORTIMPORT_INTEGRATION_TESTING
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.textfield.value import RichTextValue
from plone.namedfile.file import NamedImage
from Products.CMFPlone.tests import dummy

import unittest


class TestFixHTML(unittest.TestCase):
    """Test that we can fix html."""

    layer = COLLECTIVE_EXPORTIMPORT_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        app = self.layer["app"]
        login(app, SITE_OWNER_NAME)

    def create_demo_content(self):
        """Create a portal structure which we can test against.
        Plone (portal root)
        |-- image
        |-- about
            |-- team
            `-- contact
        """
        portal = self.layer["portal"]

        self.about = api.content.create(
            container=portal,
            type="Folder",
            id="about",
            title=u"About",
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

    def test_html_fixer(self):
        # First create some content.
        self.create_demo_content()

        # link to uuid
        old_text = '<p><a class="some-class" href="resolveuid/{0}">Links to uuid</a></p>'.format(
            self.contact.UID()
        )
        fixed_html = '<p><a class="some-class" data-linktype="internal" data-val="{0}" href="resolveuid/{0}">Links to uuid</a></p>'.format(
            self.contact.UID()
        )
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # link to non-content
        old_text = '<p><a href="delete_confirmation">Link to view/form</a></p>'
        fixed_html = '<p><a href="delete_confirmation">Link to view/form</a></p>'
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # relative link to content
        old_text = '<p><a href="team">Link to content</a></p>'
        fixed_html = '<p><a data-linktype="internal" data-val="{0}" href="resolveuid/{0}">Link to content</a></p>'.format(
            self.team.UID()
        )
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # link to view with qs is unchanged
        old_text = '<a href="edit?somequery=foo" target="_self" title="">Link to view with query string</a><br/>'
        fixed_html = '<a href="edit?somequery=foo" target="_self" title="">Link to view with query string</a><br/>'
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # link to anchor is unchanged
        old_text = '<a href="#target">Link to anchor</a>'
        fixed_html = '<a href="#target">Link to anchor</a>'
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # image without scale
        old_text = '<img src="image" />'
        fixed_html = '<img class="image-richtext image-inline" data-linktype="image" data-scale="" data-val="{0}" src="resolveuid/{0}/@@images/image"/>'.format(
            self.image.UID()
        )
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # image with modern scale
        old_text = '<img src="image/@@images/image/large" />'
        fixed_html = '<img class="image-richtext image-inline" data-linktype="image" data-scale="large" data-val="{0}" src="resolveuid/{0}/@@images/image/large"/>'.format(
            self.image.UID()
        )
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

        # TODO: image scale is fixed, link to image with scale is not fixed yet
        old_text = (
            '<p><a href="image/image_preview"><img src="image/image_preview"/></a></p>'
        )
        fixed_html = '<p><a href="image/image_preview"><img class="image-richtext image-inline" data-linktype="image" data-scale="preview" data-val="{0}" src="resolveuid/{0}/@@images/image/preview"/></a></p>'.format(
            self.image.UID()
        )
        output = html_fixer(old_text, self.team)
        self.assertEqual(output, fixed_html)

    def test_fix_html_form(self):
        self.create_demo_content()
        old_text = """
<p><a class="some-class" href="resolveuid/{0}">Links to uuid</a></p>
<p><a href="delete_confirmation">Link to view/form</a></p>
<p><a href="team">Link to content</a></p>
<a href="edit?somequery=foo" target="_self" title="">Link to view with query string</a><br/>
<a href="#target">Link to anchor</a>
<img src="image" />
<img src="image/@@images/image/large" />
<p><a href="image/image_preview"><img src="image/image_preview"/></a></p>
""".format(
            self.contact.UID()
        )
        doc = api.content.create(
            container=self.about,
            type="Document",
            id="doc1",
            text=RichTextValue(old_text, "text/html", "text/x-html-safe"),
        )
        form = self.portal.restrictedTraverse("@@fix_html")
        html = form()
        self.assertIn("Fix links to content and images in richtext", html)
        self.request.form.update({
            "form.submitted": True,
            "form.commit": False,
        })
        html = form()
        self.assertIn("Fixed html", html)
        fixed_html = """
<p><a class="some-class" data-linktype="internal" data-val="{0}" href="resolveuid/{0}">Links to uuid</a></p>
<p><a href="delete_confirmation">Link to view/form</a></p>
<p><a data-linktype="internal" data-val="{1}" href="resolveuid/{1}">Link to content</a></p>
<a href="edit?somequery=foo" target="_self" title="">Link to view with query string</a><br/>
<a href="#target">Link to anchor</a>
<img class="image-richtext image-inline" data-linktype="image" data-scale="" data-val="{2}" src="resolveuid/{2}/@@images/image"/>
<img class="image-richtext image-inline" data-linktype="image" data-scale="large" data-val="{2}" src="resolveuid/{2}/@@images/image/large"/>
<p><a href="image/image_preview"><img class="image-richtext image-inline" data-linktype="image" data-scale="preview" data-val="{2}" src="resolveuid/{2}/@@images/image/preview"/></a></p>
""".format(
            self.contact.UID(), self.team.UID(), self.image.UID()
        )
        self.assertEqual(fixed_html, doc.text.raw)

    def test_fix_html_status_message(self):
        """Test that the status message displays the correct number of fields fixed."""
        self.create_demo_content()
        old_text = '<a href="about">Link to about that will be fixed.</a>'
        fixed_html = (
            '<a href="resolveuid/%s">Link to about that will be fixed.</a>'
            % self.about.UID()
        )
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="doc",
            title="Document 2",
            text=RichTextValue(old_text, "text/html", "text/x-html-safe"),
        )
        form = self.portal.restrictedTraverse("@@fix_html")
        html = form()
        self.assertIn("Fix links to content and images in richtext", html)
        self.request.form.update({
            "form.submitted": True,
            "form.commit": False,
        })
        html = form()
        self.assertEqual(fixed_html, doc.text.raw)
        self.assertIn(
            "Fixed HTML for 1 fields in content items. Fixed HTML for 0 portlets.",
            html,
        )

