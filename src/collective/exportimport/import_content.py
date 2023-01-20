# -*- coding: utf-8 -*-
from Acquisition import aq_base
from collective.exportimport import config
from collective.exportimport.interfaces import IMigrationMarker
from datetime import datetime
from DateTime import DateTime
from datetime import timedelta
from Persistence import PersistentMapping
from plone import api
from plone.api.exc import InvalidParameterError
from plone.dexterity.interfaces import IDexterityFTI
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from plone.restapi.interfaces import IDeserializeFromJson
from Products.CMFPlone.interfaces.constrains import ENABLED
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes
from Products.CMFPlone.utils import _createObjectByType
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from six.moves.urllib.parse import unquote
from six.moves.urllib.parse import urlparse
from zExceptions import NotFound
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.interface import alsoProvides
from ZPublisher.HTTPRequest import FileUpload

import dateutil
import ijson
import json
import logging
import os
import random
import six
import transaction

try:
    from plone.app.querystring.upgrades import fix_select_all_existing_collections

    HAS_COLLECTION_FIX = True
except ImportError:
    HAS_COLLECTION_FIX = False

logger = logging.getLogger(__name__)
BLOB_HOME = os.getenv("COLLECTIVE_EXPORTIMPORT_BLOB_HOME", "")


def get_absolute_blob_path(obj, blob_path):
    """Get absolute path to a blob.

    If the BLOB_HOME variable is set, try to use this.

    If the blob is not found there, try the blobstorage of the current ZODB.
    The blob may be an export from a different Plone Site in the same database.
    Or the blobstorage from the old 4.3 site may have been copied
    or hard linked to the new 5.2 site.
    """
    if os.path.isabs(blob_path):
        if os.path.isfile(blob_path):
            return blob_path
        return
    if BLOB_HOME:
        abs_path = os.path.join(BLOB_HOME, blob_path)
        if os.path.isfile(abs_path):
            return abs_path
    # Try the blobstorage of the current ZODB.
    db = obj._p_jar.db()
    fshelper = db._storage.fshelper
    abs_path = os.path.join(fshelper.base_dir, blob_path)
    if os.path.isfile(abs_path):
        return abs_path


class ImportContent(BrowserView):

    template = ViewPageTemplateFile("templates/import_content.pt")

    # You can specify a default-target container for all items of a type.
    # Example {'News Item': '/imported-newsitems'}
    CONTAINER = {}

    # TODO
    BUGS = {}

    # These fields will be ignored
    # Exmaple: ['relatedItems']
    DROP_FIELDS = []

    # Items with these uid will be ignored
    # Example: ['04d1477583c74552a7fcd81a9085c620']
    DROP_UIDS = []

    # These paths will be ignored
    # Example: ['/Plone/doormat/', '/Plone/import_files/']
    DROP_PATHS = []

    # If set, only these paths will be imported
    # If a path is in both DROP and INCLUDE, DROP has precedence
    # If not set, all paths will be imported
    # Example: ['/Plone/important/', '/Plone/standard/item']
    INCLUDE_PATHS = []

    # Default values for some fields
    # Example: {'which_price': 'normal'}
    DEFAULTS = {}

    def __call__(self, jsonfile=None, return_json=False, limit=None, server_file=None):
        request = self.request
        self.limit = limit
        self.commit = int(request["commit"]) if request.get("commit") else None
        self.import_to_current_folder = request.get("import_to_current_folder", False)

        self.handle_existing_content = int(request.get("handle_existing_content", 0))
        self.handle_existing_content_options = (
            ("0", "Skip: Don't import at all"),
            ("1", "Replace: Delete item and create new"),
            ("2", "Update: Reuse and only overwrite imported data"),
            ("3", "Ignore: Create with a new id"),
        )
        self.import_old_revisions = request.get("import_old_revisions", False)

        if not self.request.form.get("form.submitted", False):
            return self.template()

        # If we open a server file, we should close it at the end.
        close_file = False
        status = "success"
        msg = ""

        if server_file and jsonfile:
            # This is an error.  But when you upload 10 GB AND select a server file,
            # it is a pity when you would have to upload again.
            api.portal.show_message(
                u"json file was uploaded, so the selected server file was ignored.",
                request=self.request,
                type="warn",
            )
            server_file = None
            status = "error"
        if server_file and not jsonfile:
            if server_file in self.server_files:
                for path in self.import_paths:
                    full_path = os.path.join(path, server_file)
                    if os.path.exists(full_path):
                        logger.info("Using server file %s", full_path)
                        # Open the file in binary mode and use it as jsonfile.
                        jsonfile = open(full_path, "rb")
                        close_file = True
                        break
            else:
                msg = "File '{}' not found on server.".format(server_file)
                api.portal.show_message(msg, request=self.request, type="warn")
                server_file = None
                status = "error"
        if jsonfile:
            self.portal = api.portal.get()
            try:
                if isinstance(jsonfile, str):
                    return_json = True
                    data = ijson.items(jsonfile, "item")
                elif isinstance(jsonfile, FileUpload) or hasattr(jsonfile, "read"):
                    data = ijson.items(jsonfile, "item")
                else:
                    raise RuntimeError("Data is neither text, file nor upload.")
            except Exception as e:
                logger.error(str(e))
                status = "error"
                msg = str(e)
                api.portal.show_message(
                    u"Exception during uplad: {}".format(e),
                    request=self.request,
                )
            else:
                self.start()
                msg = self.do_import(data)
                api.portal.show_message(msg, self.request)

        if close_file:
            jsonfile.close()

        self.finish()

        if return_json:
            msg = {"state": status, "msg": msg}
            return json.dumps(msg)
        return self.template()

    def start(self):
        """Hook to do something before importing one file."""

    def finish(self):
        """Hook to do something after importing one file."""

    def commit_hook(self, added, index):
        """Hook to do something after importing every x items."""
        msg = u"Committing after creating {} of {} handled items...".format(
            len(added), index
        )
        logger.info(msg)
        transaction.get().note(msg)
        transaction.commit()

    @property
    def import_paths(self):
        # Adapted from ObjectManager.list_imports, which lists zexps.
        # We list all possible paths (import directory in client home
        # and instance home), without caring whether they exist.
        listing = []
        for impath in self.context._getImportPaths():
            directory = os.path.join(impath, "import")
            listing.append(directory)
        listing.sort()
        if config.CENTRAL_DIRECTORY:
            listing.insert(0, config.CENTRAL_DIRECTORY)
        return listing

    @property
    def server_files(self):
        # Adapted from ObjectManager.list_imports, which lists zexps.
        listing = []
        for directory in self.import_paths:
            if not os.path.isdir(directory):
                continue
            listing += [
                f
                for f in os.listdir(directory)
                if f.endswith(".json") and f not in listing
            ]
        listing.sort()
        return listing

    def do_import(self, data):
        start = datetime.now()
        alsoProvides(self.request, IMigrationMarker)
        added = self.import_new_content(data)
        end = datetime.now()
        delta = end - start
        msg = u"Imported {} items".format(len(added))
        transaction.get().note(msg)
        transaction.commit()
        msg = u"{} in {} seconds".format(msg, delta.seconds)
        logger.info(msg)
        return msg

    def should_drop(self, path):
        for drop in self.DROP_PATHS:
            if drop in path:
                return True
        return False

    def should_include(self, path):
        for include in self.INCLUDE_PATHS:
            if include in path:
                return True
        return False

    def must_process(self, item_path):
        if self.INCLUDE_PATHS:
            if not self.should_include(item_path):
                return False
            elif self.should_drop(item_path):
                logger.info(u"Skipping %s, even though listed in INCLUDE_PATHS", item_path)
                return False
        else:
            if self.should_drop(item_path):
                logger.info("Skipping %s", item_path)
                return False
        return True

    def import_new_content(self, data):  # noqa: C901
        added = []

        if getattr(data, "len", None):
            logger.info(u"Importing {} items".format(len(data)))
        else:
            logger.info(u"Importing data")
        for index, item in enumerate(data, start=1):
            if self.limit and len(added) >= self.limit:
                break

            uuid = item.get("UID")
            if uuid and uuid in self.DROP_UIDS:
                continue

            if not self.must_process(item["@id"]):
                continue

            if not index % 100:
                logger.info("Imported {} items...".format(index))

            new_id = unquote(item["@id"]).split("/")[-1]
            if new_id != item["id"]:
                logger.info(
                    u"Conflicting ids in url ({}) and id ({}). Using {}".format(
                        new_id, item["id"], new_id
                    )
                )
                item["id"] = new_id

            self.safe_portal_type = fix_portal_type(item["@type"])
            item = self.handle_broken(item)
            if not item:
                continue
            item = self.handle_dropped(item)
            if not item:
                continue
            item = self.global_dict_hook(item)
            if not item:
                continue

            # portal_type might change during a hook
            self.safe_portal_type = fix_portal_type(item["@type"])
            item = self.custom_dict_hook(item)
            if not item:
                continue

            self.safe_portal_type = fix_portal_type(item["@type"])
            container = self.handle_container(item)

            if not container:
                logger.warning(
                    u"No container (parent was {}) found for {} {}".format(
                        item["parent"]["@type"], item["@type"], item["@id"]
                    )
                )
                continue

            if not getattr(aq_base(container), "isPrincipiaFolderish", False):
                logger.warning(
                    u"Container {} for {} is not folderish".format(
                        container.absolute_url(), item["@id"]
                    )
                )
                continue

            factory_kwargs = item.get("factory_kwargs", {})

            # Handle existing content
            self.update_existing = False
            if item["id"] in container:
                if self.handle_existing_content == 0:
                    # Skip
                    logger.info(
                        u"{} ({}) already exists. Skipping it.".format(
                            item["id"], item["@id"]
                        )
                    )
                    continue

                elif self.handle_existing_content == 1:
                    # Replace content before creating it new
                    logger.info(
                        u"{} ({}) already exists. Replacing it.".format(
                            item["id"], item["@id"]
                        )
                    )
                    api.content.delete(container[item["id"]], check_linkintegrity=False)

                elif self.handle_existing_content == 2:
                    # Update existing item
                    logger.info(
                        u"{} ({}) already exists. Updating it.".format(
                            item["id"], item["@id"]
                        )
                    )
                    self.update_existing = True
                    new = container[item["id"]]

                else:
                    # Create with new id. Speed up by using random id.
                    duplicate = item["id"]
                    item["id"] = "{}-{}".format(item["id"], random.randint(1000, 9999))
                    logger.info(
                        u"{} ({}) already exists. Created as {}".format(
                            duplicate, item["@id"], item["id"]
                        )
                    )

            if self.import_old_revisions and item.get("exportimport.versions"):
                # TODO: refactor into import_item to prevent duplicattion
                new = self.import_versions(container, item)
                if new:
                    added.append(new.absolute_url())
                if self.commit and not len(added) % self.commit:
                    self.commit_hook(added, index)
                continue

            if not self.update_existing:
                # create without checking constrains and permissions
                new = _createObjectByType(
                    item["@type"], container, item["id"], **factory_kwargs
                )

            new, item = self.global_obj_hook_before_deserializing(new, item)

            # import using plone.restapi deserializers
            deserializer = getMultiAdapter((new, self.request), IDeserializeFromJson)
            try:
                new = deserializer(validate_all=False, data=item)
            except Exception:
                logger.warning("Cannot deserialize %s %s", item["@type"], item["@id"], exc_info=True)
                continue

            # Blobs can be exported as only a path in the blob storage.
            # It seems difficult to dynamically use a different deserializer,
            # based on whether or not there is a blob_path somewhere in the item.
            # So handle this case with a separate method.
            self.import_blob_paths(new, item)
            self.import_constrains(new, item)

            self.global_obj_hook(new, item)
            self.custom_obj_hook(new, item)

            uuid = self.set_uuid(item, new)

            if uuid != item.get("UID"):
                item["UID"] = uuid

            # Try to set the original review_state
            self.import_review_state(new, item)

            # Import workflow_history last to drop entries created during import
            self.import_workflow_history(new, item)

            # Set modification and creation-date as a custom attribute as last step.
            # These are reused and dropped in ResetModifiedAndCreatedDate
            modified = item.get("modified", item.get("modification_date", None))
            if modified:
                modification_date = DateTime(dateutil.parser.parse(modified))
                new.modification_date = modification_date
                new.aq_base.modification_date_migrated = modification_date
            created = item.get("created", item.get("creation_date", None))
            if created:
                creation_date = DateTime(dateutil.parser.parse(created))
                new.creation_date = creation_date
                new.aq_base.creation_date_migrated = creation_date
            logger.info(
                "Created item #{}: {} {}".format(
                    index, item["@type"], new.absolute_url()
                )
            )
            added.append(new.absolute_url())

            if self.commit and not len(added) % self.commit:
                self.commit_hook(added, index)

        return added

    def import_versions(self, container, item):
        """Import one item with all its revisions..
        We only apply hooks for the current object not for each version.
        TODO: refactor into import_item to prevent duplicattion
        """
        portal_workflow = api.portal.get_tool("portal_workflow")

        # Disable automatic versioning!
        portal_types = api.portal.get_tool("portal_types")
        fti = portal_types.get(item["@type"])

        # disable versioning behavior to re-enable it after import
        versioning_behavior = None
        if IDexterityFTI.providedBy(fti):
            fti_behaviors = list(fti.behaviors)
            versioning_behaviors = [
                "plone.versioning",
                "plone.app.versioningbehavior.behaviors.IVersionable",
            ]
            for behavior in versioning_behaviors:
                if behavior in fti_behaviors:
                    versioning_behavior = behavior
                    fti_behaviors.remove(behavior)
                    fti.manage_changeProperties(behaviors=tuple(fti_behaviors))

        # disable default versioning policy to re-enable it after import
        repo_tool = api.portal.get_tool("portal_repository")
        policy = None
        policies = repo_tool._version_policy_mapping.get(item["@type"], [])
        if "at_edit_autoversion" in policies:
            policy = "at_edit_autoversion"
            repo_tool.removePolicyFromContentType(item["@type"], policy)

        for index, version in enumerate(item["exportimport.versions"].values()):
            initial = index == 0
            version = self.global_dict_hook(version)
            if not version:
                continue

            # portal_type might change during a hook
            version = self.custom_dict_hook(version)
            if not version:
                continue

            if initial and not self.update_existing:
                # initial version
                new = _createObjectByType(item["@type"], container, item["id"])
                uuid = self.set_uuid(item, new)
                if uuid != item["UID"]:
                    item["UID"] = uuid
            else:
                new = container.get(item["id"])

            # import using plone.restapi deserializers
            deserializer = getMultiAdapter((new, self.request), IDeserializeFromJson)
            try:
                new = deserializer(validate_all=False, data=version)
            except Exception:
                logger.warning("Cannot deserialize %s %s", item["@type"], item["@id"], exc_info=True)
                return

            self.save_revision(new, version, initial)

        # Finally create the current version
        new = container.get(item["id"])
        deserializer = getMultiAdapter((new, self.request), IDeserializeFromJson)
        try:
            new = deserializer(validate_all=False, data=item)
        except Exception:
            logger.warning("Cannot deserialize %s %s", item["@type"], item["@id"], exc_info=True)
            return

        self.import_blob_paths(new, item)
        self.import_constrains(new, item)
        self.global_obj_hook(new, item)
        self.custom_obj_hook(new, item)

        if item["review_state"] and item["review_state"] != "private":
            if portal_workflow.getChainFor(new):
                try:
                    api.content.transition(to_state=item["review_state"], obj=new)
                except InvalidParameterError as e:
                    logger.info(e)

        # Import workflow_history last to drop entries created during import
        self.import_workflow_history(new, item)

        # Set modification and creation-date as a custom attribute as last step.
        # These are reused and dropped in ResetModifiedAndCreatedDate
        modified = item.get("modified", item.get("modification_date", None))
        if modified:
            modification_date = DateTime(dateutil.parser.parse(modified))
            new.modification_date = modification_date
            new.aq_base.modification_date_migrated = modification_date
        created = item.get("created", item.get("creation_date", None))
        if created:
            creation_date = DateTime(dateutil.parser.parse(created))
            new.creation_date = creation_date
            new.aq_base.creation_date_migrated = creation_date

        self.save_revision(new, item)
        logger.info(
            "Created item: {} {} with {} old versions".format(
                item["@type"], new.absolute_url(), len(item["exportimport.versions"])
            )
        )

        if policy:
            repo_tool.addPolicyForContentType(item["@type"], policy)
        if versioning_behavior:
            fti_behaviors = list(fti.behaviors)
            fti_behaviors.append(versioning_behavior)
            fti.manage_changeProperties(behaviors=tuple(fti_behaviors))
        return new

    def save_revision(self, obj, item, initial=False):
        """Save revision manually to set dates and changenote from exported data."""
        rt = api.portal.get_tool("portal_repository")

        modified = dateutil.parser.parse(item["modified"])
        # add one millisecond to prevent created being before first revision
        modified = modified + timedelta(milliseconds=1)
        if six.PY2:
            import time

            timestamp = time.mktime(modified.timetuple())
        else:
            timestamp = datetime.timestamp(modified)
        from plone.app.versioningbehavior import _ as PAV

        if initial:
            comment = PAV(u"initial_version_changeNote", default=u"Initial version")
        else:
            comment = item.get("changeNote")
        sys_metadata = {
            "comment": comment,
            "timestamp": timestamp,
            "originator": None,
        }
        rt._recursiveSave(
            obj, app_metadata={}, sys_metadata=sys_metadata, autoapply=True
        )

    def handle_broken(self, item):
        """Fix some invalid values."""
        if item["id"] not in self.BUGS:
            return item
        for key, value in self.BUGS[item["id"]].items():
            logger.info(
                "Replaced {} with {} for field {} of {}".format(
                    item[key], value, key, item["id"]
                )
            )
            item[key] = value
        return item

    def handle_dropped(self, item):
        """Drop some fields, especially relations."""
        for key in self.DROP_FIELDS:
            item.pop(key, None)
        return item

    def handle_defaults(self, item):
        """Set missing values especially for required fields."""
        for key in self.DEFAULTS:
            if not item.get(key, None):
                item[key] = self.DEFAULTS[key]
        return item

    def import_blob_paths(self, new, item):
        for key, value in item.items():
            # Look for dictionaries with a blob_path key.
            if not isinstance(value, dict):
                continue
            blob_path = value.get("blob_path")
            if not blob_path:
                continue
            abs_blob_path = get_absolute_blob_path(new, blob_path)
            if not abs_blob_path:
                __traceback_info__ = item
                raise ValueError("Blob path {} does not exist!".format(blob_path))

            # Determine the class to use: file or image.
            filename = value["filename"]
            content_type = value["content-type"]
            if key == "file":
                klass = NamedBlobFile
            elif key == "image":
                klass = NamedBlobImage
            elif content_type.startswith("image"):
                klass = NamedBlobImage
            else:
                klass = NamedBlobFile

            # Write the field.
            with open(abs_blob_path, "rb") as myfile:
                blobdata = myfile.read()
            field_value = klass(
                data=blobdata,
                contentType=content_type,
                filename=filename,
            )
            setattr(new, key, field_value)

    def global_dict_hook(self, item):
        """Overwrite this do general changes on the dict before deserializing.

        Example:
        if not item['language'] and 'Plone/de/' in item['parent']['@id']:
            item['language'] = {'token': 'de', 'title': 'Deutsch'}
        elif not item['language'] and 'Plone/en/' in item['parent']['@id']:
            item['language'] = {'token': 'en', 'title': 'English'}
        elif not item['language'] and 'Plone/fr/' in item['parent']['@id']:
            item['language'] = {'token': 'fr', 'title': 'Français'}

        # drop layout property (we always use the type default view)
        item.pop('layout', None)
        """
        return item

    def custom_dict_hook(self, item):
        """Hook to inject dict-modifiers by type before deserializing.
        E.g.: dict_hook_document(self, item)
        """
        modifier = getattr(self, "dict_hook_{}".format(self.safe_portal_type), None)
        if modifier and callable(modifier):
            item = modifier(item)
        return item

    def import_constrains(self, obj, item):
        if not item.get("exportimport.constrains"):
            return
        constrains = ISelectableConstrainTypes(obj, None)
        if constrains is None:
            return
        constrains.setConstrainTypesMode(ENABLED)

        locally_allowed_types = item["exportimport.constrains"][
            "locally_allowed_types"
        ]
        try:
            constrains.setLocallyAllowedTypes(locally_allowed_types)
        except ValueError:
            logger.warning(
                "Cannot setLocallyAllowedTypes on %s", item["@id"],
                exc_info=True
            )

        immediately_addable_types = item["exportimport.constrains"][
            "immediately_addable_types"
        ]
        try:
            constrains.setImmediatelyAddableTypes(immediately_addable_types)
        except ValueError:
            logger.warning(
                "Cannot setImmediatelyAddableTypes on %s", item["@id"],
                exc_info=True
            )

    def import_review_state(self, obj, item):
        """Try to set the original review_state. Overwrite to customize or skip."""
        if item.get("review_state"):
            portal_workflow = api.portal.get_tool("portal_workflow")
            if portal_workflow.getChainFor(obj):
                try:
                    api.content.transition(to_state=item["review_state"], obj=obj)
                except InvalidParameterError as e:
                    logger.info(e)

    def import_workflow_history(self, obj, item):
        workflow_history = item.get("workflow_history", {})
        result = {}
        for key, value in workflow_history.items():
            # The time needs to be deserialized
            for history_item in value:
                history_item["time"] = DateTime(
                    dateutil.parser.parse(history_item["time"])
                )
            result[key] = value
        if result:
            obj.workflow_history = PersistentMapping(result.items())

    def global_obj_hook_before_deserializing(self, obj, item):
        """Hook to modify the created obj before deserializing the data.
        Example that applies marker-interfaces:

        for iface_name in item.pop("marker_interfaces", []):
            iface = resolveDottedName(iface_name)
            if not iface.providedBy(obj):
                alsoProvides(obj, iface)
        return obj, item
        """
        return obj, item

    def global_obj_hook(self, obj, item):
        """Override hook to modify each imported content after deserializing."""
        return obj

    def custom_obj_hook(self, obj, item):
        """Hook to inject modifiers of the imported item by type.
        E.g.: obj_hook_newsitem(self, obj, item)
        """
        modifier = getattr(self, "obj_hook_{}".format(self.safe_portal_type), None)
        if modifier and callable(modifier):
            modifier(obj, item)

    def handle_container(self, item):
        """Specify a container per item and type using custom methods
        Example for content_type Document:

        def handle_document_container(self, item):
            lang = item['language']['token'] if item.get('language') else ''
            if lang:
                base_path = self.CONTAINER["Document"][lang]
                folder = api.content.get(path=base_path)
                if folder:
                    return folder
                else:
                    raise RuntimeError(f'Target folder {base_path} is missing')

        Example for Images:

        def handle_image_container(self, item):
            if '/de/extranet/' in item['@id']:
                return self.portal['extranet']['de']['images']
            if '/en/extranet/' in item['@id']:
                return self.portal['extranet']['en']['images']
            if '/de/' in item['@id']:
                return self.portal['de']['images']
            if '/en/' in item['@id']:
                return self.portal['en']['images']

            return self.portal['images']
        """
        if self.import_to_current_folder:
            return self.context

        # Use dict-based config in self.CONTAINER if it exists
        container_path = self.CONTAINER.get(item["@type"], None)
        if container_path:
            container = api.content.get(path=container_path)
            if not container:
                raise RuntimeError(
                    u"Target folder {} for type {} is missing".format(
                        container_path, item["@type"]
                    )
                )

        # Run custom container hooks if they exist
        method = getattr(
            self, "handle_{}_container".format(self.safe_portal_type), None
        )
        if method and callable(method):
            return method(item)

        # Default is to use the original containers is they exist
        return self.get_parent_as_container(item)

    def get_parent_as_container(self, item):
        """The default is to generate a folder-structure exactly as the original.
        By default we use the UID of the parent to find it in the new site.

        During fallback to a path-based lookup there is some trickyness that probably
        only happens during local development, and not in production sites.
        Situation:

        - localhost:8080/nl is a Dutch Plone Site
        - localhost:8080/de is a German Plone Site in the same ZODB
        - localhost:9999/fr is a French Plone Site a different ZODB

        We export nl/folder/page.
        The parent url (parent/@id) is http://localhost:8080/nl/folder
        Parent path is then: ["", "nl", "folder].

        1. We import it in the NL site.
           We should recognize this, and not try to create
           /nl/random-id/nl
           which would fail with BadRequest at the reserved id 'nl'.
           Note: the 'random-id' would be because of the empty string
           at the start of the parent path.
           Expected result: nl/folder/page-1234

        2. We import it in the DE site.
           This should *not* traverse to the NL site and create the content there.
           I have seen this happen.
           It should also *not* create a de/nl folder: an unwanted extra level.
           Expected result: de/folder/page

        3. We import it in the FR site.
           It should *not* create a fr/nl folder: an unwanted extra level.
           Expected result: fr/folder/page

        """
        # The default is to use the UUID of the old parent to find it
        if item["parent"].get("UID"):
            # For some reason api.content.get(UID=xxx) does not work sometimes...
            brains = api.content.find(UID=item["parent"]["UID"])
            if brains:
                return brains[0].getObject()

        if item["parent"]["@type"] == "Plone Site":
            return api.portal.get()

        # If the item is missing look for a item with the path of the old parent
        parent_url = unquote(item["parent"]["@id"])
        parent_path = urlparse(parent_url).path
        # physical path is bytes in Zope 2 (not in Zope 4)
        # so we need to encode parent_path before using plone.api.content.get
        if isinstance(self.context.getPhysicalPath()[0], bytes):
            parent_path = parent_path.encode("utf8")
        try:
            parent = api.content.get(path=parent_path)
        except NotFound:
            parent = None
        if parent and hasattr(parent, "getPhysicalPath"):
            # Check that we did not traverse to content outside of the portal.
            # Actually, we probably should not go outside the navigation root either,
            # especially with multilingual, although most likely
            # the context is the site root.
            found_path = "/".join(parent.getPhysicalPath())
            nav_path = "/".join(
                api.portal.get_navigation_root(self.context).getPhysicalPath()
            )
            if found_path.startswith(nav_path):
                return parent
            logger.info(
                "Ignoring existing container outside of navigation root: %s", found_path
            )
        # As a final fallback we create the folder-structure required by the path
        return self.create_container(item)

    def create_container(self, item):
        """Create container for item.

        See remarks in get_parent_as_container for some corner cases.
        """
        folder = self.context
        parent_url = unquote(item["parent"]["@id"])
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

        # create original structure for imported content
        for element in parent_path:
            if element not in folder:
                folder = api.content.create(
                    container=folder,
                    type="Folder",
                    id=element,
                    title=element,
                )
                logger.info(
                    u"Created container {} to hold {}".format(
                        folder.absolute_url(), item["@id"]
                    )
                )
            else:
                folder = folder[element]

        return folder

    def set_uuid(self, item, obj):
        uuid = item.get("UID")
        if not uuid:
            return obj.UID()
        if not self.update_existing and api.content.find(UID=uuid):
            # this should only happen if you run import multiple times
            # without updating existing content
            uuid = obj.UID()
            logger.info(
                "UID {} of {} already in use by {}. Using {}".format(
                    item["UID"],
                    item["@id"],
                    api.content.get(UID=item["UID"]).absolute_url(),
                    uuid,
                ),
            )
        else:
            setattr(obj, "_plone.uuid", uuid)
            obj.reindexObject(idxs=["UID"])
        return uuid


def fix_portal_type(portal_type):
    normalizer = getUtility(IIDNormalizer)
    return normalizer.normalize(portal_type).replace("-", "")


class ResetModifiedAndCreatedDate(BrowserView):
    def __call__(self):
        self.title = "Reset creation and modification date"
        self.help_text = """<p>Creation- and modification-dates are changed during import.
        This resets them to the original dates of the imported content.</p>"""
        if not self.request.form.get("form.submitted", False):
            return self.index()

        portal = api.portal.get()

        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=reset_dates)
        msg = "Finished resetting creation and modification dates."
        logger.info(msg)
        api.portal.show_message(msg, self.request)
        return self.index()


def reset_dates(obj, path):
    modified = getattr(obj.aq_base, "modification_date_migrated", None)
    if modified and modified != obj.modification_date:
        obj.modification_date = modified
        del obj.modification_date_migrated
        obj.reindexObject(idxs=["modified"])

    created = getattr(obj.aq_base, "creation_date_migrated", None)
    if created and created != obj.creation_date:
        obj.creation_date = created
        del obj.creation_date_migrated
        obj.reindexObject(idxs=["created"])


class FixCollectionQueries(BrowserView):
    def __call__(self):
        self.title = "Fix collection queries"
        self.help_text = """<p>This fixes invalid collection-criteria that were imported from Plone 4 or 5.</p>"""

        if not HAS_COLLECTION_FIX:
            api.portal.show_message(
                "plone.app.querystring.upgrades.fix_select_all_existing_collections is not available",
                self.request,
            )
            return self.index()

        if not self.request.form.get("form.submitted", False):
            return self.index()

        portal = api.portal.get()
        fix_select_all_existing_collections(portal)
        msg = "Finished fixing collection queries."
        api.portal.show_message(msg, self.request)
        return self.index()
