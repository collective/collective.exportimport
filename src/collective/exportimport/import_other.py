# -*- coding: utf-8 -*-
from datetime import datetime
from OFS.interfaces import IOrderedContainer
from operator import itemgetter
from plone import api
from Products.Five import BrowserView
from ZPublisher.HTTPRequest import FileUpload

import json
import logging
import transaction

try:
    from collective.relationhelpers import api as relapi

    HAS_RELAPI = True
except ImportError:
    HAS_RELAPI = False

try:
    from plone.app.multilingual.interfaces import ITranslationManager

    HAS_PAM = True
except ImportError:
    HAS_PAM = False

logger = logging.getLogger(__name__)


if HAS_PAM:

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
                        u"Fehler beim Dateiuplad: {}".format(e),
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
                    u"Fehler beim Dateiuplad: {}".format(e),
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
            pr.addMember(username, password, roles, [], item)
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

        if not HAS_RELAPI:
            api.portal.show_message(
                "collective.relationhelpers is not available", self.request
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
                msg = u"Fehler beim Dateiuplad: {}".format(e)
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
        relapi.purge_relations()
        relapi.cleanup_intids()
        relapi.restore_relations(all_relations=all_fixed_relations)

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
                    u"Fehler beim Dateiuplad: {}".format(e),
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
        for item in data:
            obj = api.content.get(UID=item["uuid"])
            if not obj:
                continue
            localroles = item["localroles"]
            for userid in localroles:
                obj.manage_setLocalRoles(userid=userid, roles=localroles[userid])
            logger.info(u"Set roles on {}: {}".format(obj.absolute_url(), localroles))
            results += 1
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
                    u"Fehler beim Dateiuplad: {}".format(e),
                    request=self.request,
                )
            else:
                orders = self.import_ordering(data)
                msg = u"Imported {} orders".format(orders)
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_ordering(self, data):
        results = 0
        for item in data:
            obj = api.content.get(UID=item["uuid"])
            if not obj:
                continue
            ordered = IOrderedContainer(obj.__parent__, None)
            if not ordered:
                continue
            ordered.moveObjectToPosition(obj.getId(), item["order"])
            results += 1
        return results


class ImportDefaultPages(BrowserView):
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
                    u"Fehler beim Dateiuplad: {}".format(e),
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
                continue
            old = obj.getDefaultPage()
            obj.setDefaultPage(item["default_page"])
            if old != obj.getDefaultPage():
                results += 1
        return results
