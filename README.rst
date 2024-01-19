.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on pypi or github. It is a comment.

.. image:: https://img.shields.io/pypi/v/collective.exportimport.svg
    :target: https://pypi.python.org/pypi/collective.exportimport/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/status/collective.exportimport.svg
    :target: https://pypi.python.org/pypi/collective.exportimport
    :alt: Egg Status

.. image:: https://img.shields.io/pypi/pyversions/collective.exportimport.svg?style=plastic   :alt: Supported - Python Versions

.. image:: https://img.shields.io/pypi/l/collective.exportimport.svg
    :target: https://pypi.python.org/pypi/collective.exportimport/
    :alt: License


=======================
collective.exportimport
=======================

Export and import content, members, relations, translations, localroles and much more.

Export and import all kinds of data from and to Plone sites using a intermediate json-format.
The main use-case is migrations since it enables you to for example migrate from Plone 4 with Archetypes and Python 2 to Plone 6 with Dexterity and Python 3 in one step.
Most features use `plone.restapi` to serialize and deserialize data.

See also the training on migrating with ``exportimport``: https://training.plone.org/migrations/exportimport.html

.. contents:: Contents
    :local:

Features
========

* Export & Import content
* Export & Import members and groups with their roles
* Export & Import relations
* Export & Import translations
* Export & Import local roles
* Export & Import order (position in parent)
* Export & Import discussions/comments
* Export & Import versioned content
* Export & Import redirects

Export supports:

* Plone 4, 5 and 6
* Archetypes and Dexterity
* Python 2 and 3
* plone.app.multilingual, Products.LinguaPlone, raptus.multilanguagefields

Import supports:

* Plone 5.2+, Dexterity, Python 2 and 3, plone.app.multilingual


Installation
============

Install collective.exportimport as you would install any other Python package.

You don't need to activate the add-on in the Site Setup Add-ons control panel to be able to use the forms ``@@export_content`` and ``@@import_content`` in your site.

If you need help, see:
- for Plone 4: https://4.docs.plone.org/adapt-and-extend/install_add_ons.html
- for Plone 5: https://5.docs.plone.org/manage/installing/installing_addons.html
- for Plone 6: https://6.docs.plone.org/install/manage-add-ons-packages.html


Python 2 compatibility
----------------------

This package is compatible with Python 3 and Python 2.
Depending on the Python version different versions of it's dependencies will be installed.
If you run into problems, file an issue at: https://github.com/collective/collective.exportimport/issues


Usage
=====

Export
------

Use the form with the URL ``/@@export_content``, and select what you want to export:

.. image:: ./docs/export.png

You can export one or more types and a whole site or only a specific path in a site. Since items are exported ordered by path importing them will create the same structure as you had originally.

The downloaded json-file will have the name of the path you exported from, e.g. ``Plone.json``.

The exports for members, relations, localroles and relations are linked to in this form but can also be called individually: ``/@@export_members``, ``/@@export_relations``, ``/@@export_localroles``, ``/@@export_translations``, ``/@@export_ordering``, ``/@@export_discussion``.


Import
------

Use the form with the URL ``/@@import_content``, and upload a json-file that you want to import:

.. image:: ./docs/import.png


The imports for members, relations, localroles and relations are linked to in this form but can also be called individually: ``/@@import_members``, ``/@@import_relations``, ``/@@import_localroles``, ``/@@import_translations``, ``/@@import_ordering``, ``/@@import_discussion``.

As a last step in a migration there is another view ``@@reset_dates`` that resets the modified date on imported content to the date initially contained in the imported json-file. This is necessary since varous changes during a migration will likely result in a updated modified-date. During import the original is stored as ``obj.modification_date_migrated`` on each new object and this view sets this date.

Export- and import locations
----------------------------

If you select 'Save to file on server', the Export view will save json files in the <var> directory of your Plone instanc in /var/instance.
The import view will look for  files under /var/instance/import.
These directories will normally be different, under different Plone instances and possibly on different servers.

You can set the environment variable 'COLLECTIVE_EXPORTIMPORT_CENTRAL_DIRECTORY' to add a 'shared' directory on one server or maybe network share.
With this variable set, collective.exportimport will both save to and load .json files from the same server directory.
This saves time not having to move .json files around from the export- to the import location.
You should be aware that the Export views will overwrite any existing previous .json file export that have the same name.


Use-cases
=========

Migrations
----------

When a in-place-migration is not required you can choose this addon to migrate the most important parts of your site to json and then import it into a new Plone instance of your targeted version:

* Export content from a Plone site (it supports Plone 4 and 5, Archetypes and Dexterity, Python 2 and 3).
* Import the exported content into a new site (Plone 5.2+, Dexterity, Python 3)
* Export and import relations, users and groups with their roles, translations, local roles, ordering, default-pages, comments, portlets and redirects.

How to migrate additional features like Annotations or Marker Interfaces is discussed in the FAQ section.

Other
-----

You can use this addon to

* Archive your content as json
* Export data to prepare a migration to another system
* Combine content from multiple plone-sites into one.
* Import a plone-site as a subsite into another.
* Import content from other systems as long as it fits the required format.
* Update or replace existing data
* ...

Details
=======

Export content
--------------

Exporting content is basically a wrapper for the serializers of plone.restapi:

.. code-block:: python

    from plone.restapi.interfaces import ISerializeToJson
    from zope.component import getMultiAdapter

    serializer = getMultiAdapter((obj, request), ISerializeToJson)
    data = serializer(include_items=False)

Import content
--------------

Importing content is a elaborate wrapper for the deserializers of plone.restapi:

.. code-block:: python

    from plone.restapi.interfaces import IDeserializeFromJson
    from zope.component import getMultiAdapter

    container.invokeFactory(item['@type'], item['id'])
    deserializer = getMultiAdapter((new, self.request), IDeserializeFromJson)
    new = deserializer(validate_all=False, data=item)


Use for migrations
------------------

A main use-case of this package is migration from one Plone-Version to another.

Exporting Archetypes content and importing that as Dexterity content works fine but due to changes in field-names some settings would get lost.
For example the setting to exclude content from the navigation was renamed from ``excludeFromNav`` to ``exclude_from_nav``.

To fix this you can check the checkbox "Modify exported data for migrations".
This will modify the data during export:

* Drop unused data (e.g. `next_item` and `components`)
* Remove all relation fields
* Change some field names that changed between Archetypes and Dexterity

  * ``excludeFromNav`` → ``exclude_from_nav``
  * ``allowDiscussion`` → ``allow_discussion``
  * ``subject`` → ``subjects``
  * ``expirationDate`` → ``expires``
  * ``effectiveDate`` → ``effective``
  * ``creation_date`` → ``created``
  * ``modification_date`` → ``modified``
  * ``startDate`` → ``start``
  * ``endDate`` → ``end``
  * ``openEnd`` → ``open_end``
  * ``wholeDay`` → ``whole_day``
  * ``contactEmail`` → ``contact_email``
  * ``contactName`` → ``contact_name``
  * ``contactPhone`` → ``contact_phone``

* Update view names on Folders and Collection that changed since Plone 4.
* Export ``ATTopic`` and their criteria to Collections with querystrings.
* Update Collection-criteria.
* Links and images in Richtext-Fields of content and portlets have changes since Plone 4.
  the view ``/@@fix_html`` allows you to fix these.


Control creating imported content
---------------------------------

You can choose between four options how to deal with content that already exists:

  * Skip: Don't import at all
  * Replace: Delete item and create new
  * Update: Reuse and only overwrite imported data
  * Ignore: Create with a new id

Imported content is initially created with ``invokeFactory`` using portal_type and id of the exported item before deserializing the rest of the data.
You can set additional values by specifying a dict ``factory_kwargs`` that will be passed to the factory.
Like this you can set values on the imported object that are expected to be there by subscribers to IObjectAddedEvent.


Export versioned content
------------------------

Exporting versions of Archetypes content will not work because of a bug in plone.restapi (https://github.com/plone/plone.restapi/issues/1335).
For export to work you need to use a version between 7.7.0 and 8.0.0 (if released) or a source-checkout of the branch 7.x.x.


Notes on speed and large migrations
===================================

Exporting and importing large amounts of content can take a while. Export is pretty fast but import is constrained by some features of Plone, most importantly versioning:

* Importing 5000 Folders takes ~5 minutes
* Importing 5000 Documents takes >25 minutes because of versioning.
* Importing 5000 Documents without versioning takes ~7 minutes.

During import you can commit every x number of items which will free up memory and disk-space in your TMPDIR (where blobs are added before each commit).

When exporting large numbers of blobs (binary files and images) you will get huge json-files and may run out of memory.
You have various options to deal with this.
The best way depends on how you are going to import the blobs:

- Export as download urls: small download, but ``collective.exportimport`` cannot import the blobs, so you will need an own import script to download them.
- Export as base-64 encoded strings: large download, but ``collective.exportimport`` can handle the import.
- Export as blob paths: small download and ``collective.exportimport`` can handle the import, but you need to copy ``var/blobstorage`` to the Plone Site where you do the import or set the environment variable ``COLLECTIVE_EXPORTIMPORT_BLOB_HOME`` to the old blobstorage path: ``export COLLECTIVE_EXPORTIMPORT_BLOB_HOME=/path-to-old-instance/var/blobstorage``.
  To export the blob-path you do not need to have access to the blobs!


Format of export and import of content
======================================

By default all content is exported to and imported from one large json-file.
To inspect such very large json-files without performance-issues you can use klogg (https://klogg.filimonov.dev).

Since version 1.10 collective.exportimport also supports exporting and importing each content item as a separate json-file.
To use that select *Save each item as a separate file on the server* in the form or specify ``download_to_server=2`` when calling the export in python.
In the import-form you can manually select a directory on the server or specify ``server_directory="/mydir"`` when calling the import in python.


Customize export and import
===========================

This addon is designed to be adapted to your requirements and has multiple hooks to make that easy.

To make that easier here are packages you can reuse to override and extend the export and import.
Use these templates and adapt them to your own projects:

* https://github.com/starzel/contentexport
* https://github.com/starzel/contentimport

Many examples for customizing the export and import are collected in the chapter "FAQ, Tips and Tricks" below.

.. note::

    As a rule of thumb you should make changes to the data during import unless you need access to the original object for the required changes.
    One reason is that this way the serialized content in the json-file more closely represents the original data.
    Another reason is that it allows you to fix issues during the process you are currently developing (i.e. without having to redo the export).


Export Example
--------------

.. code-block:: python

    from collective.exportimport.export_content import ExportContent

    class CustomExportContent(ExportContent):

        QUERY = {
            'Document': {'review_state': ['published', 'pending']},
        }

        DROP_PATHS = [
            '/Plone/userportal',
            '/Plone/en/obsolete_content',
        ]

        DROP_UIDS = [
            '71e3e0a6f06942fea36536fbed0f6c42',
        ]

        def update(self):
            """Use this to override stuff before the export starts
            (e.g. force a specific language in the request)."""

        def start(self):
            """Hook to do something before export."""

        def finish(self):
            """Hook to do something after export."""

        def global_obj_hook(self, obj):
            """Inspect the content item before serialisation data.
            Bad: Changing the content-item is a horrible idea.
            Good: Return None if you want to skip this particular object.
            """
            return obj

        def global_dict_hook(self, item, obj):
            """Use this to modify or skip the serialized data.
            Return None if you want to skip this particular object.
            """
            return item

        def dict_hook_document(self, item, obj):
            """Use this to modify or skip the serialized data by type.
            Return the modified dict (item) or None if you want to skip this particular object.
            """
            return item


Register it with your own browserlayer to override the default:

.. code-block:: xml

  <browser:page
      name="export_content"
      for="zope.interface.Interface"
      class=".custom_export.CustomExportContent"
      layer="My.Custom.IBrowserlayer"
      permission="cmf.ManagePortal"
      />


Import Example
--------------

.. code-block:: python

    from collective.exportimport.import_content import ImportContent

    class CustomImportContent(ImportContent):

        CONTAINER = {'Event': '/imported-events'}

        # These fields will be ignored
        DROP_FIELDS = ['relatedItems']

        # Items with these uid will be ignored
        DROP_UIDS = ['04d1477583c74552a7fcd81a9085c620']

        # These paths will be ignored
        DROP_PATHS = ['/Plone/doormat/', '/Plone/import_files/']

        # Default values for some fields
        DEFAULTS = {'which_price': 'normal'}

        def start(self):
            """Hook to do something before importing one file."""

        def finish(self):
            """Hook to do something after importing one file."""

        def global_dict_hook(self, item):
            if isinstance(item.get('description', None), dict):
                item['description'] = item['description']['data']
            if isinstance(item.get('rights', None), dict):
                item['rights'] = item['rights']['data']
            return item

        def dict_hook_customtype(self, item):
            # change the type
            item['@type'] = 'anothertype'
            # drop a field
            item.pop('experiences', None)
            return item

        def handle_file_container(self, item):
            """Use this to specify the container in which to create the item in.
            Return the container for this particular object.
            """
            return self.portal['imported_files']

Register it:

.. code-block:: xml

  <browser:page
      name="import_content"
      for="zope.interface.Interface"
      class=".custom_import.CustomImportContent"
      layer="My.Custom.IBrowserlayer"
      permission="cmf.ManagePortal"
      />


Automate export and import
--------------------------

Run all exports and save all data in ``var/instance/``:

.. code-block:: python

    from plone import api
    from Products.Five import BrowserView

    class ExportAll(BrowserView):

        def __call__(self):
            export_content = api.content.get_view("export_content", self.context, self.request)
            self.request.form["form.submitted"] = True
            export_content(
                portal_type=["Folder", "Document", "News Item", "File", "Image"],  # only export these
                include_blobs=2,  # Export files and images as blob paths
                download_to_server=True)

            other_exports = [
                "export_relations",
                "export_members",
                "export_translations",
                "export_localroles",
                "export_ordering",
                "export_defaultpages",
                "export_discussion",
                "export_portlets",
                "export_redirects",
            ]
            for name in other_exports:
                view = api.content.get_view(name, portal, request)
                # This saves each export in var/instance/export_xxx.json
                view(download_to_server=True)

            # Important! Redirect to prevent infinite export loop :)
            return self.request.response.redirect(self.context.absolute_url())

Run all imports using the data exported in the example above:

.. code-block:: python

    from collective.exportimport.fix_html import fix_html_in_content_fields
    from collective.exportimport.fix_html import fix_html_in_portlets
    from pathlib import Path
    from plone import api
    from Products.Five import BrowserView


    class ImportAll(BrowserView):

        def __call__(self):
            portal = api.portal.get()

            # Import content
            view = api.content.get_view("import_content", portal, request)
            request.form["form.submitted"] = True
            request.form["commit"] = 500
            view(server_file="Plone.json", return_json=True)
            transaction.commit()

            # Run all other imports
            other_imports = [
                "relations",
                "members",
                "translations",
                "localroles",
                "ordering",
                "defaultpages",
                "discussion",
                "portlets",
                "redirects",
            ]
            cfg = getConfiguration()
            directory = Path(cfg.clienthome) / "import"
            for name in other_imports:
                view = api.content.get_view(f"import_{name}", portal, request)
                path = Path(directory) / f"export_{name}.json"
                results = view(jsonfile=path.read_text(), return_json=True)
                logger.info(results)
                transaction.commit()

            # Run cleanup steps
            results = fix_html_in_content_fields()
            logger.info("Fixed html for %s content items", results)
            transaction.commit()

            results = fix_html_in_portlets()
            logger.info("Fixed html for %s portlets", results)
            transaction.commit()

            reset_dates = api.content.get_view("reset_dates", portal, request)
            reset_dates()
            transaction.commit()

.. note::

    The views ``@@export_all`` and ``@@import_all`` are also contained in the helper-packages https://github.com/starzel/contentexport and https://github.com/starzel/contentimport

FAQ, Tips and Tricks
====================

This section covers frequent use-cases and examples for features that are not required for all migrations.

Using global_obj_hook during export
-----------------------------------

Using ``global_obj_hook`` during export to inspect content and decide to skip it.

.. code-block:: python

    def global_obj_hook(self, obj):
        # Drop subtopics
        if obj.portal_type == "Topic" and obj.__parent__.portal_type == "Topic":
            return

        # Drop files and images from PFG formfolders
        if obj.__parent__.portal_type == "FormFolder":
            return
        return obj


Using dict-hooks during export
------------------------------

Use ``global_dict_hook`` during export to inspect content and modify the serialized json.
You can also use ``dict_hook_<somecontenttype>`` to better structure your code for readability.

Sometimes you need to handle data that you add in ``global_dict_hook`` during export in corresponding code in ``global_object_hook`` during import.

The following example about placeful workflow policy is a perfect example for that pattern:


Export/Import placeful workflow policy
--------------------------------------

Export:

.. code-block:: python

    def global_dict_hook(self, item, obj):
        if obj.isPrincipiaFolderish and ".wf_policy_config" in obj.keys():
            wf_policy = obj[".wf_policy_config"]
            item["exportimport.workflow_policy"] = {
                "workflow_policy_below": wf_policy.workflow_policy_below,
                "workflow_policy_in": wf_policy.workflow_policy_in,
            }
        return item

Import:

.. code-block:: python

    def global_obj_hook(self, obj, item):
        wf_policy = item.get("exportimport.workflow_policy")
        if wf_policy:
            obj.manage_addProduct["CMFPlacefulWorkflow"].manage_addWorkflowPolicyConfig()
            wf_policy_config = obj[".wf_policy_config"]
            wf_policy_config.setPolicyIn(wf_policy["workflow_policy_in"], update_security=True)
            wf_policy_config.setPolicyBelow(wf_policy["workflow_policy_below"], update_security=True)


Using dict-hooks during import
------------------------------

A lot of fixes can be done during import using the ``global_dict_hook`` or ``dict_hook_<contenttype>``.

Here we prevent the expire-date to be before the effective date since that would lead to validation-errors during deserializing:

.. code-block:: python

    def global_dict_hook(self, item):
        effective = item.get('effective', None)
        expires = item.get('expires', None)
        if effective and expires and expires <= effective:
            item.pop('expires')
        return item

Here we drop empty lines from the creators:

.. code-block:: python

    def global_dict_hook(self, item):
        item["creators"] = [i for i in item.get("creators", []) if i]
        return item

This example migrates a ``PloneHelpCenter`` to a simple folder/document structure during import.
There are a couple more types to handle (as folder or document) but you get the idea, don't you?

.. code-block:: python

    def dict_hook_helpcenter(self, item):
        item["@type"] = "Folder"
        item["layout"] = "listing_view"
        return item

    def dict_hook_helpcenterglossary(self, item):
        item["@type"] = "Folder"
        item["layout"] = "listing_view"
        return item

    def dict_hook_helpcenterinstructionalvideo(self, item):
        item["@type"] = "File"
        if item.get("video_file"):
            item["file"] = item["video_file"]
        return item

    def dict_hook_helpcenterlink(self, item):
        item["@type"] = "Link"
        item["remoteUrl"] = item.get("url", None)
        return item

    def dict_hook_helpcenterreferencemanualpage(self, item):
        item["@type"] = "Document"
        return item

If you change types during import you need to take care of other cases where types are referenced.\
Examples are collection-queries (see "Fixing invalid collection queries" below) or constrains (see here):

.. code-block:: python

    PORTAL_TYPE_MAPPING = {
        "Topic": "Collection",
        "FormFolder": "EasyForm",
        "HelpCenter": "Folder",
    }

    def global_dict_hook(self, item):
        if item.get("exportimport.constrains"):
            types_fixed = []
            for portal_type in item["exportimport.constrains"]["locally_allowed_types"]:
                if portal_type in PORTAL_TYPE_MAPPING:
                    types_fixed.append(PORTAL_TYPE_MAPPING[portal_type])
                elif portal_type in ALLOWED_TYPES:
                    types_fixed.append(portal_type)
            item["exportimport.constrains"]["locally_allowed_types"] = list(set(types_fixed))

            types_fixed = []
            for portal_type in item["exportimport.constrains"]["immediately_addable_types"]:
                if portal_type in PORTAL_TYPE_MAPPING:
                    types_fixed.append(PORTAL_TYPE_MAPPING[portal_type])
                elif portal_type in ALLOWED_TYPES:
                    types_fixed.append(portal_type)
            item["exportimport.constrains"]["immediately_addable_types"] = list(set(types_fixed))
        return item


Change workflow
---------------

.. code-block:: python

    REVIEW_STATE_MAPPING = {
        "internal": "published",
        "internally_published": "published",
        "obsolete": "private",
        "hidden": "private",
    }

    def global_dict_hook(self, item):
        if item.get("review_state") in REVIEW_STATE_MAPPING:
            item["review_state"] = REVIEW_STATE_MAPPING[item["review_state"]]
        return item


Export/Import Annotations
-------------------------

Some core-features of Plone (e.g. comments) use annotations to store data.
The core features are already covered but your custom code or community addons may use annotations as well.
Here is how you can migrate them.

**Export**: Only export those Annotations that your really need.

.. code-block:: python

    from zope.annotation.interfaces import IAnnotations
    ANNOTATIONS_TO_EXPORT = [
        "syndication_settings",
    ]
    ANNOTATIONS_KEY = 'exportimport.annotations'

    class CustomExportContent(ExportContent):

        def global_dict_hook(self, item, obj):
            item = self.export_annotations(item, obj)
            return item

        def export_annotations(self, item, obj):
            results = {}
            annotations = IAnnotations(obj)
            for key in ANNOTATIONS_TO_EXPORT:
                data = annotations.get(key)
                if data:
                    results[key] = IJsonCompatible(data, None)
            if results:
                item[ANNOTATIONS_KEY] = results
            return item

**Import**:

.. code-block:: python

    from zope.annotation.interfaces import IAnnotations
    ANNOTATIONS_KEY = "exportimport.annotations"

    class CustomImportContent(ImportContent):

        def global_obj_hook(self, obj, item):
            item = self.import_annotations(obj, item)
            return item

        def import_annotations(self, obj, item):
            annotations = IAnnotations(obj)
            for key in item.get(ANNOTATIONS_KEY, []):
                annotations[key] = item[ANNOTATIONS_KEY][key]
            return item

Some features also store data in annotations on the portal, e.g. `plone.contentrules.localassignments`, `plone.portlets.categoryblackliststatus`, `plone.portlets.contextassignments`, `syndication_settings`.
Depending on your requirements you may want to export and import those as well.


Export/Import Marker Interfaces
-------------------------------

**Export**: You may only want to export the marker-interfaces you need.
It is a good idea to inspect a list of all used marker interfaces in a portal before deciding what to migrate.

.. code-block:: python

    from zope.interface import directlyProvidedBy

    MARKER_INTERFACES_TO_EXPORT = [
        "collective.easyslider.interfaces.ISliderPage",
        "plone.app.layout.navigation.interfaces.INavigationRoot",
    ]
    MARKER_INTERFACES_KEY = "exportimport.marker_interfaces"

    class CustomExportContent(ExportContent)

        def global_dict_hook(self, item, obj):
            item = self.export_marker_interfaces(item, obj)
            return item

        def export_marker_interfaces(self, item, obj):
            interfaces = [i.__identifier__ for i in directlyProvidedBy(obj)]
            interfaces = [i for i in interfaces if i in MARKER_INTERFACES_TO_EXPORT]
            if interfaces:
                item[MARKER_INTERFACES_KEY] = interfaces
            return item

**Import**:

.. code-block:: python

    from plone.dexterity.utils import resolveDottedName
    from zope.interface import alsoProvides

    MARKER_INTERFACES_KEY = "exportimport.marker_interfaces"

    class CustomImportContent(ImportContent):

        def global_obj_hook_before_deserializing(self, obj, item):
            """Apply marker interfaces before deserializing."""
            for iface_name in item.pop(MARKER_INTERFACES_KEY, []):
                try:
                    iface = resolveDottedName(iface_name)
                    if not iface.providedBy(obj):
                        alsoProvides(obj, iface)
                        logger.info("Applied marker interface %s to %s", iface_name, obj.absolute_url())
                except ModuleNotFoundError:
                    pass
            return obj, item

Skip versioning during import
-----------------------------

The event-handlers of versioning can seriously slow down your imports.
It is a good idea to skip it before the import:

.. code-block:: python

    VERSIONED_TYPES = [
        "Document",
        "News Item",
        "Event",
        "Link",
    ]

    def start(self):
        self.items_without_parent = []
        portal_types = api.portal.get_tool("portal_types")
        for portal_type in VERSIONED_TYPES:
            fti = portal_types.get(portal_type)
            behaviors = list(fti.behaviors)
            if 'plone.versioning' in behaviors:
                logger.info(f"Disable versioning for {portal_type}")
                behaviors.remove('plone.versioning')
            fti.behaviors = behaviors

Re-enable versioning and create initial versions after all imports and fixes are done, e.g in the view ``@@import_all``.

.. code-block:: python

    from Products.CMFEditions.interfaces.IModifier import FileTooLargeToVersionError

    VERSIONED_TYPES = [
        "Document",
        "News Item",
        "Event",
        "Link",
    ]

    class ImportAll(BrowserView):

        # re-enable versioning
        portal_types = api.portal.get_tool("portal_types")
        for portal_type in VERSIONED_TYPES:
            fti = portal_types.get(portal_type)
            behaviors = list(fti.behaviors)
            if "plone.versioning" not in behaviors:
                behaviors.append("plone.versioning")
                logger.info(f"Enable versioning for {portal_type}")
            if "plone.locking" not in behaviors:
                behaviors.append("plone.locking")
                logger.info(f"Enable locking for {portal_type}")
            fti.behaviors = behaviors
        transaction.get().note("Re-enabled versioning")
        transaction.commit()

        # create initial version for all versioned types
        logger.info("Creating initial versions")
        portal_repository = api.portal.get_tool("portal_repository")
        brains = api.content.find(portal_type=VERSIONED_TYPES)
        total = len(brains)
        for index, brain in enumerate(brains):
            obj = brain.getObject()
            try:
                portal_repository.save(obj=obj, comment="Imported Version")
            except FileTooLargeToVersionError:
                pass
            if not index % 1000:
                msg = f"Created versions for {index} of {total} items."
                logger.info(msg)
                transaction.get().note(msg)
                transaction.commit()
        msg = "Created initial versions"
        transaction.get().note(msg)
        transaction.commit()


Dealing with validation errors
------------------------------

Sometimes you get validation-errors during import because the data cannot be validated.
That can happen when options in a field are generated from content in the site.
In these cases you cannot be sure that all options already exist in the portal while importing the content.

It may also happen, when you have validators that rely on content or configuration that does not exist on import.

.. note::

    For relation fields this is not necessary since relations are imported after content anyway!

There are two ways to handle these issues:

* Use a simple setter bypassing the validation used by the restapi
* Defer the import until all other imports were run


Use a simple setter
*******************

You need to specify which content-types and fields you want to handle that way.

It is put in a key, that the normal import will ignore and set using ``setattr()`` before deserializing the rest of the data.

.. code-block:: python

    SIMPLE_SETTER_FIELDS = {
        "ALL": ["some_shared_field"],
        "CollaborationFolder": ["allowedPartnerDocTypes"],
        "DocType": ["automaticTransferTargets"],
        "DPDocument": ["scenarios"],
        "DPEvent" : ["Status"],
    }

    class CustomImportContent(ImportContent):

        def global_dict_hook(self, item):
            simple = {}
            for fieldname in SIMPLE_SETTER_FIELDS.get("ALL", []):
                if fieldname in item:
                    value = item.pop(fieldname)
                    if value:
                        simple[fieldname] = value
            for fieldname in SIMPLE_SETTER_FIELDS.get(item["@type"], []):
                if fieldname in item:
                    value = item.pop(fieldname)
                    if value:
                        simple[fieldname] = value
            if simple:
                item["exportimport.simplesetter"] = simple

        def global_obj_hook_before_deserializing(self, obj, item):
            """Hook to modify the created obj before deserializing the data.
            """
            # import simplesetter data before the rest
            for fieldname, value in item.get("exportimport.simplesetter", {}).items():
                setattr(obj, fieldname, value)

.. note::

    Using ``global_obj_hook_before_deserializing`` makes sure that data is there when the event-handlers are run after import.

Defer import
************

You can also wait until all content is imported before setting the values on these fields.
Again you need to find out which fields for which types you want to handle that way.

Here the data is stored in an annotation on the imported object from which it is later read.
This example also supports setting some data with ``setattr`` without validating it:

.. code-block:: python

    from plone.restapi.interfaces import IDeserializeFromJson
    from zope.annotation.interfaces import IAnnotations
    from zope.component import getMultiAdapter

    DEFERRED_KEY = "exportimport.deferred"
    DEFERRED_FIELD_MAPPING = {
        "talk": ["somefield"],
        "speaker": [
            "custom_field",
            "another_field",
        ]
    }
    SIMPLE_SETTER_FIELDS = {"custom_type": ["another_field"]}

    class CustomImportContent(ImportContent):

        def global_dict_hook(self, item):
            # Move deferred values to a different key to not deserialize.
            # This could also be done during export.
            item[DEFERRED_KEY] = {}
            for fieldname in DEFERRED_FIELD_MAPPING.get(item["@type"], []):
                if item.get(fieldname):
                    item[DEFERRED_KEY][fieldname] = item.pop(fieldname)
            return item

        def global_obj_hook(self, obj, item):
            # Store deferred data in an annotation.
            deferred = item.get(DEFERRED_KEY, {})
            if deferred:
                annotations = IAnnotations(obj)
                annotations[DEFERRED_KEY] = {}
                for key, value in deferred.items():
                    annotations[DEFERRED_KEY][key] = value

You then need a new step in the migration to move the deferred values from the annotation to the field:

.. code-block:: python

    class ImportDeferred(BrowserView):

        def __call__(self):
            # This example reuses the form export_other.pt from collective.exportimport
            self.title = "Import deferred data"
            if not self.request.form.get("form.submitted", False):
                return self.index()
            portal = api.portal.get()
            self.results = []
            for brain in api.content.find(DEFERRED_FIELD_MAPPING.keys()):
                obj = brain.getObject()
                self.import_deferred(obj)
            api.portal.show_message(f"Imported deferred data for {len(self.results)} items!", self.request)

        def import_deferred(self, obj):
            annotations = IAnnotations(obj, {})
            deferred = annotations.get(DEFERRED_KEY, None)
            if not deferred:
                return
            # Shortcut for simple fields (e.g. storing strings, uuids etc.)
            for fieldname in SIMPLE_SETTER_FIELDS.get(obj.portal_type, []):
                value = deferred.pop(fieldname, None)
                if value:
                    setattr(obj, fieldname, value)
            if not deferred:
                return
            # This approach validates the values and converts more complex data
            deserializer = getMultiAdapter((obj, self.request), IDeserializeFromJson)
            try:
                obj = deserializer(validate_all=False, data=deferred)
            except Exception as e:
                logger.info("Error while importing deferred data for %s", obj.absolute_url(), exc_info=True)
                logger.info("Data: %s", deferred)
            else:
                self.results.append(obj.absolute_url())
            # cleanup
            del annotations[DEFERRED_KEY]

This additional view obviously needs to be registered:

.. code-block:: xml

    <browser:page
        name="import_deferred"
        for="zope.interface.Interface"
        class=".import_content.ImportDeferred"
        template="export_other.pt"
        permission="cmf.ManagePortal"
        />


Handle LinguaPlone content
--------------------------

Export:

.. code-block:: python

    def global_dict_hook(self, item, obj):
        # Find language of the nearest parent with a language
        # Usefull for LinguaPlone sites where some content is languageindependent
        parent = obj.__parent__
        for ancestor in parent.aq_chain:
            if IPloneSiteRoot.providedBy(ancestor):
                # keep language for root content
                nearest_ancestor_lang = item["language"]
                break
            if getattr(ancestor, "getLanguage", None) and ancestor.getLanguage():
                nearest_ancestor_lang = ancestor.getLanguage()
                item["parent"]["language"] = nearest_ancestor_lang
                break

        # This forces "wrong" languages to the nearest parents language
        if "language" in item and item["language"] != nearest_ancestor_lang:
            logger.info(u"Forcing %s (was %s) for %s %s ", nearest_ancestor_lang, item["language"], item["@type"], item["@id"])
            item["language"] = nearest_ancestor_lang

        # set missing language
        if not item.get("language"):
            item["language"] = nearest_ancestor_lang

        # add info on translations to help find the right container
        # usually this idone by export_translations
        # but when migrating from LP to pam you sometimes want to check the
        # tranlation info during import
        if getattr(obj.aq_base, "getTranslations", None) is not None:
            translations = obj.getTranslations()
            if translations:
                item["translation"] = {}
                for lang in translations:
                    uuid = IUUID(translations[lang][0], None)
                    if uuid == item["UID"]:
                        continue
                    translation = translations[lang][0]
                    if not lang:
                        lang = "no_language"
                    item["translation"][lang] = translation.absolute_url()

Import:

.. code-block:: python

    def global_dict_hook(self, item):

        # Adapt this to your site
        languages = ["en", "fr", "de"]
        default_language = "en"
        portal_id = "Plone"

        # No language => lang of parent or default
        if item.get("language") not in languages:
            if item["parent"].get("language"):
                item["language"] = item["parent"]["language"]
            else:
                item["language"] = default_language

        lang = item["language"]

        if item["parent"].get("language") != item["language"]:
            logger.debug(f"Inconsistent lang: item is {lang}, parent is {item['parent'].get('language')} for {item['@id']}")

        # Move item to the correct language-root-folder
        # This is only relevant for items in the site-root.
        # Most items containers are usually looked up by the uuid of the old parent
        url = item["@id"]
        parent_url = item["parent"]["@id"]

        url = url.replace(f"/{portal_id}/", f"/{portal_id}/{lang}/", 1)
        parent_url = parent_url.replace(f"/{portal_id}", f"/{portal_id}/{lang}", 1)

        item["@id"] = url
        item["parent"]["@id"] = parent_url

        return item

Alternative ways to handle items without parent
-----------------------------------------------

Often it is better to export and log items for which no container could be found instead of re-creating the original structure.

.. code-block:: python

    def update(self):
        self.items_without_parent = []

    def create_container(self, item):
        # Override create_container to never create parents
        self.items_without_parent.append(item)

    def finish(self):
        # export content without parents
        if self.items_without_parent:
            data = json.dumps(self.items_without_parent, sort_keys=True, indent=4)
            number = len(self.items_without_parent)
            cfg = getConfiguration()
            filename = 'content_without_parent.json'
            filepath = os.path.join(cfg.clienthome, filename)
            with open(filepath, 'w') as f:
                f.write(data)
            msg = u"Saved {} items without parent to {}".format(number, filepath)
            logger.info(msg)
            api.portal.show_message(msg, self.request)


Export/Import Zope Users
------------------------

By default only users and groups stores in Plone are exported/imported.
You can export/import Zope user like this.

**Export**

.. code-block:: python

    from collective.exportimport.export_other import BaseExport
    from plone import api

    import six

    class ExportZopeUsers(BaseExport):

        AUTO_ROLES = ["Authenticated"]

        def __call__(self, download_to_server=False):
            self.title = "Export Zope users"
            self.download_to_server = download_to_server
            portal = api.portal.get()
            app = portal.__parent__
            self.acl = app.acl_users
            self.pms = api.portal.get_tool("portal_membership")
            data = self.all_zope_users()
            self.download(data)

        def all_zope_users(self):
            results = []
            for user in self.acl.searchUsers():
                data = self._getUserData(user["userid"])
                data['title'] = user['title']
                results.append(data)
            return results

        def _getUserData(self, userId):
            member = self.pms.getMemberById(userId)
            roles = [
                role
                for role in member.getRoles()
                if role not in self.AUTO_ROLES
            ]
            # userid, password, roles
            props = {
                "username": userId,
                "password": json_compatible(self._getUserPassword(userId)),
                "roles": json_compatible(roles),
            }
            return props

        def _getUserPassword(self, userId):
            users = self.acl.users
            passwords = users._user_passwords
            password = passwords.get(userId, "")
            return password

**Import**:

.. code-block:: python

    class ImportZopeUsers(BrowserView):

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
                    members = self.import_members(data)
                    msg = u"Imported {} members".format(members)
                    api.portal.show_message(msg, self.request)
                if return_json:
                    msg = {"state": status, "msg": msg}
                    return json.dumps(msg)

            return self.index()

        def import_members(self, data):
            app = self.portal.__parent__
            acl = app.acl_users
            counter = 0
            for item in data:
                username = item["username"]
                password = item.pop("password")
                roles = item.pop("roles", [])
                if not username or not password or not roles:
                    continue
                title = item.pop("title", None)
                acl.users.addUser(username, title, password)
                for role in roles:
                    acl.roles.assignRoleToPrincipal(role, username)
                counter += 1
            return counter


Export/Import properties, registry-settings and installed addons
----------------------------------------------------------------

When you migrate multiple similar sites that are configured manually it can be useful to export and import configuration that was set by hand.

Export/Import installed settings and add-ons
********************************************

This custom export exports and imports some selected settings and addons from a Plone 4.3 site.

**Export:**

.. code-block:: python

    from collective.exportimport.export_other import BaseExport
    from logging import getLogger
    from plone import api
    from plone.restapi.serializer.converters import json_compatible

    logger = getLogger(__name__)


    class ExportSettings(BaseExport):
        """Export various settings for haiku sites
        """

        def __call__(self, download_to_server=False):
            self.title = "Export installed addons various settings"
            self.download_to_server = download_to_server
            if not self.request.form.get("form.submitted", False):
                return self.index()

            data = self.export_settings()
            self.download(data)

        def export_settings(self):
            results = {}
            addons = []
            qi = api.portal.get_tool("portal_quickinstaller")
            for product in qi.listInstalledProducts():
                if product["id"].startswith("myproject."):
                    addons.append(product["id"])
            results["addons"] = addons

            portal = api.portal.get()
            registry = {}
            registry["plone.email_from_name"] = portal.getProperty('email_from_name', '')
            registry["plone.email_from_address"] = portal.getProperty('email_from_address', '')
            registry["plone.smtp_host"] = getattr(portal.MailHost, 'smtp_host', '')
            registry["plone.smtp_port"] = int(getattr(portal.MailHost, 'smtp_port', 25))
            registry["plone.smtp_userid"] = portal.MailHost.get('smtp_user_id')
            registry["plone.smtp_pass"] = portal.MailHost.get('smtp_pass')
            registry["plone.site_title"] = portal.title

            portal_properties = api.portal.get_tool("portal_properties")
            iprops = portal_properties.imaging_properties
            registry["plone.allowed_sizes"] = iprops.getProperty('allowed_sizes')
            registry["plone.quality"] = iprops.getProperty('quality')
            site_props = portal_properties.site_properties
            if site_props.hasProperty("webstats_js"):
                registry["plone.webstats_js"] = site_props.webstats_js
            results["registry"] = json_compatible(registry)
            return results


**Import:**

The import installs the addons and load the settings in the registry.
Since Plone 5 ``portal_properties`` is no longer used.

.. code-block:: python

    from logging import getLogger
    from plone import api
    from plone.registry.interfaces import IRegistry
    from Products.CMFPlone.utils import get_installer
    from Products.Five import BrowserView
    from zope.component import getUtility
    from ZPublisher.HTTPRequest import FileUpload

    import json

    logger = getLogger(__name__)

    class ImportSettings(BrowserView):
        """Import various settings"""

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
                        "Failure while uploading: {}".format(e),
                        request=self.request,
                    )
                else:
                    self.import_settings(data)
                    msg = "Imported addons and settings"
                    api.portal.show_message(msg, self.request)
                if return_json:
                    msg = {"state": status, "msg": msg}
                    return json.dumps(msg)

            return self.index()

        def import_settings(self, data):
            installer = get_installer(self.context)
            for addon in data["addons"]:
                if not installer.is_product_installed(addon) and installer.is_product_installable(addon):
                    installer.install_product(addon)
                    logger.info(f"Installed addon {addon}")
            registry = getUtility(IRegistry)
            for key, value in data["registry"].items():
                registry[key] = value
                logger.info(f"Imported record {key}: {value}")


Export/Import registry settings
*******************************

The pull-request https://github.com/collective/collective.exportimport/pull/130 has views ``@@export_registry`` and ``@@import_registry``.
These views export and import registry records that do not use the default-setting specified in the schema for that registry record.
The export alone could also be usefull to figure out which settings were modified for a site.

That code will probably not be merged but you can use it in your own projects.

Migrate PloneFormGen to Easyform
--------------------------------

To be able to export PFG as easyform you should use the branch ``migration_features_1.x`` of ``collective.easyform`` in your old site.
Easyform does not need to be installed, we only need the methods ``fields_model`` and ``actions_model``.

Export:

.. code-block:: python

    def dict_hook_formfolder(self, item, obj):
        item["@type"] = "EasyForm"
        item["is_folderish"] = False

        from collective.easyform.migration.fields import fields_model
        from collective.easyform.migration.actions import actions_model

        # this does most of the heavy lifting...
        item["fields_model"] = fields_model(obj)
        item["actions_model"] = actions_model(obj)

        # handle thankspage
        pfg_thankspage = obj.get(obj.getThanksPage(), None)
        if pfg_thankspage:
            item["thankstitle"] = pfg_thankspage.title
            item["thanksdescription"] = pfg_thankspage.Description()
            item["showAll"] = pfg_thankspage.showAll
            item["showFields"] = pfg_thankspage.showFields
            item["includeEmpties"] = pfg_thankspage.includeEmpties
            item["thanksPrologue"] = json_compatible(pfg_thankspage.thanksPrologue.raw)
            item["thanksEpilogue"] = json_compatible(pfg_thankspage.thanksEpilogue.raw)

        # optional
        item["exportimport._inputStorage"] = self.export_saved_data(obj)

        # Drop some PFG fields no longer needed
        obsolete_fields = [
            "layout",
            "actionAdapter",
            "checkAuthenticator",
            "constrainTypesMode",
            "location",
            "thanksPage",
        ]
        for key in obsolete_fields:
            item.pop(key, None)

        # optional: disable tabs for imported forms
        item["form_tabbing"] = False

        # fix some custom validators
        replace_mapping = {
            "request.form['": "request.form['form.widgets.",
            "request.form.get('": "request.form.get('form.widgets.",
            "member and member.id or ''": "member and member.getProperty('id', '') or ''",
        }

        # fix overrides in actions and fields to use form.widgets.xyz instead of xyz
        for schema in ["actions_model", "fields_model"]:
            for old, new in replace_mapping.items():
                if old in item[schema]:
                    item[schema] = item[schema].replace(old, new)

            # add your own fields if you have these issues...
            for fieldname in [
                "email",
                "replyto",
            ]:
                if "request/form/{}".format(fieldname) in item[schema]:
                    item[schema] = item[schema].replace("request/form/{}".format(fieldname), "python: request.form.get('form.widgets.{}')".format(fieldname))

        return item

    def export_saved_data(self, obj):
        actions = {}
        for data_adapter in obj.objectValues("FormSaveDataAdapter"):
            data_adapter_name = data_adapter.getId()
            actions[data_adapter_name] = {}
            cols = data_adapter.getColumnNames()
            column_count_mismatch = False
            for idx, row in enumerate(data_adapter.getSavedFormInput()):
                if len(row) != len(cols):
                    column_count_mismatch = True
                    logger.debug("Column count mismatch at row %s", idx)
                    continue
                data = {}
                for key, value in zip(cols, row):
                    data[key] = json_compatible(value)
                id_ = int(time() * 1000)
                while id_ in actions[data_adapter_name]:  # avoid collisions during export
                    id_ += 1
                data["id"] = id_
                actions[data_adapter_name][id_] = data
            if column_count_mismatch:
                logger.info(
                    "Number of columns does not match for all rows. Some data were skipped in "
                    "data adapter %s/%s",
                    "/".join(obj.getPhysicalPath()),
                    data_adapter_name,
                )
        return actions

Import exported ``PloneFormGen`` data into ``Easyform``:

.. code-block:: python

    def obj_hook_easyform(self, obj, item):
        if not item.get("exportimport._inputStorage"):
            return
        from collective.easyform.actions import SavedDataBTree
        from persistent.mapping import PersistentMapping
        if not hasattr(obj, '_inputStorage'):
            obj._inputStorage = PersistentMapping()
        for name, data in item["exportimport._inputStorage"].items():
            obj._inputStorage[name] = SavedDataBTree()
            for key, row in data.items():
                 obj._inputStorage[name][int(key)] = row


Export and import collective.cover content
------------------------------------------

Export:

.. code-block:: python

    from collective.exportimport.serializer import get_dx_blob_path
    from plone.app.textfield.value import RichTextValue
    from plone.namedfile.file import NamedBlobImage
    from plone.restapi.interfaces import IJsonCompatible
    from z3c.relationfield import RelationValue
    from zope.annotation.interfaces import IAnnotations

    def global_dict_hook(self, item, obj):
        item = self.handle_cover(item, obj)
        return item

    def handle_cover(self, item, obj):
        if ICover.providedBy(obj):
            item['tiles'] = {}
            annotations = IAnnotations(obj)
            for tile in obj.get_tiles():
                annotation_key = 'plone.tiles.data.{}'.format(tile['id'])
                annotation = annotations.get(annotation_key, None)
                if annotation is None:
                    continue
                tile_data = self.serialize_tile(annotation)
                tile_data['type'] = tile['type']
                item['tiles'][tile['id']] = tile_data
        return item

    def serialize_tile(self, annotation):
        data = {}
        for key, value in annotation.items():
            if isinstance(value, RichTextValue):
                value = value.raw
            elif isinstance(value, RelationValue):
                value = value.to_object.UID()
            elif isinstance(value, NamedBlobImage):
                blobfilepath = get_dx_blob_path(value)
                if not blobfilepath:
                    continue
                value = {
                    "filename": value.filename,
                    "content-type": value.contentType,
                    "size": value.getSize(),
                    "blob_path": blobfilepath,
                }
            data[key] = IJsonCompatible(value, None)
        return data

Import:

.. code-block:: python

    from collections import defaultdict
    from collective.exportimport.import_content import get_absolute_blob_path
    from plone.app.textfield.interfaces import IRichText
    from plone.app.textfield.interfaces import IRichTextValue
    from plone.namedfile.file import NamedBlobImage
    from plone.namedfile.interfaces import INamedBlobImageField
    from plone.tiles.interfaces import ITileType
    from zope.annotation.interfaces import IAnnotations
    from zope.component import getUtilitiesFor
    from zope.schema import getFieldsInOrder

    COVER_CONTENT = [
        "collective.cover.content",
    ]

    def global_obj_hook(self, obj, item):
        if item["@type"] in COVER_CONTENT and "tiles" in item:
            item = self.import_tiles(obj, item)

    def import_tiles(self, obj, item):
        RICHTEXT_TILES = defaultdict(list)
        IMAGE_TILES = defaultdict(list)
        for tile_name, tile_type in getUtilitiesFor(ITileType):
            for fieldname, field in getFieldsInOrder(tile_type.schema):
                if IRichText.providedBy(field):
                    RICHTEXT_TILES[tile_name].append(fieldname)
                if INamedBlobImageField.providedBy(field):
                    IMAGE_TILES[tile_name].append(fieldname)

        annotations = IAnnotations(obj)
        prefix = "plone.tiles.data."
        for uid, tile in item["tiles"].items():
            # TODO: Maybe create all tiles that do not need to be defferred?
            key = prefix + uid
            tile_name = tile.pop("type", None)
            # first set raw data
            annotations[key] = item["tiles"][uid]
            for fieldname in RICHTEXT_TILES.get(tile_name, []):
                raw = annotations[key][fieldname]
                if raw is not None and not IRichTextValue.providedBy(raw):
                    annotations[key][fieldname] = RichTextValue(raw, "text/html", "text/x-html-safe")
            for fieldname in IMAGE_TILES.get(tile_name, []):
                data = annotations[key][fieldname]
                if data is not None:
                    blob_path = data.get("blob_path")
                    if not blob_path:
                        continue

                    abs_blob_path = get_absolute_blob_path(obj, blob_path)
                    if not abs_blob_path:
                        logger.info("Blob path %s for tile %s of %s %s does not exist!", blob_path, tile, obj.portal_type, obj.absolute_url())
                        continue
                    # Determine the class to use: file or image.
                    filename = data["filename"]
                    content_type = data["content-type"]

                    # Write the field.
                    with open(abs_blob_path, "rb") as myfile:
                        blobdata = myfile.read()
                    image = NamedBlobImage(
                        data=blobdata,
                        contentType=content_type,
                        filename=filename,
                    )
                    annotations[key][fieldname] = image
        return item


Fixing invalid collection queries
---------------------------------

Some queries changes between Plone 4 and 5.
This fixes the issues.

The actual migration of topics to collections in ``collective.exportimport.serializer.SerializeTopicToJson`` does not (yet) take care of that.

.. code-block:: python

    class CustomImportContent(ImportContent):

        def global_dict_hook(self, item):
            if item["@type"] in ["Collection", "Topic"]:
                item = self.fix_query(item)

        def fix_query(self, item):
            item["@type"] = "Collection"
            query = item.pop("query", [])
            if not query:
                logger.info("Drop item without query: %s", item["@id"])
                return

            fixed_query = []
            indexes_to_fix = [
                "portal_type",
                "review_state",
                "Creator",
                "Subject",
            ]
            operator_mapping = {
                # old -> new
                "plone.app.querystring.operation.selection.is":
                    "plone.app.querystring.operation.selection.any",
                "plone.app.querystring.operation.string.is":
                    "plone.app.querystring.operation.selection.any",
            }

            for crit in query:
                if crit["i"] == "portal_type" and len(crit["v"]) > 30:
                    # Criterion is all types
                    continue

                if crit["o"].endswith("relativePath") and crit["v"] == "..":
                    # relativePath no longer accepts ..
                    crit["v"] = "..::1"

                if crit["i"] in indexes_to_fix:
                    for old_operator, new_operator in operator_mapping.items():
                        if crit["o"] == old_operator:
                            crit["o"] = new_operator

                if crit["i"] == "portal_type":
                    # Some types may have changed their names
                    fixed_types = []
                    for portal_type in crit["v"]:
                        fixed_type = PORTAL_TYPE_MAPPING.get(portal_type, portal_type)
                        fixed_types.append(fixed_type)
                    crit["v"] = list(set(fixed_types))

                if crit["i"] == "review_state":
                    # Review states may have changed their names
                    fixed_states = []
                    for review_state in crit["v"]:
                        fixed_state = REVIEW_STATE_MAPPING.get(review_state, review_state)
                        fixed_states.append(fixed_state)
                    crit["v"] = list(set(fixed_states))

                if crit["o"] == "plone.app.querystring.operation.string.currentUser":
                    crit["v"] = ""

                fixed_query.append(crit)
            item["query"] = fixed_query

            if not item["query"]:
                logger.info("Drop collection without query: %s", item["@id"])
                return
            return item


Migrate to Volto
----------------

You can reuse the migration-code provided by ``@@migrate_to_volto`` in ``plone.volto`` in a migration.
The following example (used for migrating https://plone.org to Volto) can be used to migrate a site from any older version to Plone 6 with Volto.

You need to have the Blocks Conversion Tool (https://github.com/plone/blocks-conversion-tool) running that takes care of migrating richtext-values to Volto-blocks.

See https://6.docs.plone.org/backend/upgrading/version-specific-migration/migrate-to-volto.html for more details on the changes the migration to Volto does.


.. code-block:: python

    from App.config import getConfiguration
    from bs4 import BeautifulSoup
    from collective.exportimport.fix_html import fix_html_in_content_fields
    from collective.exportimport.fix_html import fix_html_in_portlets
    from contentimport.interfaces import IContentimportLayer
    from logging import getLogger
    from pathlib import Path
    from plone import api
    from plone.volto.browser.migrate_to_volto import migrate_richtext_to_blocks
    from plone.volto.setuphandlers import add_behavior
    from plone.volto.setuphandlers import remove_behavior
    from Products.CMFPlone.utils import get_installer
    from Products.Five import BrowserView
    from zope.interface import alsoProvides

    import requests
    import transaction

    logger = getLogger(__name__)

    DEFAULT_ADDONS = []


    class ImportAll(BrowserView):

        def __call__(self):

            request = self.request

            # Check if Blocks-conversion-tool is running
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            r = requests.post(
                "http://localhost:5000/html", headers=headers, json={"html": "<p>text</p>"}
            )
            r.raise_for_status()

            # Submit a simple form template to trigger the import
            if not request.form.get("form.submitted", False):
                return self.index()

            portal = api.portal.get()
            alsoProvides(request, IContentimportLayer)

            installer = get_installer(portal)
            if not installer.is_product_installed("contentimport"):
                installer.install_product("contentimport")

            # install required addons
            for addon in DEFAULT_ADDONS:
                if not installer.is_product_installed(addon):
                    installer.install_product(addon)

            # Fake the target being a classic site even though plone.volto is installed...
            # 1. Allow Folders and Collections (they are disabled in Volto by default)
            portal_types = api.portal.get_tool("portal_types")
            portal_types["Collection"].global_allow = True
            portal_types["Folder"].global_allow = True
            # 2. Enable richtext behavior (otherwise no text will be imported)
            for type_ in ["Document", "News Item", "Event"]:
                add_behavior(type_, "plone.richtext")

            transaction.commit()
            cfg = getConfiguration()
            directory = Path(cfg.clienthome) / "import"

            # Import content
            view = api.content.get_view("import_content", portal, request)
            request.form["form.submitted"] = True
            request.form["commit"] = 500
            view(server_file="Plone.json", return_json=True)
            transaction.commit()

            # Run all other imports
            other_imports = [
                "relations",
                "members",
                "translations",
                "localroles",
                "ordering",
                "defaultpages",
                "discussion",
                "portlets",  # not really useful in Volto
                "redirects",
            ]
            for name in other_imports:
                view = api.content.get_view(f"import_{name}", portal, request)
                path = Path(directory) / f"export_{name}.json"
                if path.exists():
                    results = view(jsonfile=path.read_text(), return_json=True)
                    logger.info(results)
                    transaction.get().note(f"Finished import_{name}")
                    transaction.commit()
                else:
                    logger.info(f"Missing file: {path}")

            # Optional: Run html-fixers on richtext
            fixers = [anchor_fixer]
            results = fix_html_in_content_fields(fixers=fixers)
            msg = "Fixed html for {} content items".format(results)
            logger.info(msg)
            transaction.get().note(msg)
            transaction.commit()

            results = fix_html_in_portlets()
            msg = "Fixed html for {} portlets".format(results)
            logger.info(msg)
            transaction.get().note(msg)
            transaction.commit()

            view = api.content.get_view("updateLinkIntegrityInformation", portal, request)
            results = view.update()
            msg = f"Updated linkintegrity for {results} items"
            logger.info(msg)
            transaction.get().note(msg)
            transaction.commit()

            # Rebuilding the catalog is necessary to prevent issues later on
            catalog = api.portal.get_tool("portal_catalog")
            logger.info("Rebuilding catalog...")
            catalog.clearFindAndRebuild()
            msg = "Finished rebuilding catalog!"
            logger.info(msg)
            transaction.get().note(msg)
            transaction.commit()

            # This uses the blocks-conversion-tool to migrate to blocks
            logger.info("Start migrating richtext to blocks...")
            migrate_richtext_to_blocks()
            msg = "Finished migrating richtext to blocks"
            transaction.get().note(msg)
            transaction.commit()

            # Reuse the migration-form from plon.volto to do some more tasks
            view = api.content.get_view("migrate_to_volto", portal, request)
            # Yes, wen want to migrate default pages
            view.migrate_default_pages = True
            view.slate = True
            logger.info("Start migrating Folders to Documents...")
            view.do_migrate_folders()
            msg = "Finished migrating Folders to Documents!"
            transaction.get().note(msg)
            transaction.commit()

            logger.info("Start migrating Collections to Documents...")
            view.migrate_collections()
            msg = "Finished migrating Collections to Documents!"
            transaction.get().note(msg)
            transaction.commit()

            reset_dates = api.content.get_view("reset_dates", portal, request)
            reset_dates()
            transaction.commit()

            # Disallow folders and collections again
            portal_types["Collection"].global_allow = False
            portal_types["Folder"].global_allow = False

            # Disable richtext behavior again
            for type_ in ["Document", "News Item", "Event"]:
                remove_behavior(type_, "plone.richtext")

            return request.response.redirect(portal.absolute_url())


    def anchor_fixer(text, obj=None):
        """Remove anchors since they are not supported by Volto yet"""
        soup = BeautifulSoup(text, "html.parser")
        for link in soup.find_all("a"):
            if not link.get("href") and not link.text:
                # drop empty links (e.g. anchors)
                link.decompose()
            elif not link.get("href") and link.text:
                # drop links without a href but keep the text
                link.unwrap()
        return soup.decode()


Migrate very old Plone Versions with data created by collective.jsonify
-----------------------------------------------------------------------

Versions older than Plone 4 do not support ``plone.restapi`` which is required to serialize the content used by ``collective.exportimport``.

To migrate Plone 1, 2 and 3 to Plone 6 you can use ``collective.jsonify`` for the export and ``collective.exportimport`` for the import.

Export
******

Use https://github.com/collective/collective.jsonify to export content.

You include the methods of ``collective.jsonify`` using `External Methods`.
See https://github.com/collective/collective.jsonify/blob/master/docs/install.rst for more info.

To work better with ``collective.exportimport`` you could extend the exported data using the feature ``additional_wrappers``.
Add info on the parent of an item to make it easier for ``collective.exportimport`` to import the data.

Here is a full example for `json_methods.py` which should be in `BUILDOUT_ROOT/parts/instance/Extensions/`

.. code-block:: python

    def extend_item(obj, item):
        """Extend to work better well with collective.exportimport"""
        from Acquisition import aq_parent
        parent = aq_parent(obj)
        item["parent"] = {
            "@id": parent.absolute_url(),
            "@type": getattr(parent, "portal_type", None),
        }
        if getattr(parent.aq_base, "UID", None) is not None:
            item["parent"]["UID"] = parent.UID()

        return item


Here is a full example for ``json_methods.py`` which should be in ``<BUILDOUT_ROOT>/parts/instance/Extensions/``

.. code-block:: python

    from collective.jsonify.export import export_content as export_content_orig
    from collective.jsonify.export import get_item

    EXPORTED_TYPES = [
        "Folder",
        "Document",
        "News Item",
        "Event",
        "Link",
        "Topic",
        "File",
        "Image",
        "RichTopic",
    ]

    EXTRA_SKIP_PATHS = [
        "/Plone/archiv/",
        "/Plone/do-not-import/",
    ]

    # Path from which to continue the export.
    # The export walks the whole site respecting the order.
    # It will ignore everything untill this path is reached.
    PREVIOUS = ""

    def export_content(self):
        return export_content_orig(
            self,
            basedir="/var/lib/zope/json",
            skip_callback=skip_item,
            extra_skip_classname=[],
            extra_skip_id=[],
            extra_skip_paths=EXTRA_SKIP_PATHS,
            batch_start=0,
            batch_size=10000,
            batch_previous_path=PREVIOUS or None,
        )

    def skip_item(item):
        """Return True if the item should be skipped"""
        portal_type = getattr(item, "portal_type", None)
        if portal_type not in EXPORTED_TYPES:
            return True

    def extend_item(obj, item):
        """Extend to work better well with collective.exportimport"""
        from Acquisition import aq_parent
        parent = aq_parent(obj)
        item["parent"] = {
            "@id": parent.absolute_url(),
            "@type": getattr(parent, "portal_type", None),
        }
        if getattr(parent.aq_base, "UID", None) is not None:
            item["parent"]["UID"] = parent.UID()

        return item

To use these create three "External Method" in the ZMI root at the Zope root to use that:

* id: "export_content", module name: "json_methods", function name: "export_content"
* id: "get_item", module name: "json_methods", function name: "get_item"
* id: "extend_item", module name: "json_methods", function name: "extend_item"

Then you can pass the extender to the export using a query-string: http://localhost:8080/Plone/export_content?additional_wrappers=extend_item


Import
******

Two issues need to be dealt with to allow ``collective.exportimport`` to import the data generated by ``collective.jsonify``.

#. The data is in directories instead of in one large json-file.
#. The json is not in the expected format.

Starting with version 1.8 you can pass an iterator to the import.

You need to create a directory-walker that sorts the json-files the right way.
By default it would import them in the order `1.json`, `10.json`, `100.json`, `101.json` and so on.

.. code-block:: python

    from pathlib import Path

    def filesystem_walker(path=None):
        root = Path(path)
        assert(root.is_dir())
        folders = sorted([i for i in root.iterdir() if i.is_dir() and i.name.isdecimal()], key=lambda i: int(i.name))
        for folder in folders:
            json_files = sorted([i for i in folder.glob("*.json") if i.stem.isdecimal()], key=lambda i: int(i.stem))
            for json_file in json_files:
                logger.debug("Importing %s", json_file)
                item = json.loads(json_file.read_text())
                item["json_file"] = str(json_file)
                item = prepare_data(item)
                if item:
                    yield item

The walker takes the path to be the root with one or more directories holding the json-files.
The sorting of the files is done using the number in the filename.

The method ``prepare_data`` modifies the data before passing it to the import.
A very similar task is done by ``collective.exportimport`` during export.

.. code-block:: python

    def prepare_data(item):
        """modify jsonify data to work with c.exportimport"""

        # Drop relationfields or defer the import
        item.pop("relatedItems", None)

        mapping = {
            # jsonify => exportimport
            "_uid": "UID",
            "_type": "@type",
            "_path": "@id",
            "_layout": "layout",
            # AT fieldnames => DX fieldnames
            "excludeFromNav": "exclude_from_nav",
            "allowDiscussion": "allow_discussion",
            "subject": "subjects",
            "expirationDate": "expires",
            "effectiveDate": "effective",
            "creation_date": "created",
            "modification_date": "modified",
            "startDate": "start",
            "endDate": "end",
            "openEnd": "open_end",
            "eventUrl": "event_url",
            "wholeDay": "whole_day",
            "contactEmail": "contact_email",
            "contactName": "contact_name",
            "contactPhone": "contact_phone",
            "imageCaption": "image_caption",
        }
        for old, new in mapping.items():
            item = migrate_field(item, old, new)

        if item.get("constrainTypesMode", None) == 1:
            item = migrate_field(item, "constrainTypesMode", "constrain_types_mode")
        else:
            item.pop("locallyAllowedTypes", None)
            item.pop("immediatelyAddableTypes", None)
            item.pop("constrainTypesMode", None)

        if "id" not in item:
            item["id"] = item["_id"]
        return item


    def migrate_field(item, old, new):
        if item.get(old, _marker) is not _marker:
            item[new] = item.pop(old)
        return item

You can pass the generator ``filesystem_walker`` to the import:

.. code-block:: python

    class ImportAll(BrowserView):

        def __call__(self):
            # ...
            cfg = getConfiguration()
            directory = Path(cfg.clienthome) / "import"

            # import content
            view = api.content.get_view("import_content", portal, request)
            request.form["form.submitted"] = True
            request.form["commit"] = 1000
            view(iterator=filesystem_walker(directory / "mydata"))

            # import default-pages
            import_deferred = api.content.get_view("import_deferred", portal, request)
            import_deferred()


    class ImportDeferred(BrowserView):

        def __call__(self):
            self.title = "Import Deferred Settings (default pages)"
            if not self.request.form.get("form.submitted", False):
                return self.index()

            for brain in api.content.find(portal_type="Folder"):
                obj = brain.getObject()
                annotations = IAnnotations(obj)
                if DEFERRED_KEY not in annotations:
                    continue

                default = annotations[DEFERRED_KEY].pop("_defaultpage", None)
                if default and default in obj:
                    logger.info("Setting %s as default page for %s", default, obj.absolute_url())
                    obj.setDefaultPage(default)
                if not annotations[DEFERRED_KEY]:
                    annotations.pop(DEFERRED_KEY)
            api.portal.show_message("Done", self.request)
            return self.index()

``collective.jsonify`` puts the info on relations, translations and default-pages in the export-file.
You can use the approach to defer imports to deal with that data after all items were imported.
The example ``ImportDeferred`` above uses that approach to set the default pages.

This ``global_obj_hook`` below stores that data in a annotation:

.. code-block:: python

    def global_obj_hook(self, obj, item):
        # Store deferred data in an annotation.
        keys = ["_defaultpage"]
        data = {}
        for key in keys:
            if value := item.get(key, None):
                data[key] = value
        if data:
            annotations = IAnnotations(obj)
            annotations[DEFERRED_KEY] = data


Translations
============

This product has been translated into

- Spanish


Contribute
==========

- Issue Tracker: https://github.com/collective/collective.exportimport/issues
- Source Code: https://github.com/collective/collective.exportimport


Support
-------

If you are having issues, please let us know.


License
-------

The project is licensed under the GPLv2.


Written by
==========

.. image:: ./docs/starzel.png
    :target: https://www.starzel.de
    :alt: Starzel.de
