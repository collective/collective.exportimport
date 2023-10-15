# -*- coding: utf-8 -*-
from App.config import getConfiguration
from collective.exportimport import config
from collective.exportimport.testing import (
    COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING,  # noqa: E501,
)
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedImage
from Products.CMFPlone.tests import dummy

import json
import os
import shutil
import six
import tempfile
import transaction
import unittest

if six.PY2:
    from pathlib2 import Path
else:
    from pathlib import Path


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


class TestHierarchicalImport(unittest.TestCase):
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

    def create_demo_content(self):
        """Create a portal structure which we can test against.
        Plone (portal root)
        |-- blog
        |-- folder1
        |   |-- doc1
        |   |-- folder2_1
        |       |-- doc3
        |-- folder2
        |   |-- doc2
        |-- image
        """
        portal = self.layer["portal"]
        self.link = api.content.create(
            container=portal,
            type="Link",
            id="blog",
            title=u"Blog",
        )
        self.folder1 = api.content.create(
            container=portal, type="Folder", id="folder1", title="Folder 1"
        )
        self.doc1 = api.content.create(
            container=self.folder1, type="Document", id="doc1", title="Document 1"
        )
        self.folder2 = api.content.create(
            container=portal, type="Folder", id="folder2", title="Folder 2"
        )
        self.folder2_1 = api.content.create(
            container=self.folder1, type="Folder", id="folder2-1", title="Folder 2.1"
        )
        self.doc2 = api.content.create(
            container=self.folder2, type="Document", id="doc2", title="Document 2"
        )
        self.doc3 = api.content.create(
            container=self.folder2_1, type="Document", id="doc3", title="Document 3"
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
        api.content.delete(portal["blog"])
        api.content.delete(portal["folder1"])
        api.content.delete(portal["folder2"])
        api.content.delete(portal["image"])

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
        """Tests the import page"""
        # Simply test that some text is on the page.
        browser = self.open_page("@@import_content")
        # Let's compare lowercase.
        lower_contents = browser.contents.lower()
        self.assertIn("import content", lower_contents)
        self.assertIn(
            "or you can choose from a tree export in the server in one of these paths:",
            lower_contents
        )

    def test_import_content_from_server_tree(self):
        """Tests a complete import"""
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Remove all content
            self.remove_demo_content()
            transaction.commit()

            self.assertNotIn("doc1", portal.contentIds())

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back.
            self.assertIn("doc1", portal["folder1"].contentIds())
            new_doc = portal["folder1"]
            self.assertEqual(new_doc.Title(), "Folder 1")
            self.assertEqual(new_doc.portal_type, "Folder")
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_import_update_from_server_tree(self):
        """Tests a complete import with update"""
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Remove all content
            self.remove_demo_content()
            transaction.commit()

            self.assertNotIn("doc1", portal.contentIds())

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back.
            self.assertIn("doc1", portal["folder1"].contentIds())
            self.assertEqual(portal["folder1"].Title(), "Folder 1")
            folder_uid = portal["folder1"].UID()
            # Change exported file and upload again.
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "2_folder1.json"
                )
            with open(file_path, "r+") as f:
                data = json.load(f)
                data["title"] = "Folder 1. Updated."
                f.seek(0)
                json.dump(data, f, sort_keys=True, indent=4)
                f.truncate()  # if file content was larger

            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)
            self.assertIn("folder1", portal.contentIds())
            new_folder = portal["folder1"]
            self.assertEqual(new_folder.Title(), "Folder 1. Updated.")
            self.assertEqual(new_folder.UID(), folder_uid)
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_import_replace_from_server_tree(self):
        """Tests a complete import with replace

        A Connection closed error is raised if Plone Site is in the
        export and the replace option is selected.
        """
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Remove all content
            self.remove_demo_content()
            transaction.commit()

            self.assertNotIn("doc1", portal.contentIds())

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back.
            self.assertIn("doc1", portal["folder1"].contentIds())
            self.assertEqual(portal["folder1"].Title(), "Folder 1")
            folder_uid = portal["folder1"].UID()

            # Change exported file and upload again.
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "2_folder1.json"
                )
            with open(file_path, "r+") as f:
                data = json.load(f)
                data["title"] = "Folder 1. Updated."
                f.seek(0)
                json.dump(data, f, sort_keys=True, indent=4)
                f.truncate()  # if file content was larger

            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["1"]  # replace!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)
            self.assertIn("folder1", portal.contentIds())
            new_folder = portal["folder1"]
            self.assertEqual(new_folder.Title(), "Folder 1. Updated.")
            self.assertEqual(new_folder.UID(), folder_uid)
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_fresh_import_moved_non_folderish_item(self):
        """Hierarchical import allows to move content across
        the directory structure.
        Moved item should be created in the actual path where the
        json file is placed.

        From Plone 6+, many content types become folderish so during
        export process a json file and a subdirectory are created for
        each folderish item.

        For non-folderish items just a json file is created.
        """
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Remove all content
            self.remove_demo_content()
            transaction.commit()

            self.assertNotIn("image", portal.contentIds())

            # Move 2_image.json inside a subfolder
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "8_image.json"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder2",
                    "8_image.json"
                )
            shutil.move(file_path, target_path)

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertNotIn("image", portal.contentIds())
            self.assertIn("image", portal["folder2"].contentIds())
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_fresh_import_moved_folderish_item(self):
        """Hierarchical import allows to move content across
        the directory structure.
        Moved item should be created in the actual path where the
        json file is placed.

        From Plone 6+, many content types become folderish so during
        export process a json file and a subdirectory are created for
        each folderish item.

        For non-folderish items just a json file is created.

        Here we will test how to move a folderish item inside other
        If only json file is moved, the contentish object will be 
        created into the target location but his children will remain
        in the same path.
        Both json file and subfolder must be moved in order to move
        all content to target location.
        """
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Remove all content
            self.remove_demo_content()
            transaction.commit()

            self.assertNotIn("image", portal.contentIds())

            # Move 2_image.json inside a subfolder
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "2_folder1.json"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder2",
                    "2_folder1.json"
                )
            shutil.move(file_path, target_path)

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertIn("folder1", portal["folder2"].contentIds())

            # As subfolder wasn't moved, a folder1 has been also created
            # at his original place.
            self.assertNotIn("folder1", portal.contentIds())
            self.assertIn("doc1", portal["folder2"]["folder1"].contentIds())

            # Move now folder1 subdir into folder2
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder1"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder2",
                    "folder1"
                )
            shutil.move(file_path, target_path)

            # Remove all content
            api.content.delete(portal["blog"])
            api.content.delete(portal["folder2"])
            api.content.delete(portal["image"])
            transaction.commit()

            # Now re-import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertIn("folder1", portal["folder2"].contentIds())
            # Now, children should be created under folder2
            self.assertNotIn("folder1", portal.contentIds())
            self.assertIn("doc1", portal["folder2"]["folder1"].contentIds())
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory


    def test_update_import_moved_non_folderish_item(self):
        """Hierarchical import allows to move content across
        the directory structure.
        Moved item should be created in the actual path where the
        json file is placed.

        From Plone 6+, many content types become folderish so during
        export process a json file and a subdirectory are created for
        each folderish item.

        For non-folderish items just a json file is created.

        Testing moving items without deleting previous content
        """
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Move 2_image.json inside a subfolder
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "8_image.json"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder2",
                    "8_image.json"
                )
            shutil.move(file_path, target_path)

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertNotIn("image", portal.contentIds())
            self.assertIn("image", portal["folder2"].contentIds())
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_update_import_moved_folderish_item(self):
        """Hierarchical import allows to move content across
        the directory structure.
        Moved item should be created in the actual path where the
        json file is placed.

        From Plone 6+, many content types become folderish so during
        export process a json file and a subdirectory are created for
        each folderish item.

        For non-folderish items just a json file is created.

        Here we will test how to move a folderish item inside other
        If only json file is moved, the contentish object will be 
        created into the target location but his children will remain
        in the same path.
        Both json file and subfolder must be moved in order to move
        all content to target location.
        """
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Move 2_image.json inside a subfolder
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "2_folder1.json"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder2",
                    "2_folder1.json"
                )
            shutil.move(file_path, target_path)

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertIn("folder1", portal["folder2"].contentIds())

            # As subfolder wasn't moved, a folder1 has been also created
            # at his original place.
            self.assertNotIn("folder1", portal.contentIds())
            self.assertIn("doc1", portal["folder2"]["folder1"].contentIds())

            # Move now folder1 subdir into folder2
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder1"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "folder2",
                    "folder1"
                )
            shutil.move(file_path, target_path)

            # Now re-import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertIn("folder1", portal["folder2"].contentIds())
            # Now, children should be created under folder2
            self.assertNotIn("folder1", portal.contentIds())
            self.assertIn("doc1", portal["folder2"]["folder1"].contentIds())
        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory

    def test_delete_items(self):
        """Hierarchical also allows to remove elements from site
        without losing the json file. Just move it to the 
        removed_items directory and the item will be deleted in portal.
        """
        # First create some content.
        app = self.layer["app"]
        portal = self.layer["portal"]
        login(app, SITE_OWNER_NAME)
        self.create_demo_content()
        transaction.commit()

        # Now export it to a file on the server.
        browser = self.open_page("@@export_content")
        browser.getControl(name="portal_type").value = [
            "Folder",
            "Document",
            "Link",
            "Image"]
        browser.getControl(
            "Generate a file for each item (as filesytem tree)").selected = True
        original_central_directory = config.CENTRAL_DIRECTORY
        try:
            config.CENTRAL_DIRECTORY = tempfile.mkdtemp()
            browser.getForm(action="@@export_content").submit()

            msg = "Exported 8 items (Folder, Image, Link, Document) as tree to {}/exported_tree/{}/content".format(
                config.CENTRAL_DIRECTORY,
                portal.getId()
            )
            self.assertIn(msg, browser.contents)

            # Move 2_image.json inside a subfolder
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "1_blog.json"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "removed_items",
                    "1_blog.json"
                )
            shutil.move(file_path, target_path)

            # Now import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 7 items", browser.contents)
            self.assertIn("Deleted 1 items", browser.contents)

            # As subfolder wasn't moved, a folder1 has been also created
            # at his original place.
            self.assertNotIn("blog", portal.contentIds())

            # Restore content
            file_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "removed_items",
                    "1_blog.json"
                )
            target_path = os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content",
                    "1_blog.json",
                )
            shutil.move(file_path, target_path)

            # Now re-import it.
            browser = self.open_page("@@import_content")
            server_file = browser.getControl(name="server_tree_file")
            server_file.value = [
                os.path.join(
                    config.CENTRAL_DIRECTORY,
                    "exported_tree",
                    portal.getId(),
                    "content"
                )
            ]
            browser.getControl(name="handle_existing_content").value = ["2"]  # update!
            browser.getForm(action="@@import_content").submit()
            self.assertIn("Imported 8 items", browser.contents)

            # Content should be back to the new location
            self.assertIn("blog", portal.contentIds())

        finally:
            shutil.rmtree(config.CENTRAL_DIRECTORY)
            config.CENTRAL_DIRECTORY = original_central_directory
