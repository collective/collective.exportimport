# -*- coding: utf-8 -*-
from collective.exportimport.export_other import BaseExport
from logging import getLogger
from plone.dexterity.interfaces import IDexterityContent
from plone.registry.interfaces import IRegistry
from plone.restapi.interfaces import IFieldSerializer
from plone.restapi.serializer.converters import json_compatible
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.dottedname.resolve import resolve
from zope.interface import alsoProvides
from zope.interface import noLongerProvides

logger = getLogger(__name__)


class ExportRegistry(BaseExport):

    # This can hold interfaces, keys and prefixes
    IGNORELIST = [
        "plone.app.querystring.interfaces.IQueryField",
        "plone.app.querystring.interfaces.IQueryOperation",
        "Products.CMFPlone.interfaces.resources.IResourceRegistry",
    ]

    def __call__(self, download_to_server=False):
        self.title = "Export registry settings"
        self.download_to_server = download_to_server
        self.interfaces = self.request.form.get("interfaces", [])
        if not isinstance(self.interfaces, list):
            self.interfaces = [self.interfaces]
        self.skip_defaults = self.request.form.get("skip_defaults", True)
        self.all_interfacenames_with_prefix = self.get_all_interfacenames_with_prefix()
        if not self.request.form.get("form.submitted", False):
            return self.index()

        data = self.registry_config(interfaces=self.interfaces, skip_defaults=self.skip_defaults)
        self.download(data)

    def registry_config(self, interfaces=[], skip_defaults=True):
        results = {}
        registry = getUtility(IRegistry)
        for path in interfaces:
            try:
                iface = resolve(path)
            except:
                logger.debug("{} not used in this site".format(path))
                continue
            items = {}
            prefix = self.all_interfacenames_with_prefix[path] or path
            proxy = registry.forInterface(iface, check=False, prefix=prefix)
            for key, field in proxy.__schema__.namesAndDescriptions():
                default = field.default
                name = prefix + '.' + key

                value = registry.get(name, None)
                if value is None:
                    # This means that the default value is used
                    continue

                if skip_defaults and value == default:
                    continue

                alsoProvides(proxy, IDexterityContent)
                serializer = queryMultiAdapter((field, proxy, self.request), IFieldSerializer)
                noLongerProvides(proxy, IDexterityContent)
                if serializer:
                    value = serializer()
                else:
                    value = json_compatible(value)
                items[name] = value

            if items:
                results[path] = items
        return results

    def get_all_interfacenames_with_prefix(self):
        results = []
        res = {}
        registry = getUtility(IRegistry)
        for record in registry.records.values():
            key = record.__name__
            prefix = ".".join(key.split(".")[:-1])
            interfacename = record.interfaceName

            if record.interfaceName == record.__name__:
                continue

            if not interfacename or interfacename in self.IGNORELIST:
                continue
            if key in self.IGNORELIST or prefix in self.IGNORELIST:
                continue

            if interfacename == prefix:
                prefix = None
            results.append((interfacename, prefix))

        for interfacename, prefix in sorted(results):
            res[interfacename] = prefix
        return res
