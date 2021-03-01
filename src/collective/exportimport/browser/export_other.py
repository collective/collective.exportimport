# -*- coding: utf-8 -*-
from plone import api
from plone.restapi.serializer.converters import json_compatible
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from zc.relation.interfaces import ICatalog
from zope.component import queryUtility

import json
import pkg_resources
import six
import logging

try:
    pkg_resources.get_distribution("Products.Archetypes")
except pkg_resources.DistributionNotFound:
    HAS_AT = False
else:
    HAS_AT = True

logger = logging.getLogger(__name__)


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
        return self.request.response.write(safe_bytes(data))

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
        relation_catalog = queryUtility(ICatalog)
        if relation_catalog:
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
        return response.write(safe_bytes(data))

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
        return self.request.response.write(safe_bytes(data))


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
        return self.request.response.write(safe_bytes(data))

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


def safe_bytes(value, encoding='utf-8'):
    """Convert text to bytes of the specified encoding.
    """
    if isinstance(value, six.text_type):
        value = value.encode(encoding)
    return value
