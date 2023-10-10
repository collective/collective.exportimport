# -*- coding: utf-8 -*-
from collective.exportimport.interfaces import (
    IBase64BlobsMarker,
    IMigrationMarker,
    IPathBlobsMarker,
    IRawRichTextMarker,
    ITalesField,
)
from hurry.filesize import size
from plone.app.textfield.interfaces import IRichText
from plone.dexterity.interfaces import IDexterityContent
from plone.namedfile.interfaces import INamedFileField, INamedImageField
from plone.restapi.interfaces import IFieldSerializer, IJsonCompatible
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.serializer.dxfields import DefaultFieldSerializer
from Products.CMFCore.utils import getToolByName
from zope.component import adapter, getUtility
from zope.interface import implementer, Interface
from zope.schema.interfaces import IChoice, ICollection, IField, IVocabularyTokenized

import base64
import logging
import pkg_resources
import six


try:
    pkg_resources.get_distribution("Products.Archetypes")
except pkg_resources.DistributionNotFound:
    HAS_AT = False
else:
    HAS_AT = True


try:
    pkg_resources.get_distribution("Products.TALESField")
except pkg_resources.DistributionNotFound:
    HAS_TALES = False
else:
    HAS_TALES = True


try:
    pkg_resources.get_distribution("plone.app.blob")
except pkg_resources.DistributionNotFound:
    HAS_BLOB = False
else:
    HAS_BLOB = True

try:
    pkg_resources.get_distribution("plone.app.contenttypes")
except pkg_resources.DistributionNotFound:
    HAS_PAC = False
else:
    HAS_PAC = True


FILE_SIZE_WARNING = 10000000
IMAGE_SIZE_WARNING = 5000000

logger = logging.getLogger(__name__)


def get_blob_path(blob):
    """Get the path of a ZODB.blob.Blob instance"""
    connection = blob._p_jar
    connection.setstate(blob)
    db = connection.db()
    return db.storage.fshelper.layout.getBlobFilePath(blob._p_oid, blob._p_serial)


# Custom Serializers for Dexterity


@adapter(INamedImageField, IDexterityContent, IBase64BlobsMarker)
class ImageFieldSerializerWithBlobs(DefaultFieldSerializer):
    def __call__(self):
        try:
            image = self.field.get(self.context)
        except AttributeError:
            image = None
        if not image:
            return None

        if "built-in function id" in image.filename:
            filename = self.context.id
        else:
            filename = image.filename

        result = {
            "filename": filename,
            "content-type": image.contentType,
            "data": base64.b64encode(image.data),
            "encoding": "base64",
        }
        return json_compatible(result)


@adapter(INamedFileField, IDexterityContent, IBase64BlobsMarker)
class FileFieldSerializerWithBlobs(DefaultFieldSerializer):
    def __call__(self):
        try:
            namedfile = self.field.get(self.context)
        except AttributeError:
            namedfile = None
        if namedfile is None:
            return None

        if "built-in function id" in namedfile.filename:
            filename = self.context.id
        else:
            filename = namedfile.filename

        result = {
            "filename": filename,
            "content-type": namedfile.contentType,
            "data": base64.b64encode(namedfile.data),
            "encoding": "base64",
        }
        return json_compatible(result)


@adapter(IRichText, IDexterityContent, IRawRichTextMarker)
class RichttextFieldSerializerWithRawText(DefaultFieldSerializer):
    def __call__(self):
        value = self.get_value()
        if value:
            output = value.raw
            return {
                "data": json_compatible(output),
                "content-type": json_compatible(value.mimeType),
                "encoding": json_compatible(value.encoding),
            }


@adapter(ICollection, IDexterityContent, IMigrationMarker)
@implementer(IFieldSerializer)
class CollectionFieldSerializer(DefaultFieldSerializer):
    def __call__(self):
        """Override default serializer:
        1. Export only the value, not a token/title dict.
        2. Do not drop values that are not in the vocabulary.
           Instead log info so you can handle the data.
        """
        # Binding is necessary for named vocabularies
        if IField.providedBy(self.field):
            self.field = self.field.bind(self.context)
        value = self.get_value()
        value_type = self.field.value_type
        if (
            value is not None
            and IChoice.providedBy(value_type)
            and IVocabularyTokenized.providedBy(value_type.vocabulary)
        ):
            for v in value:
                try:
                    value_type.vocabulary.getTerm(v)
                except LookupError:
                    # TODO: handle defaultFactory?
                    if v not in [self.field.default, self.field.missing_value]:
                        logger.info(
                            "Term lookup error: %r not in vocabulary %r for field %r of %r",
                            v,
                            value_type.vocabularyName,
                            self.field.__name__,
                            self.context,
                        )
        return json_compatible(value)


@adapter(IChoice, IDexterityContent, IMigrationMarker)
@implementer(IFieldSerializer)
class ChoiceFieldSerializer(DefaultFieldSerializer):
    def __call__(self):
        """Override default serializer:
        1. Export only the value, not a token/title dict.
        2. Do not drop values that are not in the vocabulary.
           Instead log info so you can handle the data.
        """
        # Binding is necessary for named vocabularies
        if IField.providedBy(self.field):
            self.field = self.field.bind(self.context)
        value = self.get_value()
        if value is not None and IVocabularyTokenized.providedBy(self.field.vocabulary):
            try:
                self.field.vocabulary.getTerm(value)
            except LookupError:
                # TODO: handle defaultFactory?
                if value not in [self.field.default, self.field.missing_value]:
                    logger.info(
                        "Term lookup error: %r not in vocabulary %r for field %r of %r",
                        value,
                        self.field.vocabularyName,
                        self.field.__name__,
                        self.context,
                    )
        return json_compatible(value)


# Custom Serializers for Archetypes


if HAS_AT:
    from OFS.Image import Pdata
    from plone.app.blob.interfaces import IBlobField, IBlobImageField
    from plone.restapi.serializer.atfields import (
        DefaultFieldSerializer as ATDefaultFieldSerializer,
    )
    from Products.Archetypes.atapi import RichWidget
    from Products.Archetypes.interfaces import IBaseObject
    from Products.Archetypes.interfaces.field import IFileField, IImageField, ITextField

    if HAS_TALES:
        from Products.TALESField._field import TALESString
        from zope.interface import classImplements

        # Products.TalesField does not implements any interface
        # we mark the field class to let queryMultiAdapter intercept
        # this in place of the default one that would returns
        # the evaluated expression instead of the raw expression itself
        classImplements(TALESString, ITalesField)

        @adapter(ITalesField, IBaseObject, Interface)
        @implementer(IFieldSerializer)
        class ATTalesFieldSerializer(ATDefaultFieldSerializer):
            def __call__(self):
                return json_compatible(self.field.getRaw(self.context))

    @adapter(IImageField, IBaseObject, IBase64BlobsMarker)
    @implementer(IFieldSerializer)
    class ATImageFieldSerializer(ATDefaultFieldSerializer):
        def __call__(self):
            image = self.field.get(self.context)
            if not image:
                return None
            data = image.data.data if isinstance(image.data, Pdata) else image.data
            if len(data) > IMAGE_SIZE_WARNING:
                logger.info(
                    "Large image for {}: {}".format(
                        self.context.absolute_url(), size(len(data))
                    )
                )
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": image.getContentType(),
                "data": base64.b64encode(data),
                "encoding": "base64",
            }
            return json_compatible(result)

    @adapter(IImageField, IBaseObject, IPathBlobsMarker)
    @implementer(IFieldSerializer)
    class ATImageFieldSerializerForBlobPaths(ATImageFieldSerializer):
        pass

    @adapter(IFileField, IBaseObject, IBase64BlobsMarker)
    @implementer(IFieldSerializer)
    class ATFileFieldSerializer(ATDefaultFieldSerializer):
        def __call__(self):
            file_obj = self.field.get(self.context)
            if not file_obj:
                return None
            data = (
                file_obj.data.data
                if isinstance(file_obj.data, Pdata)
                else file_obj.data
            )
            if len(data) > FILE_SIZE_WARNING:
                logger.info(
                    "Large file for {}: {}".format(
                        self.context.absolute_url(), size(len(data))
                    )
                )

            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "data": base64.b64encode(data),
                "encoding": "base64",
            }
            return json_compatible(result)

    @adapter(IBlobImageField, IBaseObject, IBase64BlobsMarker)
    @implementer(IFieldSerializer)
    class ATImageFieldSerializerWithBlobs(ATDefaultFieldSerializer):
        def __call__(self):
            image = self.field.get(self.context)
            if not image:
                return None
            data = image.data.data if isinstance(image.data, Pdata) else image.data
            if len(data) > IMAGE_SIZE_WARNING:
                logger.info(
                    "Large image for {}: {}".format(
                        self.context.absolute_url(), size(len(data))
                    )
                )
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": image.getContentType(),
                "data": base64.b64encode(data),
                "encoding": "base64",
            }
            return json_compatible(result)

    @adapter(IBlobField, IBaseObject, IBase64BlobsMarker)
    @implementer(IFieldSerializer)
    class ATFileFieldSerializerWithBlobs(ATDefaultFieldSerializer):
        def __call__(self):
            file_obj = self.field.get(self.context)
            if not file_obj:
                return None
            data = (
                file_obj.data.data
                if isinstance(file_obj.data, Pdata)
                else file_obj.data
            )
            if len(data) > FILE_SIZE_WARNING:
                logger.info(
                    "Large File for {}: {}".format(
                        self.context.absolute_url(), size(len(data))
                    )
                )
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "data": base64.b64encode(data),
                "encoding": "base64",
            }
            return json_compatible(result)

    def get_at_blob_path(obj):
        return get_blob_path(obj.getBlob())

    @adapter(IBlobImageField, IBaseObject, IPathBlobsMarker)
    @implementer(IFieldSerializer)
    class ATImageFieldSerializerWithBlobPaths(ATDefaultFieldSerializer):
        def __call__(self):
            file_obj = self.field.get(self.context)
            if not file_obj:
                return None
            blobfilepath = get_at_blob_path(file_obj)
            if not blobfilepath:
                logger.warning(
                    "Blob file path of %s does not exist",
                    self.context.absolute_url(),
                )
                return
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "blob_path": blobfilepath,
            }
            return json_compatible(result)

    @adapter(IBlobField, IBaseObject, IPathBlobsMarker)
    @implementer(IFieldSerializer)
    class ATFileFieldSerializerWithBlobPaths(ATDefaultFieldSerializer):
        def __call__(self):
            file_obj = self.field.get(self.context)
            if not file_obj:
                return None

            blobfilepath = get_at_blob_path(file_obj)
            if not blobfilepath:
                logger.warning(
                    "Blob file path of %s does not exist",
                    self.context.absolute_url(),
                )
                return
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "blob_path": blobfilepath,
            }
            return json_compatible(result)

    @adapter(ITextField, IBaseObject, IRawRichTextMarker)
    @implementer(IFieldSerializer)
    class ATTextFieldSerializer(ATDefaultFieldSerializer):
        def __call__(self):
            data = self.field.getRaw(self.context)
            if not data:
                return
            if isinstance(self.field.widget, RichWidget):
                mimetype = self.field.getContentType(self.context)
                if mimetype == "text/html":
                    # cleanup crazy html but keep links with resolveuid
                    transforms = getToolByName(self.context, "portal_transforms")
                    data = transforms.convertTo(
                        "text/x-html-safe", data, mimetype=mimetype
                    ).getData()
                return {
                    "content-type": json_compatible(mimetype),
                    "data": json_compatible(data),
                }
            else:
                return json_compatible(data)


if HAS_AT and HAS_PAC:
    # This only works when Topics and plone.app.contenttypes is available
    from plone.app.contenttypes.migration.topics import CONVERTERS
    from plone.app.querystring.interfaces import IQuerystringRegistryReader
    from plone.registry.interfaces import IRegistry
    from plone.restapi.interfaces import ISerializeToJson
    from plone.restapi.serializer.atcontent import SerializeToJson
    from Products.ATContentTypes.interfaces.topic import IATTopic

    @implementer(ISerializeToJson)
    @adapter(IATTopic, IMigrationMarker)
    class SerializeTopicToJson(SerializeToJson):
        """This uses the topic migration from p.a.contenttypes to turn Criteria into a Querystring."""

        def __call__(self, version=None, include_items=False):
            # 1. Get the default serialisation for AT content
            item = super(SerializeTopicToJson, self).__call__(version=version)

            # 2. Get querystring-registry
            query = []
            reg = getUtility(IRegistry)
            reader = IQuerystringRegistryReader(reg)
            registry = reader.parseRegistry()

            # Inject new selection-operators that were added in Plone 5
            selection = registry["plone"]["app"]["querystring"]["operation"][
                "selection"
            ]
            new_operators = ["all", "any", "none"]
            for operator in new_operators:
                if operator not in selection:
                    # just a dummy method to pass validation
                    selection[operator] = {"operation": "collective.exportimport"}

            # Inject any operator for some fields
            any_operator = "plone.app.querystring.operation.selection.any"
            fields_with_any_operator = [
                "Creator",
                "Subject",
                "portal_type",
                "review_state",
            ]
            for field in fields_with_any_operator:
                operations = registry["plone"]["app"]["querystring"]["field"][field][
                    "operations"
                ]
                if any_operator not in operations:
                    registry["plone"]["app"]["querystring"]["field"][field][
                        "operations"
                    ].append(any_operator)

            # Inject all operator for Subject
            all_operator = "plone.app.querystring.operation.selection.all"
            fields_with_any_operator = ["Subject"]
            for field in fields_with_any_operator:
                operations = registry["plone"]["app"]["querystring"]["field"][field][
                    "operations"
                ]
                if all_operator not in operations:
                    registry["plone"]["app"]["querystring"]["field"][field][
                        "operations"
                    ].append(all_operator)

            # 3. Migrate criteria using the converters from p.a.contenttypes
            criteria = self.context.listCriteria()
            for criterion in criteria:
                type_ = criterion.__class__.__name__
                if type_ == "ATSortCriterion":
                    # Migrate sorting
                    item["sort_reversed"] = criterion.getReversed()
                    item["sort_on"] = criterion.Field()
                    continue

                converter = CONVERTERS.get(type_)
                if converter is None:
                    msg = "Unsupported criterion {0}".format(type_)
                    logger.error(msg)
                    raise ValueError(msg)
                before = len(query)
                try:
                    converter(query, criterion, registry)
                except Exception:
                    logger.info(
                        "Error converting criterion %s",
                        criterion.__dict__,
                        exc_info=True,
                    )
                    pass

                # Try to manually convert when no criterion was added
                # this happens with invalid criteria (e.g. path without a path)
                if len(query) == before:
                    fixed = self.fix_criteria(criterion)
                    if fixed:
                        query.append(fixed)
                    else:
                        logger.info(
                            "Check maybe broken collection %s",
                            self.context.absolute_url(),
                        )

            # 4. So some manual fixes in the migrated query
            indexes_to_fix = [
                "portal_type",
                "review_state",
                "Creator",
                "Subject",
            ]
            operator_mapping = {
                # old -> new
                "plone.app.querystring.operation.selection.is": "plone.app.querystring.operation.selection.any",
                "plone.app.querystring.operation.string.is": "plone.app.querystring.operation.selection.any",
            }
            fixed_query = []
            for crit in query:
                if crit["o"].endswith("relativePath") and crit["v"] == "..":
                    # relativePath no longer accepts ..
                    crit["v"] = "..::1"
                if crit["i"] in indexes_to_fix:
                    for old_operator, new_operator in operator_mapping.items():
                        if crit["o"] == old_operator:
                            crit["o"] = new_operator
                if crit["o"] == "plone.app.querystring.operation.string.currentUser":
                    crit["v"] = ""
                fixed_query.append(crit)
            query = fixed_query

            # 5. Migrate batch size
            if self.context.itemCount:
                item["item_count"] = self.context.itemCount

            # 6. Migrate customView
            if item.pop("customView", False):
                item["layout"] = "tabular_view"

            item["query"] = json_compatible(query)
            return item

        def fix_criteria(self, criterion):
            """Try to fix some invalid criteria"""
            FIXES = {
                # real operators
                "or": "plone.app.querystring.operation.selection.any",
                # fake operators
                "contains": "plone.app.querystring.operation.string.contains",
                "any": "plone.app.querystring.operation.selection.any",
            }

            type_ = criterion.__class__.__name__
            field = criterion.field
            value = getattr(criterion, "value", None)
            operator = getattr(criterion, "operator", None)

            if type_ == "ATSimpleStringCriterion":
                operator = "contains"
            if type_ == "ATSelectionCriterion":
                operator = "any"
            if type_ == "ATListCriterion":
                operator = "any"
            if type_ in ["ATPathCriterion", "ATDateCriteria"] and not value:
                return
            if field == "commentators":
                # no index
                return

            query = {
                "i": field,
                "o": FIXES.get(operator, operator),
                "v": value,
            }
            return query


def get_dx_blob_path(obj):
    return get_blob_path(obj._blob)


@adapter(INamedFileField, IDexterityContent, IPathBlobsMarker)
@implementer(IFieldSerializer)
class FileFieldSerializerWithBlobPaths(DefaultFieldSerializer):
    def __call__(self):
        namedfile = self.field.get(self.context)
        if namedfile is None:
            return None

        blobfilepath = get_dx_blob_path(namedfile)
        if not blobfilepath:
            logger.warning(
                "Blob file path of %s does not exist",
                self.context.absolute_url(),
            )
            return
        result = {
            "filename": namedfile.filename,
            "content-type": namedfile.contentType,
            "size": namedfile.getSize(),
            "blob_path": blobfilepath,
        }
        return json_compatible(result)


@adapter(INamedImageField, IDexterityContent, IPathBlobsMarker)
@implementer(IFieldSerializer)
class ImageFieldSerializerWithBlobPaths(DefaultFieldSerializer):
    def __call__(self):
        image = self.field.get(self.context)
        if image is None:
            return None

        blobfilepath = get_dx_blob_path(image)
        if not blobfilepath:
            logger.warning(
                "Blob file path of %s does not exist",
                self.context.absolute_url(),
            )
            return
        width, height = image.getImageSize()
        result = {
            "filename": image.filename,
            "content-type": image.contentType,
            "size": image.getSize(),
            "width": width,
            "height": height,
            "blob_path": blobfilepath,
        }
        return json_compatible(result)


if six.PY2:

    @adapter(long)
    @implementer(IJsonCompatible)
    def long_converter(value):
        # convert long (py2 only)
        return int(str(value))

else:

    @adapter(int)
    @implementer(IJsonCompatible)
    def long_converter(value):
        # same as default_converter for py3
        return value
