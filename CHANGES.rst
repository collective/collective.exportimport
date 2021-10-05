Changelog
=========


1.2 (unreleased)
----------------

- Fixed creating missing folder structure.  [maurits]

- Export portlets.
  [pbauer]

- Export content and write to file using a generator/yield. This avoids memory ballooning to the size of the exported file.
  [fredvd]


1.1 (2021-08-02)
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

- Fix @id of collections and parents of subcollections. Fix #30
  [pbauer]

- Fix use in Plone 4.3 with dexterity but without z3c.relationfield.
  [maurits]

- Add export and import for discussions/comments.
  [pbauer]

- Add option to fix collection queries after import.
  [thomasmassmann]

- Reset Creation Date. Fix #29
  [pbauer]

- Remove custom serializer for relations beacuse of ConfigurationConflictError with restapi.
  Relations are dropped anyway in update_data_for_migration when using the default setting.
  [pbauer]

- Migrate batch size for topics.
  [pbauer]

- Fix issue of reusing the previous container when no container for a item could be found.
  [pbauer]

- Add hook self.finish() to do things after importing one file.
  [pbauer]

- Fix installation with older versions of setuptools (#35)
  [pbauer]

- Fix installation using pip (#36)
  [ericof]

- Do not constrain exportable FTIs to allow export of types as CalendarXFolder or ATTopic Criteria.
  [pbauer]

- Add hook self.start() to do things after importing one file.
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
