# -*- coding: utf-8 -*-
from collective.exportimport import _
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

    def __init__(self, context, server_tree_file):
        self.path = server_tree_file
        self.context = context

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
            json_parent = item.get("parent", {})

            # Find the real parent nodes as they could be moved
            # among directories
            prefix = os.path.commonprefix([str(json_file.parent), self.path])

            # relative path will be the diference between base export path
            # and the position of the json file
            relative_path = os.path.relpath(str(json_file.parent), prefix)
            parent_path = "%s/%s" % (
                "/".join(self.context.getPhysicalPath()),
                relative_path)
            parents = self.get_parents(json_parent)

            if json_file.parent == Path(os.path.join(self.path, parents)):
                yield item
            else:
                parent_obj = api.content.get(path=parent_path)
                if not parent_obj:
                    # if parent_path is "." or parent_obj doesn't yet exist
                    parent_obj = portal

                # Modify parent data into json to be yield
                # local files won't be modified
                if parent_obj:
                    self.delete_old_if_moved(item.get("UID"))
                    item["@id"] = item.get("@id")
                    json_parent.update(
                        {"@id": parent_obj.absolute_url(), "UID": parent_obj.UID()}
                    )
                    item["parent"] = json_parent
                yield item

    def delete_old_if_moved(self, UID):
        """Checks if json file was moved by
        getting object by UID. If exists, removes object"""
        check_if_moved = api.content.get(UID=UID)
        if check_if_moved:
            # delete all object
            api.content.delete(obj=check_if_moved, check_linkintegrity=False)
            self.logger.info("Removed old object %s", check_if_moved.UID)

    def process_deleted(self):
        """Will process all elements in removed_items dir"""
        root = Path(self.path).parent
        removed_items_dir = root / "removed_items"
        json_files = removed_items_dir.glob("**/*.json")
        deleted_items = []
        for json_file in json_files:
            self.logger.debug("Deleting %s", json_file)
            item = json.loads(json_file.read_text())
            uid = item.get("UID")
            obj = api.content.get(UID=uid)
            if obj:
                api.content.delete(obj=obj, check_linkintegrity=False)
                self.logger.info("Deleted object %s", item.get("UID"))
                deleted_items.append(uid)

        return self.context.translate(
            _(
                "deleted_items_msg",
                default=u"Deleted ${items} items.",
                mapping={u"items": len(deleted_items)}
            )
        )
