# -*- coding: utf-8 -*-
from collections import OrderedDict
from collective.exportimport.interfaces import ICollectiveExportimportLayer
from operator import itemgetter
from plone import api
from plone.app.textfield.interfaces import IRichText
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.interfaces import IDexterityFTI
from plone.namedfile.interfaces import INamedFileField
from plone.namedfile.interfaces import INamedImageField
from plone.restapi.interfaces import IFieldSerializer
from plone.restapi.interfaces import IJsonCompatible
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.serializer.dxfields import DefaultFieldSerializer
from Products.CMFCore.interfaces import IContentish
from Products.CMFCore.utils import getToolByName
from Products.CMFDynamicViewFTI.interfaces import IDynamicViewTypeInformation
from Products.Five import BrowserView
from z3c.relationfield.interfaces import IRelationValue
from zc.relation.interfaces import ICatalog
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.component import queryUtility
from zope.i18n import translate
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.interface import Interface
from zope.interface import noLongerProvides

import base64
import json
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


logger = logging.getLogger(__name__)


class IBase64BlobsMarker(Interface):
    """A marker interface to override default serializers."""


class IRawRichTextMarker(Interface):
    """A marker interface to override default serializers for Richtext."""



class ExportRestapi(BrowserView):

    QUERY = {}

    DROP_PATHS = []

    def __call__(self, portal_type=None, include_blobs=False):
        self.portal_type = portal_type

        self.fixup_request()

        if not self.request.form.get('form.submitted', False):
            return self.index()

        if self.request.form.get('export_relations', False):
            view = ExportRelations(self.context, self.request)
            return view()

        if self.request.form.get('export_translations', False):
            view = ExportTranslations(self.context, self.request)
            return view()

        if self.request.form.get('export_members', False):
            view = ExportMembers(self.context, self.request)
            return view()

        if self.request.form.get('export_localroles', False):
            view = ExportLocalRoles(self.context, self.request)
            return view()

        if not self.portal_type:
            return self.index()

        data = self.export_content(include_blobs=include_blobs)
        number = len(data)
        msg = u'Exported {} {}'.format(number, self.portal_type)
        logger.info(msg)
        data = json.dumps(data, sort_keys=True, indent=4)
        response = self.request.response
        response.setHeader('content-type', 'application/json')
        response.setHeader('content-length', len(data))
        response.setHeader(
            'content-disposition',
            'attachment; filename="{0}.json"'.format(self.portal_type))
        return response.write(data)

    def build_query(self):
        query = {'portal_type': self.portal_type}
        catalog = api.portal.get_tool('portal_catalog')
        if 'Language' in catalog.indexes():
            query['Language'] = 'all'
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
        logger.info(u'Exporting {} {}'.format(len(brains), self.portal_type))

        if include_blobs:
            # Add marker-interface to request to use our custom serializers
            alsoProvides(self.request, IBase64BlobsMarker)

        # Override richtext serializer to export links using resolveuid/xxx
        alsoProvides(self.request, IRawRichTextMarker)

        for index, brain in enumerate(brains, start=1):
            skip = False
            for drop in self.DROP_PATHS:
                if drop in brain.getPath():
                    skip = True

            if skip:
                continue

            if not index % 100:
                logger.info(u'Handled {} items...'.format(index))
            obj = brain.getObject()
            try:
                serializer = getMultiAdapter((obj, self.request), ISerializeToJson)
                item = serializer(include_items=False)
                item = self.fixup_item(item)
                data.append(item)
            except Exception as e:
                logger.info(e)

        if include_blobs:
            # remove marker interface
            noLongerProvides(self.request, IBase64BlobsMarker)

        return data

    def portal_types(self):
        """A list with info on all content types with existing items.
        """
        catalog = api.portal.get_tool('portal_catalog')
        portal_types = api.portal.get_tool('portal_types')
        results = []
        query = self.build_query()
        for fti in portal_types.listTypeInfo():
            if not IDexterityFTI.providedBy(fti) and not IDynamicViewTypeInformation.providedBy(fti):
                # Ignore non-DX and non-AT types
                continue
            query['portal_type'] = fti.id
            query['limit'] = 1
            number = len(catalog(**query))
            if number >= 1:
                results.append({
                    'number': number,
                    'value': fti.id,
                    'title': translate(
                        fti.title, domain='plone', context=self.request)
                })
        return sorted(results, key=itemgetter('title'))

    def fixup_request(self):
        """Use this to override stuff (e.g. force a specific language in request)."""
        return

    def fixup_item(self, item):
        """Used this to modify the serialized data."""
        # drop stuff not needed for export/import
        item.pop('@components')
        item.pop('next_item')
        item.pop('previous_item')
        return item


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
    from plone.restapi.serializer.atfields import DefaultFieldSerializer as ATDefaultFieldSerializer
    from Products.Archetypes.interfaces.field import IFileField
    from Products.Archetypes.interfaces import IBaseObject
    from plone.app.blob.interfaces import IBlobField
    from plone.app.blob.interfaces import IBlobImageField
    from Products.Archetypes.interfaces.field import IImageField
    from OFS.Image import Pdata

    @adapter(IImageField, IBaseObject, IBase64BlobsMarker)
    @implementer(IFieldSerializer)
    class ATImageFieldSerializer(ATDefaultFieldSerializer):
        def __call__(self):
            image = self.field.get(self.context)
            if not image:
                return None
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": image.getContentType(),
                "data": base64.b64encode(image.data.data if isinstance(image.data, Pdata) else image.data),
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
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "data": base64.b64encode(file_obj.data.data),
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
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": image.getContentType(),
                "data": base64.b64encode(image.data.data if isinstance(image.data, Pdata) else image.data),
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
            result = {
                "filename": self.field.getFilename(self.context),
                "content-type": self.field.getContentType(self.context),
                "data": base64.b64encode(file_obj.data.data),
                "encoding": "base64",
            }
            return json_compatible(result)


@adapter(IRelationValue)
@implementer(IJsonCompatible)
def relationvalue_converter_uuid(value):
    """Save uuid instead of summary
    """
    if value.to_object:
        return value.to_object.UID()



class ExportRelations(BrowserView):
    """Export all relations
    """

    def __call__(self):
        all_stored_relations = self.get_all_references()
        data = json.dumps(all_stored_relations, indent=4)
        filename = 'relations.json'
        self.request.response.setHeader('Content-type', 'application/json')
        self.request.response.setHeader('content-length', len(data))
        self.request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="{0}"'.format(filename))
        return data

    def get_all_references(self):
        results = []

        if HAS_AT:
            from Products.Archetypes.config import REFERENCE_CATALOG

            # Archetypes
            # Get all data from the reference_catalog if it exists
            reference_catalog = getToolByName(self.context, REFERENCE_CATALOG, None)
            if reference_catalog is not None:
                ref_catalog = reference_catalog._catalog
                for rid in ref_catalog.data:
                    rel = ref_catalog[rid]
                    results.append({
                        'from_uuid': rel.sourceUID,
                        'to_uuid': rel.targetUID,
                        'relationship': rel.relationship,
                    })

        # Dexterity
        # Get all data from zc.relation (relation_catalog)
        relation_catalog = queryUtility(ICatalog, None)
        if relation_catalog is not None:
            portal_catalog = getToolByName(self.context, 'portal_catalog')
            for rel in relation_catalog.findRelations():
                if rel.from_path and rel.to_path:
                    from_brain = portal_catalog(path=dict(query=rel.from_path,
                                                          depth=0))
                    to_brain = portal_catalog(path=dict(query=rel.to_path, depth=0))
                    if len(from_brain) > 0 and len(to_brain) > 0:
                        results.append({
                            'from_uuid': from_brain[0].UID,
                            'to_uuid': to_brain[0].UID,
                            'relationship': rel.from_attribute,
                        })

        return results


class ExportMembers(BrowserView):
    """Export plone groups and members
    """

    MEMBER_PROPERTIES = [
        'email',
        'listed',
        'login_time',
        'last_login_time',
        'fullname',
        'home_page',
        'location',
        'description',
    ]

    AUTO_GROUPS = ['AuthenticatedUsers']
    AUTO_ROLES = ['Authenticated']

    def __call__(self):
        self.pms = api.portal.get_tool('portal_membership')
        data = {}
        data['groups'] = self.export_groups()
        data['members'] = sorted(self.export_members())
        msg = u'Exported {} groups and {} members'.format(len(data['groups']), len(data['members']))
        logger.info(msg)
        data = json.dumps(data, sort_keys=True, indent=4)
        response = self.request.response
        response.setHeader('content-type', 'application/json')
        response.setHeader('content-length', len(data))
        response.setHeader(
            'content-disposition',
            'attachment; filename="members.json"')
        return response.write(data)

    def export_groups(self):
        data = []
        for group in api.group.get_groups():
            if group.id in self.AUTO_GROUPS:
                continue
            item = {'groupid': group.id}
            item['roles'] = [i for i in api.group.get_roles(group=group) if i not in self.AUTO_ROLES]
            item['groups'] = [i.id for i in api.group.get_groups(user=group) if i.id not in self.AUTO_GROUPS]
            for prop in group.getProperties():
                item[prop] = json_compatible(group.getProperty(prop))
            data.append(item)
        return data

    def export_members(self):
        pg = api.portal.get_tool('portal_groups')
        acl = api.portal.get_tool('acl_users')
        gids = set([item['id'] for item in acl.searchGroups()])
        self.group_roles = {}
        for gid in gids:
            self.group_roles[gid] = pg.getGroupById(gid).getRoles()
        return self._getUsersInfos()

    def _getUsersInfos(self):
        """Generator filled with the members data."""
        acl = api.portal.get_tool('acl_users')
        for user in acl.searchUsers():
            if not user['pluginid'] == 'mutable_properties':
                yield self._getUserData(user['userid'])

    def _getUserPassword(self, userId):
        acl = api.portal.get_tool('acl_users')
        users = acl.source_users
        passwords = users._user_passwords
        return passwords.get(userId, '')

    def _getUserData(self, userId):
        member = self.pms.getMemberById(userId)
        groups = member.getGroups()
        groups = [i for i in groups if i not in self.AUTO_GROUPS]
        group_roles = []
        for gid in groups:
            group_roles.extend(self.group_roles.get(gid, []))
        roles = [role for role in member.getRoles() if role not in group_roles and role not in self.AUTO_ROLES]
        # userid, password, roles
        props = {
            'username': userId,
            'password': self._getUserPassword(userId),
            'roles': json_compatible(roles),
            'groups': json_compatible(groups),
            }
        if member is not None:
            # TODO: Add support for any additional member-properties.
            for prop in self.MEMBER_PROPERTIES:
                props[prop] = json_compatible(member.getProperty(prop))
        return props


class ExportTranslations(BrowserView):

    DROP_PATH = []

    def __call__(self):
        portal_catalog = api.portal.get_tool('portal_catalog')
        if 'TranslationGroup' not in  portal_catalog.indexes():
            logger.info(u'No index TranslationGroup (p.a.multilingual not installed)')
            return
        results = []
        for uid in portal_catalog.uniqueValuesFor('TranslationGroup'):
            brains = portal_catalog(TranslationGroup=uid, Language='all')

            if len(brains) < 2:
                # logger.info(u'Skipping...{} {}'.format(uid, brains))
                continue
            item = {}
            skip = False
            for brain in brains:
                for path in self.DROP_PATH:
                    if path in brain.getPath():
                        skip = True
                if not skip and brain.Language in item:
                    logger.info(u'Duplicate language for {}: {}'.format(uid, [i.getPath() for i in brains]))
                item[brain.Language] = brain.UID

            if not skip:
                results.append(item)

        # TODO: Add support for LinguaPlone
        # TODO: Add support for raptus.multilingual

        data = json.dumps(results, indent=4)
        filename = 'translations.json'
        self.request.response.setHeader('Content-Type', 'application/json')
        self.request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="{0}"'.format(filename))
        return data


class ExportLocalRoles(BrowserView):
    """Export all local roles
    """

    def __call__(self):
        all_localroles = self.all_localroles()
        data = json.dumps(all_localroles, indent=4)
        filename = 'localroles.json'
        self.request.response.setHeader('Content-type', 'application/json')
        self.request.response.setHeader('content-length', len(data))
        self.request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="{0}"'.format(filename))
        return data

    def all_localroles(self):
        results = []
        from Products.CMFPlone.utils import base_hasattr

        def get_localroles(obj, path):
            if not base_hasattr(obj, '__ac_local_roles__'):
                return
            if not base_hasattr(obj, 'UID'):
                return
            results.append({'uuid': obj.UID(), 'localroles': obj.__ac_local_roles__})

        portal = api.portal.get()
        portal.ZopeFindAndApply(portal,
                                search_sub=True,
                                apply_func=get_localroles)
        return results
