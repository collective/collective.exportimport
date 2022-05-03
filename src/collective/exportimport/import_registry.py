# -*- coding: utf-8 -*-
from collective.exportimport.interfaces import IMigrationMarker
from logging import getLogger
from plone import api
from plone.dexterity.interfaces import IDexterityContent
from plone.registry.interfaces import IRegistry
from plone.restapi.interfaces import IFieldDeserializer
from Products.Five import BrowserView
from Products.Five import BrowserView
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.interface import alsoProvides
from zope.interface import noLongerProvides
from ZPublisher.HTTPRequest import FileUpload

import json

logger = getLogger(__name__)


class ImportRegistry(BrowserView):
    """Import registry settings"""

    def __call__(self, jsonfile=None, return_json=False):
        if jsonfile:
            self.portal = api.portal.get()
            status = "success"
            try:
                if isinstance(jsonfile, str):
                    return_json = True
                    data = json.loads(jsonfile)
                elif isinstance(jsonfile, FileUpload):
                    data = json.loads(jsonfile.read())
                else:
                    raise ("Data is neither text nor upload.")
            except Exception as e:
                status = "error"
                logger.error(e)
                api.portal.show_message(
                    u"Failure while uploading: {}".format(e),
                    request=self.request,
                )
            else:
                results = self.import_registry(data)
                msg = u"Imported {} registry records".format(len(results))
                api.portal.show_message(msg, self.request)
                for msg in results:
                    api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_registry(self, data):
        alsoProvides(self.request, IMigrationMarker)
        registry = getUtility(IRegistry)
        records = registry.records
        results = []
        for interface, item in data.items():
            for key in item:
                try:
                    proxy = records[key]
                except KeyError:
                    logger.info(u"Registry has no record for %s", key)
                    continue
                current_value = proxy.value
                value = item[key]
                if current_value == value:
                    logger.debug(u"No changes to %s as %r", key, value)
                    continue

                try:
                    proxy.field.validate(value)
                except:
                    alsoProvides(proxy, IDexterityContent)
                    deserializer = queryMultiAdapter((proxy.field, proxy, self.request), IFieldDeserializer)
                    if deserializer:
                        try:
                            value = deserializer(value)
                        except Exception as e:
                            logger.error(u"Could not import %s as %s", value, key, exc_info=True)
                            pass
                    noLongerProvides(proxy, IDexterityContent)

                if current_value == value:
                    logger.debug(u"No changes to %s as %r", key, value)
                    continue

                try:
                    registry[key] = value
                except Exception:
                    logger.error(u"Could not import %s as %r", value, key, exc_info=True)
                    continue
                else:
                    msg = u"Imported {} as {}".format(key, value)
                    logger.info(msg)
                    results.append(msg)
        return results
