# -*- coding: utf-8 -*-
from glob import iglob
from plone import api
from six.moves.urllib.parse import unquote, urlparse

import json
import logging
import os
import six


if six.PY2:
    from pathlib2 import Path
else:
    from pathlib import Path


class FileSystemImporter(object):
    """Base FS Importer"""

    logger = logging.getLogger(__name__)

    def __init__(self, server_tree_file):
        self.path = server_tree_file

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


class FileSystemContentImporter(FileSystemImporter):
    """Deserializes JSON items into a FS tree"""

    def list_files(self):
        """Loads all json files from filesystem tree"""
        files = iglob(os.path.join(self.path, "**/*.json"), recursive=True)
        return files

    def get_hierarchical_files(self):
        """Gets all files and folders"""
        root = Path(self.path)
        portal = api.portal.get()
        assert root.is_dir()
        json_files = root.glob("**/*.json")
        for json_file in json_files:
            self.logger.debug("Importing %s", json_file)
            item = json.loads(json_file.read_text())
            item["json_file"] = str(json_file)

            # Modify parent data
            json_parent = item.get("parent", {})

            # Find the real parent nodes
            prefix = os.path.commonprefix([str(json_file.parent), self.path])
            path = os.path.relpath(str(json_file.parent), prefix)
            parents = self.get_parents(json_parent)

            if json_file.parent == Path(os.path.join(self.path, parents)):
                yield item
            else:
                try:
                    parent_obj = portal.unrestrictedTraverse(path)
                except KeyError:
                    parent_obj = portal

                if parent_obj:
                    item["@id"] = item.get("@id")
                    json_parent.update(
                        {"@id": parent_obj.absolute_url(), "UID": parent_obj.UID()}
                    )
                    item["parent"] = json_parent
                yield item
