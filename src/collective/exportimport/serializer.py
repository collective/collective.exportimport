# -*- coding: utf-8 -*-
from collective.exportimport.interfaces import IBase64BlobsMarker
from collective.exportimport.interfaces import IMigrationMarker
from collective.exportimport.interfaces import IPathBlobsMarker
from collective.exportimport.interfaces import IRawRichTextMarker
from hurry.filesize import size
from plone.app.textfield.interfaces import IRichText
from plone.dexterity.interfaces import IDexterityContent
from plone.namedfile.interfaces import INamedFileField
from plone.namedfile.interfaces import INamedImageField
from plone.restapi.interfaces import IFieldSerializer
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.serializer.dxfields import DefaultFieldSerializer
from Products.CMFCore.utils import getToolByName
from zope.component import adapter
from zope.component import getUtility
from zope.interface import implementer

import base64
import logging
import os
import pkg_resources

try:
    pkg_resources.get_distribution("Products.Archetypes")
except pkg_resources.DistributionNotFound:
    HAS_AT = False
else:
    HAS_AT = True


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


# Custom Serializers


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
                u"data": json_compatible(output),
                u"content-type": json_compatible(value.mimeType),
                u"encoding": json_compatible(value.encoding),
            }


def get_relative_blob_path(obj, full_path):
    # Get blob path relative from the blobstorage root.
    db = obj._p_jar.db()
    base_dir = db._storage.fshelper.base_dir
    if not full_path.startswith(base_dir):
        return full_path
    return full_path[len(base_dir):]


if HAS_AT:
    from OFS.Image import Pdata
    from plone.app.blob.interfaces import IBlobField
    from plone.app.blob.interfaces import IBlobImageField
    from plone.restapi.serializer.atfields import (
        DefaultFieldSerializer as ATDefaultFieldSerializer,
    )
    from Products.Archetypes.atapi import RichWidget
    from Products.Archetypes.interfaces import IBaseObject
    from Products.Archetypes.interfaces.field import IFileField
    from Products.Archetypes.interfaces.field import IImageField
    from Products.Archetypes.interfaces.field import ITextField

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
                    u"Large image for {}: {}".format(
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
                    u"Large file for {}: {}".format(
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
                    u"Large image for {}: {}".format(
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
                    u"Large File for {}: {}".format(
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
        full_path = obj.getBlob().committed()
        if not os.path.exists(full_path):
            return
        return get_relative_blob_path(obj, full_path)

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
            topic_metadata = super(SerializeTopicToJson, self).__call__(version=version)

            # migrate criteria
            formquery = []
            reg = getUtility(IRegistry)
            reader = IQuerystringRegistryReader(reg)
            self.registry = reader.parseRegistry()

            criteria = self.context.listCriteria()
            for criterion in criteria:
                type_ = criterion.__class__.__name__
                if type_ == "ATSortCriterion":
                    # Sort order and direction are now stored in the Collection.
                    self._collection_sort_reversed = criterion.getReversed()
                    self._collection_sort_on = criterion.Field()
                    logger.debug(
                        "Sort on %r, reverse: %s.",
                        self._collection_sort_on,
                        self._collection_sort_reversed,
                    )
                    continue

                converter = CONVERTERS.get(type_)
                if converter is None:
                    msg = "Unsupported criterion {0}".format(type_)
                    logger.error(msg)
                    raise ValueError(msg)
                try:
                    converter(formquery, criterion, self.registry)
                except Exception as e:
                    logger.info(e)

            topic_metadata["query"] = json_compatible(formquery)

            # migrate batch size
            if self.context.itemCount:
                topic_metadata["b_size"] = self.context.itemCount

            return topic_metadata


def get_dx_blob_path(obj):
    full_path = obj._blob.committed()
    if not os.path.exists(full_path):
        return
    return get_relative_blob_path(obj, full_path)


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
