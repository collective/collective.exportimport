from collective.exportimport.interfaces import IMigrationMarker
from plone.app.textfield.interfaces import IRichText
from plone.app.textfield.value import RichTextValue
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.deserializer.dxfields import DefaultFieldDeserializer
from plone.restapi.interfaces import IFieldDeserializer
from zope.component import adapter
from zope.interface import implementer


@implementer(IFieldDeserializer)
@adapter(IRichText, IDexterityContent, IMigrationMarker)
class RichTextFieldDeserializerWithoutUnescape(DefaultFieldDeserializer):
    """Override default RichTextFieldDeserializer without using html_parser.unescape().
    Fixes https://github.com/collective/collective.exportimport/issues/99
    """
    def __call__(self, value):
        content_type = self.field.default_mime_type
        encoding = "utf8"
        if isinstance(value, dict):
            content_type = value.get("content-type", content_type)
            encoding = value.get("encoding", encoding)
            data = value.get("data", "")
        else:
            data = value
        value = RichTextValue(
            raw=data,
            mimeType=content_type,
            outputMimeType=self.field.output_mime_type,
            encoding=encoding,
        )
        self.field.validate(value)
        return value
