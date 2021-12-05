# -*- coding: utf-8 -*-
from Acquisition import aq_base
from collective.exportimport import config
from OFS.interfaces import IOrderedContainer
from operator import itemgetter
from plone import api
from plone.app.discussion.interfaces import IConversation
from plone.app.textfield.value import RichTextValue
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.serializer.converters import json_compatible
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from zope.component import getMultiAdapter
from zope.component import queryUtility
from plone.app.portlets.interfaces import IPortletTypeInterface
from plone.portlets.interfaces import IPortletAssignmentMapping
from plone.portlets.interfaces import ILocalPortletAssignmentManager
from plone.portlets.interfaces import IPortletAssignmentSettings
from plone.portlets.interfaces import IPortletManager
from plone.portlets.constants import (
    USER_CATEGORY,
    GROUP_CATEGORY,
    CONTENT_TYPE_CATEGORY,
    CONTEXT_CATEGORY,
)
from zope.component import getUtilitiesFor
from zope.component import queryMultiAdapter
from zope.interface import providedBy

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


try:
    pkg_resources.get_distribution("zc.relation")
except pkg_resources.DistributionNotFound:
    HAS_DX = False
else:
    HAS_DX = True

try:
    pkg_resources.get_distribution("z3c.relationfield")
except pkg_resources.DistributionNotFound:
    RelationValue = None
else:
    from z3c.relationfield import RelationValue


logger = logging.getLogger(__name__)


class ExportRelations(BrowserView):
    """Export all relations"""

    def __call__(self, debug=False):
        self.title = "Export relations"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_stored_relations = self.get_all_references(debug)
        data = json.dumps(all_stored_relations, indent=4)
        filename = "relations.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def get_all_references(self, debug=False):
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
                    source = uuidToObject(rel.sourceUID)
                    target = uuidToObject(rel.targetUID)
                    if not source or not target:
                        continue
                    item = {
                        "from_uuid": rel.sourceUID,
                        "to_uuid": rel.targetUID,
                        "relationship": rel.relationship,
                    }
                    if debug:
                        item["from_path"] = source.absolute_url_path()
                        item["to_path"] = target.absolute_url_path()
                    item = self.reference_hook(item)
                    if item is None:
                        continue
                    results.append(item)

        if HAS_DX:
            from zc.relation.interfaces import ICatalog

            # Dexterity
            # Get all data from zc.relation (relation_catalog)
            relation_catalog = queryUtility(ICatalog)
            if relation_catalog:
                portal_catalog = getToolByName(self.context, "portal_catalog")
                for rel in relation_catalog.findRelations():
                    if rel.from_path and rel.to_path:
                        from_brain = portal_catalog(
                            path=dict(query=rel.from_path, depth=0)
                        )
                        to_brain = portal_catalog(path=dict(query=rel.to_path, depth=0))
                        if len(from_brain) > 0 and len(to_brain) > 0:
                            item = {
                                "from_uuid": from_brain[0].UID,
                                "to_uuid": to_brain[0].UID,
                                "relationship": rel.from_attribute,
                            }
                            if self.debug:
                                item["from_path"] = from_brain[0].getPath()
                                item["to_path"] = to_brain[0].getPath()
                            item = self.reference_hook(item)
                            if item is None:
                                continue
                            results.append(item)

        return results

    def reference_hook(self, item):
        return item


class ExportMembers(BrowserView):
    """Export plone groups and members"""

    MEMBER_PROPERTIES = [
        "email",
        "listed",
        "login_time",
        "last_login_time",
        "fullname",
        "home_page",
        "location",
        "description",
    ]

    AUTO_GROUPS = ["AuthenticatedUsers"]
    AUTO_ROLES = ["Authenticated"]

    def __call__(self):
        self.title = "Export members, groups and roles"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        self.pms = api.portal.get_tool("portal_membership")
        data = {}
        data["groups"] = self.export_groups()
        data["members"] = [i for i in self.export_members()]
        msg = u"Exported {} groups and {} members".format(
            len(data["groups"]), len(data["members"])
        )
        logger.info(msg)
        data = json.dumps(data, sort_keys=True, indent=4)
        response = self.request.response
        response.setHeader("content-type", "application/json")
        response.setHeader("content-length", len(data))
        response.setHeader("content-disposition", 'attachment; filename="members.json"')
        return response.write(safe_bytes(data))

    def export_groups(self):
        data = []
        for group in api.group.get_groups():
            if group.id in self.AUTO_GROUPS:
                continue
            item = {"groupid": group.id}
            item["roles"] = [
                i for i in api.group.get_roles(group=group) if i not in self.AUTO_ROLES
            ]
            item["groups"] = [
                i.id
                for i in api.group.get_groups(user=group)
                if i.id not in self.AUTO_GROUPS
            ]
            for prop in group.getProperties():
                item[prop] = json_compatible(group.getProperty(prop))
            data.append(item)
        return data

    def export_members(self):
        pg = api.portal.get_tool("portal_groups")
        acl = api.portal.get_tool("acl_users")
        gids = set([item["id"] for item in acl.searchGroups()])
        self.group_roles = {}
        for gid in gids:
            self.group_roles[gid] = pg.getGroupById(gid).getRoles()
        return self._getUsersInfos()

    def _getUsersInfos(self):
        """Generator filled with the members data."""
        acl = api.portal.get_tool("acl_users")
        for user in acl.searchUsers():
            if not user["pluginid"] == "mutable_properties":
                yield self._getUserData(user["userid"])

    def _getUserPassword(self, userId):
        acl = api.portal.get_tool("acl_users")
        users = acl.source_users
        passwords = users._user_passwords
        password = passwords.get(userId, "")
        if six.PY3 and isinstance(password, bytes):
            # bytes are not json serializable.
            # Happens at least in the tests.
            password = password.decode("utf-8")
        return password

    def _getUserData(self, userId):
        member = self.pms.getMemberById(userId)
        groups = member.getGroups()
        groups = [i for i in groups if i not in self.AUTO_GROUPS]
        group_roles = []
        for gid in groups:
            group_roles.extend(self.group_roles.get(gid, []))
        roles = [
            role
            for role in member.getRoles()
            if role not in group_roles and role not in self.AUTO_ROLES
        ]
        # userid, password, roles
        props = {
            # TODO: We should have userid and username (login name).
            "username": userId,
            "password": self._getUserPassword(userId),
            "roles": json_compatible(roles),
            "groups": json_compatible(groups),
        }
        if member is not None:
            # TODO: Add support for any additional member-properties.
            for prop in self.MEMBER_PROPERTIES:
                props[prop] = json_compatible(member.getProperty(prop))
        return props


class ExportTranslations(BrowserView):

    DROP_PATH = []

    def __call__(self):
        self.title = "Export translations"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_translations = self.all_translations()
        data = json.dumps(all_translations, indent=4)
        filename = "translations.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def all_translations(self):  # noqa: C901
        results = []

        # Archetypes with LinguaPlone
        if HAS_AT:
            try:
                pkg_resources.get_distribution("Products.LinguaPlone")
            except pkg_resources.DistributionNotFound:
                HAS_LINGUAPLONE = False
            else:
                HAS_LINGUAPLONE = True

            if HAS_LINGUAPLONE:
                from Products.Archetypes.config import REFERENCE_CATALOG

                # Get all data from the reference_catalog if it exists
                reference_catalog = getToolByName(self.context, REFERENCE_CATALOG, None)
                if reference_catalog is not None:
                    for ref in reference_catalog(relationship="translationOf"):
                        source = api.content.get(UID=ref.sourceUID)
                        if not source:
                            continue
                        item = {}
                        translations = source.getTranslations()
                        for lang in translations:
                            if not lang:
                                logger.info(u"Skip translation: {}".format(lang))
                                continue
                            uuid = IUUID(translations[lang][0], None)
                            if uuid:
                                item[lang] = uuid
                        if len(item) < 2:
                            continue
                        results.append(item)

        # Archetypes and Dexterity with plone.app.multilingual
        portal_catalog = api.portal.get_tool("portal_catalog")
        if "TranslationGroup" not in portal_catalog.indexes():
            logger.debug(u"No index TranslationGroup (p.a.multilingual not installed)")
            return results

        for uid in portal_catalog.uniqueValuesFor("TranslationGroup"):
            brains = portal_catalog(TranslationGroup=uid)

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
                    logger.info(
                        u"Duplicate language for {}: {}".format(
                            uid, [i.getPath() for i in brains]
                        )
                    )
                item[brain.Language] = brain.UID

            if not skip:
                results.append(item)
        return results


class ExportLocalRoles(BrowserView):
    """Export all local roles"""

    def __call__(self):
        self.title = "Export local roles"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_localroles = self.all_localroles()
        data = json.dumps(all_localroles, indent=4)
        filename = "localroles.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def all_localroles(self):
        self.results = []

        portal = api.portal.get()
        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=self.get_localroles)
        return self.results

    def get_localroles(self, obj, path):
        uid = IUUID(obj, None)
        if not uid:
            return
        localroles = None
        block = None
        obj = aq_base(obj)
        if getattr(obj, "__ac_local_roles__", None) is not None:
            localroles = obj.__ac_local_roles__
        if getattr(obj, "__ac_local_roles_block__", False):
            block = obj.__ac_local_roles_block__
        if localroles or block:
            item = {"uuid": uid}
            if localroles:
                item["localroles"] = localroles
            if block:
                item["block"] = 1
            item = self.item_hook(item)
            if item is None:
                return
            self.results.append(item)

    def item_hook(self, item):
        return item


class ExportOrdering(BrowserView):
    """Export all local roles"""

    def __call__(self):
        self.title = "Export ordering"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_orders = self.all_orders()
        data = json.dumps(all_orders, indent=4)
        filename = "ordering.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def all_orders(self):
        results = []

        def get_position_in_parent(obj, path):
            uid = IUUID(obj, None)
            if not uid:
                return
            parent = obj.__parent__
            ordered = IOrderedContainer(parent, None)
            if ordered is not None:
                order = ordered.getObjectPosition(obj.getId())
                if order is not None:
                    results.append({"uuid": uid, "order": order})
            return

        portal = api.portal.get()
        portal.ZopeFindAndApply(
            portal, search_sub=True, apply_func=get_position_in_parent
        )
        return sorted(results, key=itemgetter("order"))


class ExportDefaultPages(BrowserView):
    """Export all default_page settings."""

    def __call__(self):
        self.title = "Export default pages"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_default_pages = self.all_default_pages()
        data = json.dumps(all_default_pages, indent=4)
        filename = "defaultpages.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def all_default_pages(self):
        results = []

        def get_default_page(obj, path):
            uid = IUUID(obj, None)
            if not uid:
                return
            default_page = obj.getDefaultPage()
            if default_page:
                results.append({"uuid": uid, "default_page": default_page})
            return

        portal = api.portal.get()
        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=get_default_page)
        portal_default_page = portal.getDefaultPage()
        if portal_default_page:
            results.append({"uuid": config.SITE_ROOT, "default_page": portal_default_page})
        return results


class ExportDiscussion(BrowserView):
    def __call__(self):
        self.title = "Export comments"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_discussions = self.all_discussions()
        data = json.dumps(all_discussions, indent=4)
        filename = "discussions.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def all_discussions(self):
        results = []

        def get_discussion(obj, path):
            conversation = IConversation(obj, None)
            if not conversation:
                return
            serializer = getMultiAdapter((conversation, self.request), ISerializeToJson)
            output = serializer()
            if output:
                results.append({"uuid": IUUID(obj), "conversation": output})
            return

        portal = api.portal.get()
        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=get_discussion)
        return results


class ExportPortlets(BrowserView):
    def __call__(self):
        self.title = "Export portlets"
        if not self.request.form.get("form.submitted", False):
            return self.index()

        all_portlets = self.all_portlets()
        data = json.dumps(all_portlets, indent=4)
        filename = "portlets.json"
        self.request.response.setHeader("Content-type", "application/json")
        self.request.response.setHeader("content-length", len(data))
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{0}"'.format(filename)
        )
        return self.request.response.write(safe_bytes(data))

    def all_portlets(context=None):
        results = []

        def get_portlets(obj, path):
            uid = IUUID(obj, None)
            if not uid:
                return
            portlets = export_local_portlets(obj)
            blacklist = export_portlets_blacklist(obj)
            obj_results = {}
            if portlets:
                obj_results["portlets"] = portlets
            if blacklist:
                obj_results["blacklist_status"] = blacklist
            if obj_results:
                obj_results["uuid"] = uid
                results.append(obj_results)
            return

        portal = api.portal.get()
        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=get_portlets)
        return results


def export_local_portlets(obj):
    """Serialize portlets for one content object
    Code mostly taken from https://github.com/plone/plone.restapi/pull/669
    """
    portlets_schemata = {
        iface: name for name, iface in getUtilitiesFor(IPortletTypeInterface)
    }
    items = {}
    for manager_name, manager in getUtilitiesFor(IPortletManager):
        mapping = queryMultiAdapter((obj, manager), IPortletAssignmentMapping)
        if mapping is None:
            continue
        mapping = mapping.__of__(obj)
        for name, assignment in mapping.items():
            portlet_type = None
            schema = None
            for schema in providedBy(assignment).flattened():
                portlet_type = portlets_schemata.get(schema, None)
                if portlet_type is not None:
                    break
            if portlet_type is None:
                continue
            assignment = assignment.__of__(mapping)
            settings = IPortletAssignmentSettings(assignment)
            if manager_name not in items:
                items[manager_name] = []
            values = {}
            for name in schema.names():
                value = getattr(assignment, name, None)
                if RelationValue is not None and isinstance(value, RelationValue):
                    value = value.to_object.UID()
                elif isinstance(value, RichTextValue):
                    value = {
                        "data": json_compatible(value.raw),
                        "content-type": json_compatible(value.mimeType),
                        "encoding": json_compatible(value.encoding),
                    }
                value = json_compatible(value)
                values[name] = value
            items[manager_name].append(
                {
                    "type": portlet_type,
                    "visible": settings.get("visible", True),
                    "assignment": values,
                }
            )
    return items


def export_portlets_blacklist(obj):
    results = []
    for manager_name, manager in getUtilitiesFor(IPortletManager):
        assignable = queryMultiAdapter((obj, manager), ILocalPortletAssignmentManager)
        if assignable is None:
            continue
        for category in (
            USER_CATEGORY,
            GROUP_CATEGORY,
            CONTENT_TYPE_CATEGORY,
            CONTEXT_CATEGORY,
        ):
            obj_results = {}
            status = assignable.getBlacklistStatus(category)
            if status is True:
                obj_results["status"] = u"block"
            elif status is False:
                obj_results["status"] = u"show"

            if obj_results:
                obj_results["manager"] = manager_name
                obj_results["category"] = category
                results.append(obj_results)
    return results


def safe_bytes(value, encoding="utf-8"):
    """Convert text to bytes of the specified encoding."""
    if isinstance(value, six.text_type):
        value = value.encode(encoding)
    return value
