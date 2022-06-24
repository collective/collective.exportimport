# -*- coding: utf-8 -*-
from Acquisition import aq_base
from BTrees.LLBTree import LLSet
from collective.exportimport import config
from datetime import datetime
from OFS.interfaces import IOrderedContainer
from operator import itemgetter
from collective.exportimport.export_other import PORTAL_PLACEHOLDER
from plone import api
from plone.app.discussion.comment import Comment
from plone.app.discussion.interfaces import IConversation
from plone.app.portlets.interfaces import IPortletTypeInterface
from plone.app.redirector.interfaces import IRedirectionStorage
from plone.portlets.interfaces import ILocalPortletAssignmentManager
from plone.portlets.interfaces import IPortletAssignmentMapping
from plone.portlets.interfaces import IPortletAssignmentSettings
from plone.portlets.interfaces import IPortletManager
from plone.restapi.interfaces import IFieldDeserializer
from Products.Five import BrowserView
from Products.ZCatalog.ProgressHandler import ZLogHandler
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.component import queryUtility
from zope.component.interfaces import IFactory
from zope.container.interfaces import INameChooser
from zope.globalrequest import getRequest
from ZPublisher.HTTPRequest import FileUpload

import dateutil
import json
import logging
import six
import transaction

try:
    from collective.relationhelpers import api as relapi

    HAS_RELAPI = True
except ImportError:
    HAS_RELAPI = False

try:
    from Products.CMFPlone import relationhelper

    HAS_PLONE6 = True
except ImportError:
    HAS_PLONE6 = False

try:
    from plone.app.multilingual.interfaces import ITranslationManager

    HAS_PAM = True
except ImportError:
    HAS_PAM = False

if six.PY2:
    from HTMLParser import HTMLParser

    unescape = HTMLParser().unescape
else:
    from html import unescape


logger = logging.getLogger(__name__)

DISCUSSION_ANNOTATION_KEY = "plone.app.discussion:conversation"


if HAS_PAM:  # noqa: C901

    class ImportTranslations(BrowserView):
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
                    logger.error(e)
                    status = "error"
                    msg = e
                    api.portal.show_message(
                        u"Failure while uploading: {}".format(e),
                        request=self.request,
                    )
                else:
                    msg = self.do_import(data)
                    api.portal.show_message(msg, self.request)

            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)
            return self.index()

        def do_import(self, data):
            start = datetime.now()
            self.import_translations(data)
            transaction.commit()
            end = datetime.now()
            delta = end - start
            msg = "Imported translations in {} seconds".format(delta.seconds)
            logger.info(msg)
            return msg

        def import_translations(self, data):
            imported = 0
            empty = []
            less_than_2 = []
            for translationgroup in data:
                if len(translationgroup) < 2:
                    continue

                # Make sure we have content to translate
                tg_with_obj = {}
                for lang, uid in translationgroup.items():
                    obj = api.content.get(UID=uid)
                    if obj:
                        tg_with_obj[lang] = obj
                    else:
                        # logger.info(f'{uid} not found')
                        continue
                if not tg_with_obj:
                    empty.append(translationgroup)
                    continue

                if len(tg_with_obj) < 2:
                    less_than_2.append(translationgroup)
                    logger.info(u"Only one item: {}".format(translationgroup))
                    continue

                imported += 1
                for index, (lang, obj) in enumerate(tg_with_obj.items()):
                    if index == 0:
                        canonical = obj
                    else:
                        translation = obj
                        link_translations(canonical, translation, lang)
            logger.info(
                u"Imported {} translation-groups. For {} groups we found only one item. {} groups without content dropped".format(
                    imported, len(less_than_2), len(empty)
                )
            )

    def link_translations(obj, translation, language):
        if obj is translation or obj.language == language:
            logger.info(
                "Not linking {} to {} ({})".format(
                    obj.absolute_url(), translation.absolute_url(), language
                )
            )
            return
        logger.debug(
            "Linking {} to {} ({})".format(
                obj.absolute_url(), translation.absolute_url(), language
            )
        )
        try:
            ITranslationManager(obj).register_translation(language, translation)
        except TypeError as e:
            logger.info(u"Item is not translatable: {}".format(e))

else:
    class ImportTranslations(BrowserView):
        def __call__(self, jsonfile=None, return_json=False):
            return "This view only works when using plone.app.multilingual >= 2.0.0"


class ImportMembers(BrowserView):
    """Import plone groups and members"""

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
                groups = self.import_groups(data["groups"])
                members = self.import_members(data["members"])
                msg = u"Imported {} groups and {} members".format(groups, members)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_groups(self, data):
        acl = api.portal.get_tool("acl_users")
        pg = api.portal.get_tool("portal_groups")
        groupsIds = {item["id"] for item in acl.searchGroups()}

        groupsNumber = 0
        for item in data:
            if item["groupid"] not in groupsIds:  # New group, 'have to create it
                api.group.create(
                    groupname=item["groupid"],
                    title=item["title"],
                    description=item["description"],
                    roles=item["roles"],
                    groups=item["groups"],
                )
                # add all principals
                for principal in item.get("principals", []):
                    pg.addPrincipalToGroup(principal, item["groupid"])
                groupsNumber += 1
        return groupsNumber

    def import_members(self, data):
        pr = api.portal.get_tool("portal_registration")
        pg = api.portal.get_tool("portal_groups")
        acl = api.portal.get_tool("acl_users")
        groupsIds = {item["id"] for item in acl.searchGroups()}
        groupsDict = {}

        groupsNumber = 0
        for item in data:
            groups = item["groups"]
            for group in groups:
                if group not in groupsIds:  # New group, 'have to create it
                    pg.addGroup(group)
                    groupsNumber += 1

        usersNumber = 0
        for item in data:
            username = item["username"]
            if api.user.get(username=username) is not None:
                logger.error(u"Skipping: User {} already exists!".format(username))
                continue
            password = item.pop("password")
            roles = item.pop("roles")
            groups = item.pop("groups")
            if not item["email"]:
                logger.info(
                    u"Skipping user {} without email: {}".format(username, item)
                )
                continue
            try:
                pr.addMember(username, password, roles, [], item)
            except ValueError:
                logger.info(
                    u"ValueError {} : {}".format(username, item)
                )
                continue
            for group in groups:
                if group not in groupsDict.keys():
                    groupsDict[group] = acl.getGroupById(group)
                groupsDict[group].addMember(username)
            usersNumber += 1

        return usersNumber


class ImportRelations(BrowserView):

    # Overwrite to handle scustom relations
    RELATIONSHIP_FIELD_MAPPING = {
        # default relations of Plone 4 > 5
        "Working Copy Relation": "iterate-working-copy",
        "relatesTo": "relatedItems",
    }

    def __call__(self, jsonfile=None, return_json=False):

        if not HAS_RELAPI and not HAS_PLONE6:
            api.portal.show_message(
                "You need either Plone 6 or collective.relationhelpers to import relations",
                self.request,
            )
            return self.index()

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
                msg = u"Failure while uploading: {}".format(e)
                api.portal.show_message(msg, request=self.request)
            else:
                msg = self.do_import(data)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)
        return self.index()

    def do_import(self, data):
        start = datetime.now()
        self.import_relations(data)
        transaction.commit()
        end = datetime.now()
        delta = end - start
        msg = "Imported relations in {} seconds".format(delta.seconds)
        logger.info(msg)
        return msg

    def import_relations(self, data):
        ignore = [
            "translationOf",  # old LinguaPlone
            "isReferencing",  # linkintegrity
            "internal_references",  # obsolete
            "link",  # tab
            "link1",  # extranetfrontpage
            "link2",  # extranetfrontpage
            "link3",  # extranetfrontpage
            "link4",  # extranetfrontpage
            "box3_link",  # shopfrontpage
            "box1_link",  # shopfrontpage
            "box2_link",  # shopfrontpage
            "source",  # remotedisplay
            "internally_links_to",  # DoormatReference
        ]
        all_fixed_relations = []
        for rel in data:
            if rel["relationship"] in ignore:
                continue
            rel["from_attribute"] = self.get_from_attribute(rel)
            all_fixed_relations.append(rel)
        all_fixed_relations = sorted(
            all_fixed_relations, key=itemgetter("from_uuid", "from_attribute")
        )
        if HAS_RELAPI:
            relapi.purge_relations()
            relapi.cleanup_intids()
            relapi.restore_relations(all_relations=all_fixed_relations)
        elif HAS_PLONE6:
            relationhelper.purge_relations()
            relationhelper.cleanup_intids()
            relationhelper.restore_relations(all_relations=all_fixed_relations)

    def get_from_attribute(self, rel):
        # Optionally handle special cases...
        return self.RELATIONSHIP_FIELD_MAPPING.get(
            rel["relationship"], rel["relationship"]
        )


class ImportLocalRoles(BrowserView):
    """Import local roles"""

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
                localroles = self.import_localroles(data)
                msg = u"Imported {} localroles".format(localroles)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_localroles(self, data):
        results = 0
        total = len(data)
        for index, item in enumerate(data, start=1):
            obj = api.content.get(UID=item["uuid"])
            if not obj:
                if item["uuid"] == PORTAL_PLACEHOLDER:
                    obj = api.portal.get()
            if item.get("localroles"):
                localroles = item["localroles"]
                for userid in localroles:
                    obj.manage_setLocalRoles(userid=userid, roles=localroles[userid])
                logger.debug(
                    u"Set roles on {}: {}".format(obj.absolute_url(), localroles)
                )
            if item.get("block"):
                obj.__ac_local_roles_block__ = 1
                logger.debug(
                    u"Disable acquisition of local roles on {}".format(
                        obj.absolute_url()
                    )
                )
            if not index % 1000:
                logger.info(
                    u"Set local roles on {} ({}%) of {} items".format(
                        index, round(index / total * 100, 2), total
                    )
                )
            results += 1
        if results:
            logger.info("Reindexing Security")
            catalog = api.portal.get_tool("portal_catalog")
            pghandler = ZLogHandler(1000)
            catalog.reindexIndex("allowedRolesAndUsers", None, pghandler=pghandler)
        return results


class ImportOrdering(BrowserView):
    """Import content order"""

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
                start = datetime.now()
                orders = self.import_ordering(data)
                end = datetime.now()
                delta = end - start
                msg = u"Imported {} orders in {} seconds".format(orders, delta.seconds)
                logger.info(msg)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_ordering(self, data):
        results = 0
        total = len(data)
        for index, item in enumerate(data, start=1):
            obj = api.content.get(UID=item["uuid"])
            if not obj:
                continue
            ordered = IOrderedContainer(obj.__parent__, None)
            if not ordered:
                continue
            ordered.moveObjectToPosition(obj.getId(), item["order"])
            if not index % 1000:
                logger.info(
                    u"Ordered {} ({}%) of {} items".format(
                        index, round(index / total * 100, 2), total
                    )
                )
            results += 1
        return results


class ImportDefaultPages(BrowserView):
    """Import default pages"""

    def __call__(self, jsonfile=None, return_json=False):
        if jsonfile:
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
                defaultpages = self.import_default_pages(data)
                msg = u"Changed {} default pages".format(defaultpages)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_default_pages(self, data):
        results = 0
        for item in data:
            obj = api.content.get(UID=item["uuid"])
            if not obj:
                if item["uuid"] == config.SITE_ROOT:
                    obj = api.portal.get()
                else:
                    continue
            if "default_page_uuid" in item:
                default_page_obj = api.content.get(UID=item["default_page_uuid"])
                if not default_page_obj:
                    logger.info("Default page missing: %s", item["default_page_uuid"])
                    continue
                default_page = default_page_obj.id
            else:
                # fallback for old export versions
                default_page = item["default_page"]
            if default_page not in obj:
                logger.info(
                    u"Default page not a child: %s not in %s",
                    default_page,
                    obj.absolute_url(),
                )
                continue

            if default_page == "index_html":
                # index_html is automatically used as default page
                continue

            if six.PY2:
                obj.setDefaultPage(default_page.encode("utf-8"))
            else:
                obj.setDefaultPage(default_page)
            logger.debug(
                u"Set %s as default page for %s", default_page, obj.absolute_url()
            )
            results += 1
        return results


class ImportDiscussion(BrowserView):
    """Import default pages"""

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
                results = self.import_data(data)
                msg = u"Imported {} comments".format(results)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_data(self, data):
        results = 0
        for conversation_data in data:
            obj = api.content.get(UID=conversation_data["uuid"])
            if not obj:
                continue
            if not obj.restrictedTraverse("@@conversation_view").enabled():
                continue
            added = 0
            conversation = IConversation(obj)

            for item in conversation_data["conversation"]["items"]:

                if isinstance(item["text"], dict) and item["text"].get("data"):
                    item["text"] = item["text"]["data"]

                comment = Comment()
                comment_id = int(item["comment_id"])
                comment.comment_id = comment_id
                comment.creation_date = dateutil.parser.parse(item["creation_date"])
                comment.modification_date = dateutil.parser.parse(
                    item["modification_date"]
                )
                comment.author_name = item["author_name"]
                comment.author_username = item["author_username"]
                comment.creator = item["author_username"]
                comment.text = unescape(
                    item["text"]
                    .replace(u"\r<br />", u"\r\n")
                    .replace(u"<br />", u"\r\n")
                )

                if item["user_notification"]:
                    comment.user_notification = True
                if item.get("in_reply_to"):
                    comment.in_reply_to = int(item["in_reply_to"])

                conversation._comments[comment_id] = comment
                comment.__parent__ = aq_base(conversation)
                commentator = comment.author_username
                if commentator:
                    if commentator not in conversation._commentators:
                        conversation._commentators[commentator] = 0
                    conversation._commentators[commentator] += 1

                reply_to = comment.in_reply_to
                if not reply_to:
                    # top level comments are in reply to the faux id 0
                    comment.in_reply_to = reply_to = 0

                if reply_to not in conversation._children:
                    conversation._children[reply_to] = LLSet()
                conversation._children[reply_to].insert(comment_id)

                # Add the annotation if not already done
                annotions = IAnnotations(obj)
                if DISCUSSION_ANNOTATION_KEY not in annotions:
                    annotions[DISCUSSION_ANNOTATION_KEY] = aq_base(conversation)
                added += 1
            logger.info("Added {} comments to {}".format(added, obj.absolute_url()))
            results += added

        return results


class ImportPortlets(BrowserView):
    """Import portlets"""

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
                portlets = self.import_portlets(data)
                msg = u"Created {} portlets".format(portlets)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_portlets(self, data):
        results = 0
        for item in data:
            obj = api.content.get(UID=item["uuid"])
            if not obj:
                continue
            registered_portlets = register_portlets(obj, item)
            results += registered_portlets
        return results


def register_portlets(obj, item):
    """Register portlets fror one object
    Code adapted from plone.app.portlets.exportimport.portlets.PortletsXMLAdapter
    Work in progress...
    """
    site = api.portal.get()
    request = getRequest()
    results = 0
    for manager_name, portlets in item.get("portlets", {}).items():
        manager = queryUtility(IPortletManager, manager_name)
        if not manager:
            logger.info(u"No portlet manager {}".format(manager_name))
            continue
        mapping = queryMultiAdapter((obj, manager), IPortletAssignmentMapping)
        namechooser = INameChooser(mapping)

        for portlet_data in portlets:
            # 1. Create the assignment
            assignment_data = portlet_data["assignment"]
            portlet_type = portlet_data["type"]
            portlet_factory = queryUtility(IFactory, name=portlet_type)
            if not portlet_factory:
                logger.info(u"No factory for portlet {}".format(portlet_type))
                continue

            assignment = portlet_factory()

            name = namechooser.chooseName(None, assignment)
            mapping[name] = assignment

            # aq-wrap it so that complex fields will work
            assignment = assignment.__of__(site)

            # set visibility setting
            visible = portlet_data.get("visible")
            if visible is not None:
                settings = IPortletAssignmentSettings(assignment)
                settings["visible"] = visible

            # 2. Apply portlet settings
            portlet_interface = getUtility(IPortletTypeInterface, name=portlet_type)
            for property_name, value in assignment_data.items():
                field = portlet_interface.get(property_name, None)
                if field is None:
                    continue
                field = field.bind(assignment)
                # deserialize data (e.g. for RichText)
                deserializer = queryMultiAdapter(
                    (field, obj, request), IFieldDeserializer
                )
                if deserializer is not None:
                    try:
                        value = deserializer(value)
                    except Exception as e:
                        logger.info(
                            u"Could not import portlet data {} for field {} on {}: {}".format(
                                value, field, obj.absolute_url(), str(e)
                            )
                        )
                        continue
                field.set(assignment, value)

            logger.info(
                u"Added {} '{}' to {} of {}".format(
                    portlet_type, name, manager_name, obj.absolute_url()
                )
            )
            results += 1

    for blacklist_status in item.get("blacklist_status", []):
        status = blacklist_status["status"]
        manager_name = blacklist_status["manager"]
        category = blacklist_status["category"]
        manager = queryUtility(IPortletManager, manager_name)
        if not manager:
            logger.info("No portlet manager {}".format(manager_name))
            continue
        assignable = queryMultiAdapter((obj, manager), ILocalPortletAssignmentManager)
        if status.lower() == "block":
            assignable.setBlacklistStatus(category, True)
        elif status.lower() == "show":
            assignable.setBlacklistStatus(category, False)

    return results


def import_plone_redirects(jsondata):
    storage = getUtility(IRedirectionStorage)

    for key, value in jsondata.items():
        storage.add(key, value)


class ImportRedirects(BrowserView):
    """Import redirects"""

    def __call__(self, jsonfile=None, return_json=False):
        if jsonfile:
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
                import_plone_redirects(data)
                msg = u"Redirects imported"
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()
