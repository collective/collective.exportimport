# -*- coding: utf-8 -*-
from App.config import getConfiguration
from collective.exportimport import config
from plone import api
from six.moves.urllib.parse import unquote, urlparse

import json
import logging
import os


class FileSystemExporter(object):
    """Base FS Exporter"""

    logger = logging.getLogger(__name__)

    def __init__(self):
        self._create_base_dirs()

    def _create_base_dirs(self):
        """Creates base content directory and subdir deleted_items"""
        # Will generate a directory tree with one json file per item
        portal_id = api.portal.get().getId()
        directory = config.CENTRAL_DIRECTORY
        if not directory:
            cfg = getConfiguration()
            directory = cfg.clienthome

        self.root = os.path.join(
            directory, "exported_tree/%s/content" % portal_id
        )
        self._make_dir(self.root)

        remove_dir = os.path.join(
            directory, "exported_tree/%s/removed_items" % portal_id
        )
        self._make_dir(remove_dir)

        return self.root

    def _make_dir(self, path):
        """Make directory"""
        if not os.path.exists(path):
            os.makedirs(path)
            self.logger.info("Created path %s", path)

    def create_dir(self, dirname):
        """Creates a directory if does not exist

        Args:
            dirname (str): dirname to be created
        """
        dirpath = os.path.join(self.root, dirname)
        self._make_dir(dirpath)

    def get_parents(self, parent):
        """Extracts parents of item

        Args:
            parent (dict): Parent info dict

        Returns:
            (str): relative path
        """

        if not parent:
            return ""

        parent_url = unquote(parent["@id"])
        parent_url_parsed = urlparse(parent_url)

        # Get the path part, split it, remove the always empty first element.
        parent_path = parent_url_parsed.path.split("/")[1:]
        if (
            len(parent_url_parsed.netloc.split(":")) > 1
            or parent_url_parsed.netloc == "nohost"
        ):
            # For example localhost:8080, or nohost when running tests.
            # First element will then be a Plone Site id.
            # Get rid of it.
            parent_path = parent_path[1:]

        return "/".join(parent_path)


class FileSystemContentExporter(FileSystemExporter):
    """Deserializes JSON items into a FS tree"""

    def save(self, number, item):
        """Saves a json file to filesystem tree
        Target directory is related as original parent position in site.
        """

        parent_path = self.get_parents(item.get("parent"))

        if item.get("is_folderish", False):
            item_path = os.path.join(parent_path, item.get("id"))
            self.create_dir(item_path)
        else:
            self.create_dir(parent_path)

        # filename = "%s_%s_%s.json" % (number, item.get("@type"), item.get("UID"))
        filename = "%s_%s.json" % (number, item.get("id"))
        filepath = os.path.join(self.root, parent_path, filename)
        with open(filepath, "w") as f:
            json.dump(item, f, sort_keys=True, indent=4)
