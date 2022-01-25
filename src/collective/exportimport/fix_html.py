# -*- coding: UTF-8 -*-
from Acquisition import aq_parent
from bs4 import BeautifulSoup
from collections import defaultdict
from logging import getLogger
from plone import api
from plone.app.portlets.interfaces import IPortletTypeInterface
from plone.app.textfield import RichTextValue
from plone.app.textfield.interfaces import IRichText
from plone.app.textfield.value import IRichTextValue
from plone.dexterity.utils import iterSchemataForType
from plone.portlets.interfaces import IPortletAssignmentMapping
from plone.portlets.interfaces import IPortletManager
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import IContentish
from Products.Five import BrowserView
from six.moves.urllib.parse import urlparse
from six.moves.urllib.parse import urlunparse
from zope.component import getUtilitiesFor
from zope.component import queryMultiAdapter
from zope.interface import providedBy

import six
import transaction

logger = getLogger(__name__)

IMAGE_SCALE_MAP = {
    "icon": "icon",
    "large": "large",
    "listing": "listing",
    "mini": "mini",
    "preview": "preview",
    "thumb": "thumb",
    "tile": "tile",
}


class FixHTML(BrowserView):
    def __call__(self):
        self.title = "Fix links to content and images in richtext"
        if not self.request.form.get("form.submitted", False):
            return self.index()
        commit = self.request.form.get("form.commit", True)

        msg = []

        fix_count = fix_html_in_content_fields(commit=commit)
        msg.append(u"Fixed HTML for {} fields in content items".format(fix_count))
        logger.info(msg[-1])

        fix_count = fix_html_in_portlets()
        msg.append(u"Fixed HTML for {} portlets".format(fix_count))
        logger.info(msg[-1])

        # TODO: Fix html in tiles
        # tiles = fix_html_in_tiles()
        # msg = u"Fixed html for {} tiles".format(tiles)

        api.portal.show_message(u" ".join(m + u"." for m in msg), self.request)
        return self.index()


def html_fixer(text, obj=None, old_portal_url=None):
    # Fix issues with migrated html
    #
    # 1. Fix image scales from old to new types
    # 2. Add data-attributes to internal links and images fix editing in TinyMCE
    if not text:
        return

    portal = api.portal.get()
    portal_url = portal.absolute_url()
    if old_portal_url is None:
        old_portal_url = portal_url

    soup = BeautifulSoup(text, "html.parser")
    for tag, attr in [
        (tag, attr)
        for attr, tags in [
            ("href", ["a"]),
            ("src", ["source", "img", "video", "audio", "iframe"]),
            ("srcset", ["source", "img"]),
        ]
        for tag in tags
    ]:
        fix_tag_attr(soup, tag, attr, old_portal_url, obj=obj)

    return soup.decode()


def fix_tag_attr(soup, tag, attr, old_portal_url, obj=None):
    """Fix the attribute every matching tag passed within the soup."""
    for content_link in soup.find_all(tag):
        origlink = content_link.get(attr)
        if not origlink:
            # Ignore tags without attr
            continue
        orig = content_link.decode()  # to compare

        if attr == "srcset":
            links = [x.split(maxsplit=1)[0] for x in origlink.split(",")]
            addenda = [x.split(maxsplit=1)[1:] for x in origlink.split(",")]
        else:
            links = [origlink]
            addenda = [[]]
        if not links:
            # Ignore tags with no usable content
            continue

        for n, link in enumerate(links):
            uuid = None
            parsed_link = urlparse(link)
            if parsed_link.scheme in ["mailto", "file"]:
                continue

            if parsed_link.netloc and parsed_link.netloc not in old_portal_url:
                # skip external url
                continue

            path = parsed_link.path
            if not path:
                # link to anchor only?
                continue

            # remove trailing /view
            if path.endswith("/view"):
                path = path[:-5]

            # get uuid from link with resolveuid
            components = path.split("/")
            if "resolveuid" in components:
                uuid = components[components.index("resolveuid") + 1]

            # update image scaling and traversal
            if tag == "img":
                for old, new in IMAGE_SCALE_MAP.items():
                    # replace plone.app.imaging old scale names with new ones
                    path = path.replace(
                        "/@@images/image/{old}".format(old=old),
                        "/@@images/image/{new}".format(new=new),
                    )
                    # replace old AT traversing scales
                    path = path.replace(
                        "/image_{old}".format(old=old),
                        "/@@images/image/{new}".format(new=new),
                    )

                scaled = False
                if "/@@images/" in path:
                    scale = path.split("/@@images/image")[-1]
                    if scale and scale.startswith("/"):
                        scale = scale[1:]
                        if attr == "src":
                            # Different srcset items can have different scales.
                            content_link["data-scale"] = scale
                        path = path.split("/@@images/")[0]
                        scaled = True

            # get uuid from path
            if not uuid:
                target = find_object(obj, path)
                if not target:
                    logger.debug("Cannot find target obj for {path}".format(path=path))
                    continue
                uuid = IUUID(target, None)

            if not uuid:
                logger.debug("Cannot find target obj for {link}".format(link=link))
                continue

            # construct new link
            if tag == "img":
                if scaled:
                    new_href = "resolveuid/{uuid}/@@images/image/{scale}".format(
                        uuid=uuid, scale=scale
                    )
                    if attr == "src":
                        content_link["data-scale"] = scale
                else:
                    new_href = "resolveuid/{uuid}/@@images/image".format(uuid=uuid)
                    if attr == "src":
                        content_link["data-scale"] = ""
            else:
                new_href = "resolveuid/{uuid}".format(uuid=uuid)
                if parsed_link.fragment:
                    new_href += "#" + parsed_link.fragment
                if attr != "srcset":
                    content_link["data-linktype"] = "internal"
                    content_link["data-val"] = uuid

            if tag == "img":
                # data-attrs for tinymce pattern
                if attr == "src":
                    # Different srcset items can have different UUIDs.
                    content_link["data-val"] = uuid
                content_link["data-linktype"] = "image"
                iklass = content_link.get("class")
                if not iklass:
                    content_link["class"] = ["image-richtext", "image-inline"]
                else:
                    image_aligns = {
                        "image-right",
                        "image-left",
                        "image-responsive",
                        "image-inline",
                    }
                    if image_aligns.isdisjoint(set(iklass)):
                        # No image-align class is set, so we defaul to inline.
                        iklass.append("image-inline")
                    if "image-richtext" not in iklass:
                        iklass.append("image-richtext")

            links[n] = new_href

        content_link[attr] = ",".join(
            " ".join([link] + addendum)
            for link, addendum in zip(links, addenda)
        )

        if orig != content_link.decode():
            logger.debug(
                "Changed {tag} {attr} from {orig} to {content_link}".format(
                    tag=tag, attr=attr, orig=orig, content_link=content_link
                )
            )


def find_object(base, path):
    """Find a link target based ob a absolute or relative path.
    When the target in the link is no content leave the link as is.
    It might be a link to a browser-view, form or script...
    """
    if six.PY2 and isinstance(path, six.text_type):
        path = path.encode("utf-8")
    if path.startswith("/"):
        # Make an absolute path relative to the portal root
        obj = api.portal.get()
        portal_path = obj.absolute_url_path() + "/"
        if path.startswith(portal_path):
            path = path[len(portal_path) :]
    else:
        obj = aq_parent(base)  # relative urls start at the parent...

    try:
        target = obj.unrestrictedTraverse(path)
    except:
        return
    if IContentish.providedBy(target):
        return target


def find_object(base, path):
    """Find a link target based ob a absolute or relative path.
    When the target in the link is no content leave the link as is.
    It might be a link to a browser-view, form or script...
    """
    if six.PY2 and isinstance(path, six.text_type):
        path = path.encode('utf-8')
    if path.startswith('/'):
        # Make an absolute path relative to the portal root
        obj = api.portal.get()
        portal_path = obj.absolute_url_path() + '/'
        if path.startswith(portal_path):
            path = path[len(portal_path):]
    else:
        obj = aq_parent(base)   # relative urls start at the parent...

    try:
        target = obj.unrestrictedTraverse(path)
    except:
        return
    if IContentish.providedBy(target):
        return target


def fix_html_in_content_fields(context=None, commit=True):
    """Run this in Plone 5.x"""
    catalog = api.portal.get_tool("portal_catalog")
    portal_types = api.portal.get_tool("portal_types")

    types_with_richtext_fields = defaultdict(list)
    for portal_type in portal_types.keys():
        for schema in iterSchemataForType(portal_type):
            for fieldname, field in schema.namesAndDescriptions():
                if IRichText.providedBy(field):
                    types_with_richtext_fields[portal_type].append(fieldname)
    query = {}
    query["portal_type"] = list(types_with_richtext_fields.keys())
    query["sort_on"] = "path"

    brains = catalog(**query)
    total = len(brains)
    logger.info(
        "There are {} content items in total, starting migration...".format(len(brains))
    )
    results = 0
    results_to_commit = 0
    items_to_commit = 0
    for index, brain in enumerate(brains, start=1):
        try:
            obj = brain.getObject()
        except Exception:
            logger.warning(
                "Not possible to fetch object from catalog result for "
                "item: {}.".format(brain.getPath())
            )
            continue

        _p = results_to_commit
        for fieldname in types_with_richtext_fields[obj.portal_type]:
            text = getattr(obj.aq_base, fieldname, None)
            if text and IRichTextValue.providedBy(text) and text.raw:
                logger.debug("Checking {}".format(obj.absolute_url()))
                clean_text = html_fixer(text.raw, obj)
                if clean_text and clean_text != text.raw:
                    textvalue = RichTextValue(
                        raw=clean_text,
                        mimeType=text.mimeType,
                        outputMimeType=text.outputMimeType,
                        encoding=text.encoding,
                    )
                    setattr(obj, fieldname, textvalue)
                    obj.reindexObject(idxs=("SearchableText",))
                    logger.debug(
                        "Fixed html for field {} of {}".format(
                            fieldname, obj.absolute_url()
                        )
                    )
                    results += 1
                    results_to_commit += 1
        if _p != results_to_commit:
            items_to_commit += 1

        if results_to_commit >= 1000:
            # Commit every 1000 changes.
            msg = u"Fix html for {} ({}%) of {} items ({} changed fields)".format(items_to_commit, round(items_to_commit / total * 100, 2), total, results)
            logger.info(msg)
            if commit:
                transaction.get().note(msg)
                transaction.commit()
            results_to_commit = 0
            items_to_commit = 0

    if results_to_commit > 0:
        # Commit any remaining changes.
        msg = u"Fix html for {} ({}%) of {} items ({} changed fields)".format(items_to_commit, round(items_to_commit / total * 100, 2), total, results)
        logger.info(msg)
        if commit:
            transaction.get().note(msg)
            transaction.commit()

    return results


def fix_html_in_portlets(context=None):

    portlets_schemata = {
        iface: name for name, iface in getUtilitiesFor(IPortletTypeInterface)
    }

    def get_portlets(obj, path, fix_count_ref):
        for manager_name, manager in getUtilitiesFor(IPortletManager):
            mapping = queryMultiAdapter((obj, manager), IPortletAssignmentMapping)
            if mapping is None or not mapping.items():
                continue
            mapping = mapping.__of__(obj)
            for name, assignment in mapping.items():
                portlet_type = None
                schema = None
                for schema in providedBy(assignment).flattened():
                    portlet_type = portlets_schemata.get(schema, None)
                    if portlet_type is not None:
                        break
                assignment = assignment.__of__(mapping)
                for fieldname, field in schema.namesAndDescriptions():
                    if IRichText.providedBy(field):
                        text = getattr(assignment, fieldname, None)
                        if text and IRichTextValue.providedBy(text) and text.raw:
                            clean_text = html_fixer(text.raw, obj)
                            if clean_text and clean_text != text.raw:
                                textvalue = RichTextValue(
                                    raw=clean_text,
                                    mimeType=text.mimeType,
                                    outputMimeType=text.outputMimeType,
                                    encoding=text.encoding,
                                )
                                fix_count_ref.append(True)
                                setattr(assignment, fieldname, textvalue)
                                logger.info(
                                    "Fixed html for field {} of portlet at {}".format(
                                        fieldname, obj.absolute_url()
                                    )
                                )
                        elif text and isinstance(text, str):
                            clean_text = html_fixer(text, obj)
                            if clean_text and clean_text != text:
                                textvalue = RichTextValue(
                                    raw=clean_text,
                                    mimeType="text/html",
                                    outputMimeType="text/x-html-safe",
                                    encoding="utf-8",
                                )
                                fix_count_ref.append(True)
                                setattr(assignment, fieldname, textvalue)
                                logger.info(
                                    "Fixed html for field {} of portlet {} at {}".format(
                                        fieldname, str(assignment), obj.absolute_url()
                                    )
                                )

    portal = api.portal.get()
    fix_count = []
    f = lambda obj, path: get_portlets(obj, path, fix_count)
    portal.ZopeFindAndApply(portal, search_sub=True, apply_func=f)
    return len(fix_count)
