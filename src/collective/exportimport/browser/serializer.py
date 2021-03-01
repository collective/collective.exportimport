from hurry.filesize import size
from operator import itemgetter
from plone import api
from plone.app.textfield.interfaces import IRichText
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.interfaces import IDexterityFTI
from plone.namedfile.interfaces import INamedFileField
from plone.namedfile.interfaces import INamedImageField
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.restapi.interfaces import IFieldSerializer
from plone.restapi.interfaces import IJsonCompatible
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.serializer.dxfields import DefaultFieldSerializer
from Products.CMFCore.utils import getToolByName
from Products.CMFDynamicViewFTI.interfaces import IDynamicViewTypeInformation
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.relationfield.interfaces import IRelationValue
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.i18n import translate
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.interface import Interface
from zope.interface import noLongerProvides

import base64


@adapter(INamedImageField, IDexterityContent, IBase64BlobsMarker)
class ImageFieldSerializerWithBlobs(DefaultFieldSerializer):
    def __call__(self):
        image = self.field.get(self.context)
        if not image:
            return None

        if 'built-in function id' in image.filename:
            filename = self.context.id
        else:
            filename = image.filename

        result = {
            "filename": filename,
            "content-type": image.contentType,
            "data":  base64.b64encode(image.data),
            "encoding": "base64",
        }
        return json_compatible(result)


@adapter(INamedFileField, IDexterityContent, IBase64BlobsMarker)
class FileFieldSerializerWithBlobs(DefaultFieldSerializer):
    def __call__(self):
        namedfile = self.field.get(self.context)
        if namedfile is None:
            return None

        if 'built-in function id' in namedfile.filename:
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


if HAS_AT:
    from OFS.Image import Pdata
    from plone.app.blob.interfaces import IBlobField
    from plone.app.blob.interfaces import IBlobImageField
    from plone.restapi.serializer.atfields import DefaultFieldSerializer as ATDefaultFieldSerializer
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
                logger.info(u'Large image for {}: {}'.format(self.context.absolute_url(), size(len(data))))
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": image.getContentType(),
                "data": base64.b64encode(data),
                "encoding": "base64",
            }
            return json_compatible(result)


    @adapter(IFileField, IBaseObject, IBase64BlobsMarker)
    @implementer(IFieldSerializer)
    class ATFileFieldSerializer(ATDefaultFieldSerializer):
        def __call__(self):
            file_obj = self.field.get(self.context)
            if not file_obj:
                return None
            data = file_obj.data.data if isinstance(file_obj.data, Pdata) else file_obj.data
            if len(data) > FILE_SIZE_WARNING:
                logger.info(u'Large file for {}: {}'.format(self.context.absolute_url(), size(len(data))))

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
                logger.info(u'Large image for {}: {}'.format(self.context.absolute_url(), size(len(data))))
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
            data = file_obj.data.data if isinstance(file_obj.data, Pdata) else file_obj.data
            if len(data) > FILE_SIZE_WARNING:
                logger.info(u'Large File for {}: {}'.format(self.context.absolute_url(), size(len(data))))
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "data": base64.b64encode(data),
                "encoding": "base64",
            }
            return json_compatible(result)


    @adapter(ITextField, IBaseObject, IRawRichTextMarker)
    @implementer(IFieldSerializer)
    class ATTextFieldSerializer(ATDefaultFieldSerializer):
        def __call__(self):
            data = self.field.getRaw(self.context)
            if not data:
                return
            mimetype = self.field.getContentType(self.context)
            if mimetype == 'text/html':
                # cleanup crazy html but keep links with resolveuid
                transforms = getToolByName(self.context, "portal_transforms")
                data = transforms.convertTo('text/x-html-safe', data, mimetype=mimetype).getData()
            return {
                "content-type": json_compatible(mimetype),
                "data": data,
            }


@adapter(IRelationValue)
@implementer(IJsonCompatible)
def relationvalue_converter_uuid(value):
    """Save uuid instead of summary
    """
    if value.to_object:
        return value.to_object.UID()