# -*- coding: utf-8 -*-
from six.moves.urllib.parse import unquote, urlparse

import json
import os


class FileSystemExporter(object):
    """Base FS Exporter"""

    def __init__(self, rootpath, json_item):
        self.item = json_item
        self.root = rootpath

    def create_dir(self, dirname):
        """Creates a directory if does not exist

        Args:
            dirname (str): dirname to be created
        """
        dirpath = os.path.join(self.root, dirname)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

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

    def save(self):
        """Saves a json file to filesystem tree
        Target directory is related as original parent position in site.
        """
        parent_path = self.get_parents(self.item.get("parent"))
        self.create_dir(parent_path)

        filename = "%s_%s.json" % (self.item.get("@type"), self.item.get("UID"))
        filepath = os.path.join(self.root, parent_path, filename)
        with open(filepath, "w") as f:
            json.dump(self.item, f, sort_keys=True, indent=4)
