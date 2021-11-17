# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
from collections import defaultdict
from logging import getLogger
from plone import api
from plone.app.linkintegrity.handlers import findObject
from plone.app.portlets.interfaces import IPortletTypeInterface
from plone.app.textfield import RichTextValue
from plone.app.textfield.interfaces import IRichText
from plone.app.textfield.value import IRichTextValue
from plone.dexterity.utils import iterSchemataForType
from plone.portlets.interfaces import IPortletAssignmentMapping
from plone.portlets.interfaces import IPortletManager
from plone.uuid.interfaces import IUUID
from Products.Five import BrowserView
from six.moves.urllib.parse import urlparse
from zope.component import getUtilitiesFor
from zope.component import queryMultiAdapter
from zope.interface import providedBy

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
        self.title = 'Fix links to content and images in richtext'
        if not self.request.form.get("form.submitted", False):
            return self.index()

        content = fix_html_in_content_fields()
        msg = u"Fixed html for {} content items".format(content)
        logger.info(msg)

        fix_html_in_portlets()
        msg = u"Fixed html for portlets"
        logger.info(msg)

        # TODO: Fix html in tiles
        # tiles = fix_html_in_tiles()
        # msg = u"Fixed html for {} tiles".format(tiles)

        logger.info("committing...")
        msg = u"Fixed html"
        api.portal.show_message(msg, self.request)
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
    for content_link in soup.find_all("a"):
        orig = content_link.decode()  # to compare
        link = content_link.get("href")
        if not link:
            # Ignore <a>-tags without href
            continue

        uuid = None
        parsed_link = urlparse(link)
        if parsed_link.scheme in ["mailto", "file"]:
            continue

        if parsed_link.netloc and parsed_link.netloc not in old_portal_url:
            # skip external url
            continue

        path = parsed_link.path
        if not path:
            # link to ancor only?
            continue

        # remove trailing /view
        if path.endswith('/view'):
            path = path[:-5]

        # get uuid from link with resolveuid
        components = path.split('/')
        if 'resolveuid' in components:
            uuid = components[components.index('resolveuid') + 1]

        # get uuid from path
        if not uuid:
            target, extra = findObject(obj, path)
            if not target:
                logger.debug("Cannot find target obj for {path}".format(path=path))
                continue
            uuid = IUUID(target, None)

        if not uuid:
            logger.debug("Cannot find target obj for {link}".format(link=link))
            continue

        # construct new link from uuid
        new_href = "resolveuid/{uuid}".format(uuid=uuid)
        if parsed_link.fragment:
            new_href += "#" + parsed_link.fragment

        content_link["href"] = new_href
        content_link["data-linktype"] = "internal"
        content_link["data-val"] = uuid
        if orig != content_link.decode():
            logger.debug(
                "Changed link from \n{orig} \n to \n{content_link}".format(
                    orig=orig, content_link=content_link
                )
            )

    for img_link in soup.find_all("img"):
        orig = img_link.decode()
        link = img_link.get("src")
        if not link:
            # Ignore <img>-tags without src
            continue

        uuid = None
        parsed_link = urlparse(link)
        if parsed_link.scheme in ["mailto", "file", ]:
            continue

        path = parsed_link.path

        # get uuid from link with resolveuid
        components = path.split('/')
        if 'resolveuid' in components:
            uuid = components[components.index('resolveuid') + 1]

        # update image scaling and traversal
        for old, new in IMAGE_SCALE_MAP.items():
            # replace plone.app.imaging old scale names with new ones
            path = path.replace(
                "/@@images/image/{old}".format(old=old),
                "/@@images/image/{new}".format(new=new),
            )
            # replace old AT traversing scales
            path = path.replace(
                "/image_{old}".format(old=old), "/@@images/image/{new}".format(new=new)
            )

        scaled = False
        if "/@@images/" in path:
            scale = path.split("/@@images/image")[-1]
            if scale and scale.startswith("/"):
                scale = scale[1:]
                img_link["data-scale"] = scale
                path = path.split("/@@images/")[0]
                scaled = True

        # get uuid from path
        if not uuid:
            target, extra = findObject(obj, path)
            uuid = IUUID(target, None)

        if not uuid:
            logger.debug("Cannot find target obj for {path}".format(path=path))
            continue

        # construct new link
        if scaled:
            new_src = "resolveuid/{uuid}/@@images/image/{scale}".format(
                uuid=uuid, scale=scale
            )
            img_link["data-scale"] = scale
        else:
            new_src = "resolveuid/{uuid}/@@images/image".format(uuid=uuid)
            img_link["data-scale"] = ""

        img_link["src"] = new_src

        # data-attrs for tinymce pattern
        img_link["data-val"] = uuid
        img_link["data-linktype"] = "image"
        iklass = img_link.get("class")
        if not iklass:
            img_link["class"] = ["image-richtext", "image-inline"]
        else:
            image_aligns = {
                'image-right',
                'image-left',
                'image-responsive',
                'image-inline',
            }
            if image_aligns.isdisjoint(set(iklass)):
                # No image-align class is set, so we defaul to inline.
                iklass.append("image-inline")
            if "image-richtext" not in iklass:
                iklass.append("image-richtext")
        if orig != img_link.decode():
            logger.debug(
                "Change img from {orig} to {img_link}".format(
                    orig=orig, img_link=img_link
                )
            )

    return soup.decode()


def fix_html_in_content_fields(context=None):
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
    logger.info("There are {} content items in total, starting migration...".format(len(brains)))
    results = 0
    for index, brain in enumerate(brains, start=1):
        try:
            obj = brain.getObject()
        except Exception:
            logger.warning(
                "Not possible to fetch object from catalog result for "
                "item: {}.".format(brain.getPath())
            )
            continue

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
                    logger.debug("Fixed html for field {} of {}".format(fieldname, obj.absolute_url()))
                    results += 1

        if not index % 1000:
            msg = u"Fix html for {} ({}%) of {} items ({} changed fields)".format(index, round(index / total * 100, 2), total, results)
            logger.info(msg)
            transaction.get().note(msg)
            transaction.commit()
    return results


def fix_html_in_portlets(context=None):

    portlets_schemata = {
        iface: name for name, iface in getUtilitiesFor(IPortletTypeInterface)
    }

    def get_portlets(obj, path):
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
                                setattr(assignment, fieldname, textvalue)
                                logger.info("Fixed html for field {} of portlet at {}".format(
                                    fieldname, obj.absolute_url()))
                        elif text and isinstance(text, str):
                            clean_text = html_fixer(text, obj)
                            if clean_text and clean_text != text:
                                textvalue = RichTextValue(
                                    raw=clean_text,
                                    mimeType='text/html',
                                    outputMimeType='text/x-html-safe',
                                    encoding='utf-8',
                                )
                                setattr(assignment, fieldname, textvalue)
                                logger.info("Fixed html for field {} of portlet {} at {}".format(
                                    fieldname, str(assignment), obj.absolute_url()))

    portal = api.portal.get()
    portal.ZopeFindAndApply(portal, search_sub=True, apply_func=get_portlets)
