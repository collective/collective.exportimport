# -*- coding: utf-8 -*-
from Acquisition import aq_base
from App.config import getConfiguration
from collective.exportimport import config
from collective.exportimport.interfaces import IBase64BlobsMarker
from collective.exportimport.interfaces import IMigrationMarker
from collective.exportimport.interfaces import IPathBlobsMarker
from collective.exportimport.interfaces import IRawRichTextMarker
from operator import itemgetter
from plone import api
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.restapi.interfaces import ISerializeToJson
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes
from Products.CMFPlone.interfaces.constrains import ENABLED
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.i18n import translate
from zope.interface import alsoProvides
from zope.interface import noLongerProvides
from zope.schema import getFields

import json
import logging
import os
import pkg_resources
import six
import tempfile

try:
    pkg_resources.get_distribution("Products.Archetypes")
except pkg_resources.DistributionNotFound:
    ReferenceField = None
    IBaseObject = None
    HAS_AT = False
else:
    from Products.Archetypes.atapi import ReferenceField
    from Products.Archetypes.interfaces import IBaseObject

    HAS_AT = True

try:
    pkg_resources.get_distribution("plone.dexterity")
except pkg_resources.DistributionNotFound:
    IDexterityContent = None
    iterSchemata = None
    HAS_DX = False
else:
    from plone.dexterity.interfaces import IDexterityContent
    from plone.dexterity.utils import iterSchemata

    HAS_DX = True

try:
    pkg_resources.get_distribution("z3c.relationfield")
except pkg_resources.DistributionNotFound:
    IRelationChoice = None
    IRelationList = None
    HAS_RELATIONS = False
else:
    from z3c.relationfield.interfaces import IRelationChoice
    from z3c.relationfield.interfaces import IRelationList

    HAS_RELATIONS = True


logger = logging.getLogger(__name__)

_marker = object()

# copied from plone.app.contenttypes inplace migration
LISTING_VIEW_MAPPING = {  # OLD (AT and old DX) : NEW
    "all_content": "full_view",
    "atct_album_view": "album_view",
    "atct_topic_view": "listing_view",
    "collection_view": "listing_view",
    "folder_album_view": "album_view",
    "folder_full_view": "full_view",
    "folder_listing": "listing_view",
    "folder_listing_view": "listing_view",
    "folder_summary_view": "summary_view",
    "folder_tabular_view": "tabular_view",
    "standard_view": "listing_view",
    "thumbnail_view": "album_view",
    "view": "listing_view",
}


class ExportContent(BrowserView):

    template = ViewPageTemplateFile("templates/export_content.pt")

    QUERY = {}

    DROP_UIDS = []

    DROP_PATHS = []

    def __call__(
        self,
        portal_type=None,
        path=None,
        depth=-1,
        include_blobs=1,
        download_to_server=False,
        migration=True,
    ):
        self.portal_type = portal_type or []
        if isinstance(self.portal_type, str):
            self.portal_type = [self.portal_type]
        self.migration = migration
        self.path = path or "/".join(self.context.getPhysicalPath())

        self.depth = int(depth)
        self.depth_options = (
            ("-1", "unlimited"),
            ("0", "0"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
            ("8", "8"),
            ("9", "9"),
            ("10", "10"),
        )
        self.include_blobs = int(include_blobs)
        self.include_blobs_options = (
            ("0", "as download urls"),
            ("1", "as base-64 encoded strings"),
            ("2", "as blob paths"),
        )

        self.update()

        if not self.request.form.get("form.submitted", False):
            return self.template()

        if not self.portal_type:
            api.portal.show_message(u"Select at least one type to export", self.request)
            return self.template()

        if self.include_blobs == 1:
            # Add marker-interface to request to use our custom serializers
            alsoProvides(self.request, IBase64BlobsMarker)
        elif self.include_blobs == 2:
            # Add marker interface to export blob paths
            alsoProvides(self.request, IPathBlobsMarker)
        else:
            # Use the default plone.restapi serializer,
            # which gives a download url.
            pass

        if self.migration:
            # Add marker-interface to request to use custom serializers
            alsoProvides(self.request, IMigrationMarker)

        # to get a useful filename...
        if self.portal_type and len(self.portal_type) == 1:
            filename = self.portal_type[0]
        else:
            filename = self.path.split("/")[-1]
        filename = "{}.json".format(filename)

        content_generator = self.export_content()

        number = 0
        if download_to_server:
            directory = config.CENTRAL_DIRECTORY
            if directory:
                if not os.path.exists(directory):
                    os.makedirs(directory)
                    logger.info("Created central export/import directory %s", directory)
            else:
                cfg = getConfiguration()
                directory = cfg.clienthome
            filepath = os.path.join(directory, filename)
            with open(filepath, "w") as f:
                for number, datum in enumerate(content_generator, start=1):
                    if number == 1:
                        f.write("[")
                    else:
                        f.write(",")
                    json.dump(datum, f, sort_keys=True, indent=4)
                if number:
                    f.write("]")
            msg = u"Exported {} items ({}) as {} to {}".format(
                number, ", ".join(self.portal_type), filename, filepath
            )
            logger.info(msg)
            api.portal.show_message(msg, self.request)

            if self.include_blobs == 1:
                # remove marker interface
                noLongerProvides(self.request, IBase64BlobsMarker)
            elif self.include_blobs == 2:
                noLongerProvides(self.request, IPathBlobsMarker)
            self.request.response.redirect(self.request["ACTUAL_URL"])
        else:
            with tempfile.TemporaryFile(mode="w+") as f:
                for number, datum in enumerate(content_generator, start=1):
                    if number == 1:
                        f.write("[")
                    else:
                        f.write(",")
                    json.dump(datum, f, sort_keys=True, indent=4)
                if number:
                    f.write("]")
                msg = u"Exported {} {}".format(number, self.portal_type)
                logger.info(msg)
                api.portal.show_message(msg, self.request)
                response = self.request.response
                response.setHeader("content-type", "application/json")
                response.setHeader("content-length", f.tell())
                response.setHeader(
                    "content-disposition",
                    'attachment; filename="{0}"'.format(filename),
                )
                if self.include_blobs == 1:
                    # remove marker interface
                    noLongerProvides(self.request, IBase64BlobsMarker)
                elif self.include_blobs == 2:
                    noLongerProvides(self.request, IPathBlobsMarker)
                f.seek(0)
                return response.write(safe_bytes(f.read()))

    def update(self):
        """Hook to do something before export."""

    def build_query(self):
        query = {
            "portal_type": self.portal_type,
            "sort_on": "path",
            "path": {"query": self.path, "depth": self.depth},
        }
        # custom setting per type
        for portal_type in self.portal_type:
            query.update(self.QUERY.get(portal_type, {}))
        query = self.update_query(query)
        return query

    def update_query(self, query):
        """Overwrite this if you want more control over which content to export."""
        return query

    def export_content(self):
        query = self.build_query()
        catalog = api.portal.get_tool("portal_catalog")
        brains = catalog.unrestrictedSearchResults(**query)
        logger.info(u"Exporting {} {}".format(len(brains), self.portal_type))

        # Override richtext serializer to export links using resolveuid/xxx
        alsoProvides(self.request, IRawRichTextMarker)

        for index, brain in enumerate(brains, start=1):
            skip = False
            if brain.UID in self.DROP_UIDS:
                continue

            for drop in self.DROP_PATHS:
                if drop in brain.getPath():
                    skip = True

            if skip:
                continue

            if not index % 100:
                logger.info(u"Handled {} items...".format(index))
            obj = brain.getObject()
            obj = self.global_obj_hook(obj)
            if not obj:
                continue
            try:
                self.safe_portal_type = fix_portal_type(obj.portal_type)
                serializer = getMultiAdapter((obj, self.request), ISerializeToJson)
                if getattr(aq_base(obj), "isPrincipiaFolderish", False):
                    item = serializer(include_items=False)
                else:
                    item = serializer()
                item = self.fix_url(item, obj)
                item = self.export_constraints(item, obj)
                if self.migration:
                    item = self.update_data_for_migration(item, obj)
                item = self.global_dict_hook(item, obj)
                if not item:
                    logger.info(u"Skipping {}".format(brain.getURL()))
                    continue

                item = self.custom_dict_hook(item, obj)
                if not item:
                    logger.info(u"Skipping {}".format(brain.getURL()))
                    continue

                yield item
            except Exception as e:
                logger.info(u"Error exporting {}: {}".format(obj.absolute_url(), e))

    def portal_types(self):
        """A list with info on all content types with existing items."""
        catalog = api.portal.get_tool("portal_catalog")
        portal_types = api.portal.get_tool("portal_types")
        results = []
        query = self.build_query()
        for fti in portal_types.listTypeInfo():
            query["portal_type"] = fti.id
            number = len(catalog.unrestrictedSearchResults(**query))
            if number >= 1:
                results.append(
                    {
                        "number": number,
                        "value": fti.id,
                        "title": translate(
                            fti.title, domain="plone", context=self.request
                        ),
                    }
                )
        return sorted(results, key=itemgetter("title"))

    def global_obj_hook(self, obj):
        """Inspect the content item before serialisation data.
        Bad: Changing the content-item is a horrible idea.
        Good: Return None if you want to skip this particular object.
        """
        return obj

    def global_dict_hook(self, item, obj):
        """Use this to modify or skip the serialized data.
        Return None if you want to skip this particular object.
        """
        return item

    def custom_dict_hook(self, item, obj):
        """Add you own method e.g. def dict_hook_document(self, item, obj)
        Use this to modify or skip the serialized data by type.
        Return a dict or None if you want to skip this particular object.
        """
        hook = getattr(self, "dict_hook_{}".format(self.safe_portal_type), None)
        if hook and callable(hook):
            item = hook(item, obj)
        return item

    def update_data_for_migration(self, item, obj):
        """Update serialized data to optimze use for migrations.

        1. Drop unused data
        2. Remove all relationfields (done with the serializer relationvalue_converter)
        3. Change some default-fieldnames (AT to DX)
        4. Fix issue with AT Text fields
        5. Fix collection-criteria
        6. Fix image links and scales
        7. Fix view names on Folder, Collection, Topic CT's

        """
        # 1. Drop unused data
        item.pop("@components", None)
        item.pop("next_item", None)
        item.pop("previous_item", None)
        item.pop("immediatelyAddableTypes", None)
        item.pop("locallyAllowedTypes", None)

        # 2. Remove all relationfields
        if HAS_AT and IBaseObject.providedBy(obj):
            for field in obj.schema.fields():
                if isinstance(field, ReferenceField):
                    item.pop(field.__name__, None)
        elif HAS_DX and HAS_RELATIONS and IDexterityContent.providedBy(obj):
            for schema in iterSchemata(obj):
                for name, field in getFields(schema).items():
                    if IRelationChoice.providedBy(field) or IRelationList.providedBy(
                        field
                    ):
                        item.pop(name, None)

        # 3. Change default-fieldnames (AT to DX)
        item = migrate_field(item, "excludeFromNav", "exclude_from_nav")
        item = migrate_field(item, "allowDiscussion", "allow_discussion")
        item = migrate_field(item, "subject", "subjects")

        # Some Date fields
        item = migrate_field(item, "expirationDate", "expires")
        item = migrate_field(item, "effectiveDate", "effective")
        item = migrate_field(item, "creation_date", "created")
        item = migrate_field(item, "modification_date", "modified")

        # Event fields
        item = migrate_field(item, "startDate", "start")
        item = migrate_field(item, "endDate", "end")
        item = migrate_field(item, "openEnd", "open_end")
        item = migrate_field(item, "eventUrl", "event_url")
        # url cannot be a empty string
        if item.get("event_url", None) == "":
            item["event_url"] = None
        item = migrate_field(item, "wholeDay", "whole_day")
        item = migrate_field(item, "contactEmail", "contact_email")
        item = migrate_field(item, "contactName", "contact_name")
        item = migrate_field(item, "contactPhone", "contact_phone")

        # 4. Fix issue with AT Text fields
        # This is done in the ATTextFieldSerializer

        # 5. Fix collection-criteria
        # TODO

        # 6. Fix image links and scales
        # TODO

        # 7. Fix view names on Folders and Collection
        if self.safe_portal_type in ("collection", "topic", "folder"):
            old_layout = item.get("layout", "does_not_exist")
            if old_layout in LISTING_VIEW_MAPPING:
                item["layout"] = LISTING_VIEW_MAPPING[old_layout]

        return item

    def fix_url(self, item, obj):
        """Fix the id. Mostly relevant for collections, where the id is set to “@@export-content”
        because of the HypermediaBatch in plone.restapi
        """
        obj_url = obj.absolute_url()
        parent_url = obj.__parent__.absolute_url()
        if item["@id"] != obj_url:
            item["@id"] = obj_url
        if item["parent"]["@id"] != parent_url:
            item["parent"]["@id"] = parent_url
        return item

    def export_constraints(self, item, obj):
        constrains = ISelectableConstrainTypes(obj, None)
        if constrains is None:
            return item
        if constrains.getConstrainTypesMode() == ENABLED:
            key = "exportimport.constrains"
            item[key] = {
                "locally_allowed_types": constrains.getLocallyAllowedTypes(),
                "immediately_addable_types": constrains.getImmediatelyAddableTypes(),
            }
        return item


def fix_portal_type(portal_type):
    normalizer = getUtility(IIDNormalizer)
    return normalizer.normalize(portal_type).replace("-", "")


def migrate_field(item, old, new):
    if item.get(old, _marker) is not _marker:
        item[new] = item.pop(old)
    return item


def safe_bytes(value, encoding="utf-8"):
    """Convert text to bytes of the specified encoding."""
    if isinstance(value, six.text_type):
        value = value.encode(encoding)
    return value
