# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""
from zope.interface import Interface


class IBase64BlobsMarker(Interface):
    """A marker interface to override default serializers."""


class IRawRichTextMarker(Interface):
    """A marker interface to override default serializers for Richtext."""
