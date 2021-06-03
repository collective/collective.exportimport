Changelog
=========


1.1 (unreleased)
----------------

- Add option to import file from server.
  [maurits]

- Missing ``</form>`` closing tag in ``export_content.pt``
  [petschki]

- Support disabled aquisition of local roles during export/import of local roles.
  [pbauer]

- Use unrestrictedSearchResults to actually export all content.
  [pbauer]

- Add commit message after importing one type.
  [pbauer]

- Fix getting container for some cases.
  [pbauer]

- Fix use in Plone 4.3 without dexterity, zc.relation or plone.app.contenttypes.
  [pbauer]

1.0 (2021-04-27)
----------------

- Support setting values with ``factory_kwargs`` when creating instances during import.
  This can be used to set values that need to be there during subscribers to IObjectAddedEvent.
  [pbauer]


1.0b1 (2021-03-26)
------------------

- Add option to save export on server.
  [pbauer]

- Fix issues in import_relations and import_ordering.
  [pbauer]

- Use links to other exports in export_content for easier override.
  [pbauer]

- Add support for exporting LinguaPlone translations.
  [pbauer]


1.0a2 (2021-03-11)
------------------

- Simplify package structure and remove all unneeded files
  [pbauer]

- Add export/import for position in parent
  [pbauer]


1.0a1 (2021-03-10)
------------------

- Initial release.
  [pbauer]
