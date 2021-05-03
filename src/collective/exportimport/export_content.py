# -*- coding: utf-8 -*-
from App.config import getConfiguration
from collective.exportimport.interfaces import IBase64BlobsMarker
from collective.exportimport.interfaces import IRawRichTextMarker
from operator import itemgetter
from plone import api
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import iterSchemata
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.restapi.interfaces import IJsonCompatible
from plone.restapi.interfaces import ISerializeToJson
from Products.CMFDynamicViewFTI.interfaces import IDynamicViewTypeInformation
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.relationfield.interfaces import IRelationChoice
from z3c.relationfield.interfaces import IRelationList
from z3c.relationfield.interfaces import IRelationValue
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.i18n import translate
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.interface import Interface
from zope.interface import noLongerProvides
from zope.schema import getFields

import json
import logging
import os
import pkg_resources
import six

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

logger = logging.getLogger(__name__)


class ExportContent(BrowserView):

    template = ViewPageTemplateFile("templates/export_content.pt")

    QUERY = {}

    DROP_UIDS = []

    DROP_PATHS = []

    def __call__(self, portal_type=None, include_blobs=False, download_to_server=False, migration=True):
        self.portal_type = portal_type
        self.migration = migration

        self.fixup_request()

        if not self.request.form.get("form.submitted", False):
            return self.template()

        if not self.portal_type:
            return self.template()

        data = self.export_content(include_blobs=include_blobs)
        number = len(data)
        filename = '{}.json'.format(self.portal_type)
        data = json.dumps(data, sort_keys=True, indent=4)

        if download_to_server:
            cfg = getConfiguration()
            filepath = os.path.join(cfg.clienthome, filename)
            with open(filepath, 'w') as f:
                f.write(data)
            msg = u"Exported {} {} as {} to {}".format(number, self.portal_type, filename, filepath)
            logger.info(msg)
            api.portal.show_message(msg, self.request)
            self.request.response.redirect(self.request['ACTUAL_URL'])
        else:
            msg = u"Exported {} {}".format(number, self.portal_type)
            logger.info(msg)
            api.portal.show_message(msg, self.request)
            response = self.request.response
            response.setHeader("content-type", "application/json")
            response.setHeader("content-length", len(data))
            response.setHeader(
                "content-disposition",
                'attachment; filename="{0}"'.format(filename),
            )
            return response.write(safe_bytes(data))

    def build_query(self):
        query = {"portal_type": self.portal_type, "sort_on": "path"}
        # custom setting per type
        query.update(self.QUERY.get(self.portal_type, {}))
        query = self.update_query(query)
        return query

    def update_query(self, query):
        """Overwrite this if you want more control over which content to export."""
        return query

    def export_content(self, include_blobs=False):
        data = []
        query = self.build_query()
        brains = api.content.find(**query)
        logger.info(u"Exporting {} {}".format(len(brains), self.portal_type))
        self.safe_portal_type = fix_portal_type(self.portal_type)

        if include_blobs:
            # Add marker-interface to request to use our custom serializers
            alsoProvides(self.request, IBase64BlobsMarker)

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
                serializer = getMultiAdapter((obj, self.request), ISerializeToJson)
                item = serializer(include_items=False)
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

                data.append(item)
            except Exception as e:
                logger.info(e)

        if include_blobs:
            # remove marker interface
            noLongerProvides(self.request, IBase64BlobsMarker)

        return data

    def portal_types(self):
        """A list with info on all content types with existing items."""
        catalog = api.portal.get_tool("portal_catalog")
        portal_types = api.portal.get_tool("portal_types")
        results = []
        query = self.build_query()
        for fti in portal_types.listTypeInfo():
            if not IDexterityFTI.providedBy(
                fti
            ) and not IDynamicViewTypeInformation.providedBy(fti):
                # Ignore non-DX and non-AT types
                continue
            query["portal_type"] = fti.id
            number = len(catalog(**query))
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

    def fixup_request(self):
        """Use this to override stuff (e.g. force a specific language in request)."""
        return

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
        """
        # 1. Drop unused data
        item.pop('@components', None)
        item.pop('next_item', None)
        item.pop('previous_item', None)
        item.pop('immediatelyAddableTypes', None)
        item.pop('locallyAllowedTypes', None)

        # 2. Remove all relationfields
        if HAS_AT and IBaseObject.providedBy(obj):
            for field in obj.schema.fields():
                if isinstance(field, ReferenceField):
                    item.pop(field.__name__, None)
        if HAS_DX and IDexterityContent.providedBy(obj):
            for schema in iterSchemata(obj):
                for name, field in getFields(schema).items():
                    if IRelationChoice.providedBy(field) or
                            IRelationList.providedBy(field):
                        item.pop(name, None)

        # 3. Change default-fieldnames (AT to DX)
        if item.get("subject"):
            item["subjects"] = item["subject"]
            item.pop("subject")
        if item.get("excludeFromNav", None) is not None:
            item["exclude_from_nav"] = item["excludeFromNav"]
            item.pop("excludeFromNav")
        if item.get("expirationDate"):
            item["expires"] = item["expirationDate"]
            item.pop("expirationDate")
        if item.get("effectiveDate"):
            item["effective"] = item["effectiveDate"]
            item.pop("effectiveDate")
        if item.get("creation_date"):
            item["created"] = item["creation_date"]
            item.pop("creation_date")
        if item.get("modification_date"):
            item["modified"] = item["modification_date"]
            item.pop("modification_date")

        # 4. Fix issue with AT Text fields
        # This is done in the ATTextFieldSerializer

        # 5. Fix collection-criteria
        # TODO

        # 6. Fix image links and scales
        # TODO

        return item

def fix_portal_type(portal_type):
    normalizer = getUtility(IIDNormalizer)
    return normalizer.normalize(portal_type).replace("-", "")


@adapter(IRelationValue)
@implementer(IJsonCompatible)
def relationvalue_converter_uuid(value):
    """Save uuid instead of summary"""
    if value.to_object:
        return value.to_object.UID()


def safe_bytes(value, encoding="utf-8"):
    """Convert text to bytes of the specified encoding."""
    if isinstance(value, six.text_type):
        value = value.encode(encoding)
    return value
