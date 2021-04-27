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

Export and import content, members, relations, translations and localroles

Features
========

* Export & Import content
* Export & Import members and groups with their roles
* Export & Import relations
* Export & Import translations
* Export & Import local roles
* Export & Import order (position in parent)

Export supports:

* Plone 4, 5 and 6
* Archetypes and Dexterity
* Python 2 and 3
* plone.app.multilingual, Products.LinguaPlone, raptus.multilanguagefields

Import supports:

* Plone 5.2+, Dexterity, Python 2 and 3, plone.app.multilingual

Usage
=====

Export
------

Use the form with the URL ``/@@export_content``, and select which content type you want to export:

.. image:: ./docs/export.png

The downloaded json-file will have the name of the selected type, e.g. ``Folder.json``.

The exports for members, relations, localroles and relations are linked to in this form but can also be called individually: ``/@@export_members``, ``/@@export_relations``, ``/@@export_localroles``, ``/@@export_translations``, ``/@@export_ordering``.


Import
------

Use the form with the URL ``/@@import_content``, and upload a json-file that you want to import:

.. image:: ./docs/import.png


The imports for members, relations, localroles and relations are linked to in this form but can also be called individually: ``/@@import_members``, ``/@@import_relations``, ``/@@import_localroles``, ``/@@import_translations``, ``/@@import_ordering``..

As a last step in a migration there is another view ``@@reset_modified_date`` that resets the modified date on imported content to the date initially contained in the imported json-file. This is necessary since varous changes during a migration will likely result in a updated modified-date. During import the original is stored as ``obj.modification_date_migrated`` on each new object and this view sets this date.


Use-cases
=========

Migrations
----------

When a in-place-migration is not required you can choose this addon to migrate the most important parts of your site to json and then import it into a new Plone instance of your targeted version:

* Export content from a Plone site (it supports Plone 4 and 5, Archetypes and Dexterity, Python 2 and 3).
* Import the exported content into a new site (Plone 5.2+, Dexterity, Python 3)
* Export and import relations, translations, users, groups and local roles.

It does not support any of the following data from your database:

* content revisions
* registry-settings
* portlets
* theme
* installed addons

Other
-----

You can use this addon to

* Archive your content as json
* Export data to prepare a migration to another system
* Combine content from mutiple plone-sites into one.
* Import a plone-site as a subsite into another.
* Import content from other systems as long as it fits the required format.
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


Use for migrations from Archetypes to Dexterity
-----------------------------------------------

Exporting Archetypes content and importing that as Dexterity content works fine but due to changes in field-names some settings would get lost.
For example the setting to exclude content from the navigation was renamed from ``excludeFromNav`` to ``exclude_from_nav``.

To fix this you can modify the data during import like the following example.

.. code-block:: python

    from collective.exportimport.import_content import ImportContent

    class CustomImportContent(ImportContent):

        def global_dict_hook(self, item):
            if item.get("expirationDate"):
                item["expires"] = item["expirationDate"]
            if item.get("effectiveDate"):
                item["effective"] = item["effectiveDate"]
            if item.get("excludeFromNav"):
                item["exclude_from_nav"] = item["excludeFromNav"]
            return item


Obviously you can use the same approach to handle any changes that you made to your custom content-types.
For more details on customizing see below.


Control creating imported content
---------------------------------

Imported content is initially created with ``invokeFactory`` using portal_type and id of the exported item before deserialing the rest of the data.
You can set additional values by specifying a dict ``factory_kwargs`` that will be passed to the facory.
Like this you can set values on the imported object that are expected to be there by subscribers to IObjectAddedEvent.


Customize export and import
===========================

This addon is meant to be adapted to your requirements and has multiple hooks to do so.


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

        def fixup_request(self):
            """Use this to override stuff befor ethe export starts
            (e.g. force a specific language in the request)."""
            return

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
            return return self.portal['imported_files']

Register it:

.. code-block:: xml

  <browser:page
      name="import_content"
      for="zope.interface.Interface"
      class=".custom_import.CustomImportContent"
      layer="My.Custom.IBrowserlayer"
      permission="cmf.ManagePortal"
      />


Use in code
-----------

It is possible to import data in a setuphandler or upgrade-step:

.. code-block:: python

    from pathlib import Path
    from plone import api

    def full_import():
        portal = api.portal.get()
        request = aq_get(portal, 'REQUEST')

        import_content = api.content.get_view('import_content', portal, request)
        path = Path(os.path.dirname(__file__)) / 'Document.json'
        import_content(jsonfile=path.read_text(), portal_type=item.stem, return_json=True)

        path = Path(os.path.dirname(__file__)) / 'Event.json'
        import_content(jsonfile=path.read_text(), portal_type=item.stem, return_json=True)

        import_translations = api.content.get_view('import_translations', portal, request)
        path = Path(os.path.dirname(__file__)) / 'translations.json'
        import_translations(jsonfile=path.read_text())

        import_relations = api.content.get_view('import_relations', portal, request)
        path = Path(os.path.dirname(__file__)) / 'relations.json'
        import_relations(jsonfile=path.read_text())

        import_members = api.content.get_view('import_members', portal, request)
        path = Path(os.path.dirname(__file__)) / 'members.json'
        import_members(jsonfile=path.read_text())

        import_ordering = api.content.get_view('import_ordering', portal, request)
        path = Path(os.path.dirname(__file__)) / 'ordering.json'
        import_ordering(jsonfile=path.read_text())

        reset_modified = api.content.get_view('reset_modified_date', portal, request)
        reset_modified()


Save all content to ``var/instance/``:

.. code-block:: python

    from plone import api
    from Products.Five import BrowserView

    class ExportAll(BrowserView):

        def __call__(self):
            portal_types = api.portal.get_tool('portal_types').keys()
            export_content = api.content.get_view('export_content', self.context, self.request)
            self.request.form['form.submitted'] = True
            for portal_type in portal_types:
                export_content(portal_type=portal_type, include_blobs=True, download_to_server=True)

Import all content from ``var/instance/import/``:

.. code-block:: python

    from App.config import getConfiguration
    from pathlib import Path
    from plone import api
    from plone.protect.interfaces import IDisableCSRFProtection
    from Products.Five import BrowserView
    from zope.interface import alsoProvides

    import os

    class ImportAll(BrowserView):

        def __call__(self):
            alsoProvides(self.request, IDisableCSRFProtection)
            # Start with folderish content!
            portal_types = [
                'Folder',
                'File',
                'Image',
                'Document',
                'News Item',
                'Event',
                'Collection',
                'Link',
            ]
            instance_path = getConfiguration().clienthome
            import_content = api.content.get_view('import_content', self.context, self.request)
            self.request.form['form.submitted'] = True
            for portal_type in portal_types:
                path = Path(instance_path) / 'import' / f'{portal_type}.json'
                import_content(jsonfile=path.read_text(), portal_type=portal_type, return_json=True)


Written by
----------

.. image:: ./docs/starzel.png
    :target: https://www.starzel.de
    :alt: Starzel.de



Installation
------------

Install collective.exportimport by adding it to your buildout::

    [buildout]

    ...

    eggs =
        collective.exportimport


and then running ``bin/buildout``

You don't need to install the add-on.


Contribute
----------

- Issue Tracker: https://github.com/collective/collective.exportimport/issues
- Source Code: https://github.com/collective/collective.exportimport


Support
-------

If you are having issues, please let us know.


License
-------

The project is licensed under the GPLv2.
