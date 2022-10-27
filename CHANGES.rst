Changelog
=========


1.7 (unreleased)
----------------

- Filter out 'Discussion Item' in content type export list. Comments have their own export and
  import views. A normal content type export for comments will raise a KeyError when trying to find 
  the parent. (#112)
  [fredvd]

- Be more specific in the import_translation endpoint condition to install in a site with p.a.multilingual 1.x
  [erral]

- Fix importing hidden portlets as visible. (#152)
  [pbauer]

- Use ``Language=all`` when querying TranslationGroup items
  [erral]

- Fix members import, by handling members that already exist.
  [sunew]

- Don't use new_id because a hook can change ``item["id"]``
  [pbauer]

- Support exporting the blob-path without having access to the blobs.
- Set image-variants in html-fields when running @@fix_html targeting in Plone 6.
  [pbauer]


1.6 (2022-10-07)
----------------

- Export and import all group-members (including ldap-users and -groups).
  Previously it only exported users and groups created in Plone.
  [pbauer]

- Support importing content without a UUID (e.g. for importing from an external source).
  The minimal required data is @id, @type, id, and @parent["@id"].
  [pbauer]

- Export only value when serializing vocabulary-based fields instead of token/title.
  [pbauer]

- Improve logging of errors during import.
  [pbauer]

- Add INCLUDE_PATHS to specify which paths only should be imported.
  [pbauer]

- Add import_review_state to allow overriding setting the review_state during import.
  [pbauer]

- Export parent UID and use it to find the container to import.
  [pbauer]

- Move the various export-hooks into update_export_data for readability.
  [pbauer]

- Support export to server by passing ``download_to_server=True`` for all exports (#115).
  [pbauer]

- Add support for adding custom html-fixers to fix_html_in_content_fields.
  [pbauer]


1.5 (2022-04-26)
----------------

- Fix AttributeError for getPhysicalPath when checking parent, issue 123.
  [maurits]

- Export and import redirection tool data.
  [gotcha, Michael Penninck]

- Serialize Products.TALESField fields as raw instead of evaluated expression.
  (useful to export PFG overrides)
  [sauzher]

- Make sure we never change a acquired modification_date or creation_date.
  [pbauer]

- Export and import workflow_history.
  [pbauer]

- Fail gracefully on errors during importing portlets.
  [pbauer]

- Ignore containers where content should be imported to that are non-folderish.
  [pbauer]

- Use catalog instead of ZopeFindAndApply and better logging for export_discussion.
  [pbauer]

- Add converter for long ints (py2 only).
  [pbauer]

- By default no not export linkintegrity relations.
  [pbauer]

- Log detailed exception when exporting content fails.
  [pbauer]

- Add start and finish hooks for export of content.
  [pbauer]

- Rewrite export/import of default pages: Use uuid of default-page instead of id.
  Rewrite getting default_page to fix various issues with translated content.
  [pbauer]

- Add export and import of versions/revisions of content (#105).
  [pbauer]


1.4 (2022-01-07)
----------------

- Fix ``debug`` flag in ``ExportRelations``
  [petschki]

- Deserialize portlet-data using restapi to fix importing RichText.
  [pbauer]

- Fix importing richtext with html-entities. Fixes #99
  [pbauer]

- Preserve links to browser-views by using a custom find_object. Fixes #97
  [pbauer]

- Ignore linkintegrity when importing items with replace-strategy.
  [pbauer]

- Add tests for fix_html.
  [pbauer]


1.3 (2021-12-08)
----------------

- Handle default page of the site root object.
  [fulv]

- Optionally (checkbox) skip existing content on import instead of generating it new with a randomized id.
  [petschki]

- Fix `UnboundLocalError` when calling `import_content` with `return_json` and `server_file`.
  [petschki]

- Add option to make a commit every x items.
  [pbauer]

- Improve logging during import in vairous cases.
  [pbauer]

- Work around case where api.content.get(path=parent_path) raises NotFound instead of returning None.
  [pbauer]

- Keep value of import_to_current_folder.
  [pbauer]

- Fix html unescape in py3.
  [pbauer]

- Fix serializing ATNewsItem image field content.
  [gotcha]

- Migrate eventUrl to event_url (AT to DX).
  [ThibautBorn]

- Log items that cannot be serialized instead of aborting the export.
  [ThibautBorn]

- Add a item_hook to export_localroles.
  [ThibautBorn]

- Fix handling of checkboxes for skip_existing_content and import_to_current_folder.
  [pbauer]

- Move intermediary commit code into commit_hook method to allow overriding.
  [pbauer]

- Add hook global_obj_hook_before_deserializing to modify the created obj before deserializing the data.
  [pbauer]

- Add support to update and to replace existing content during import (#76)
  [pbauer]

- Reindex permissions after importing local roles.
  [pbauer]

- Add export/import for constrains but import content without checking constrains or permissions (#71).
  [pbauer]


1.2 (2021-10-11)
----------------

- Prevent creating content in a different Plone Site in the same database (#52).
  In general, cleanup parent paths when in development on localhost.
  [maurits]

- Read environment variable ``COLLECTIVE_EXPORTIMPORT_CENTRAL_DIRECTORY`` (#51).
  When set, this is used for storing an export file and getting an import file.
  This is useful for sharing content between multiple Plone Sites on the same server.
  [maurits]

- Unescape html entities and line-breaks when importing comments (#43).
  [pbauer]

- Export and import complete sites or content trees with configurable types, depth and path (#40).
  [pbauer]

- Added option to export blobs as blob paths (#50).
  [pbauer, maurits]

- Fixed creating missing folder structure (#45).
  [maurits]

- Export and import portlets (#39).
  [pbauer]

- Export content and write to file using a generator/yield. This avoids memory ballooning to the size of the exported file (#41).
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
