from collective.exportimport.import_content import ImportContent

import unittest


class NoIncludeAndNoDrop(ImportContent):
    pass


class IncludeAndNoDrop(ImportContent):
    INCLUDE_PATHS = ['/Plone/include']


class NoIncludeAndDrop(ImportContent):
    DROP_PATHS = ['/Plone/drop']


class IncludeAndDrop(ImportContent):
    INCLUDE_PATHS = ['/Plone/include']
    DROP_PATHS = ['/Plone/include/drop', '/Plone/drop']


class TestDropAndInclude(unittest.TestCase):
    def test_no_include_and_no_drop(self):
        view = NoIncludeAndNoDrop(None, None)
        self.assertFalse(view.should_drop('/Plone/testdocument'))
        self.assertTrue(view.must_process('/Plone/testdocument'))

    def test_include_and_no_drop(self):
        view = IncludeAndNoDrop(None, None)
        self.assertFalse(view.should_drop('/Plone/testdocument'))
        self.assertFalse(view.should_include('/Plone/testdocument'))
        self.assertTrue(view.should_include('/Plone/include'))
        self.assertTrue(view.should_include('/Plone/include/testdocument'))
        self.assertFalse(view.must_process('/Plone/testdocument'))
        self.assertTrue(view.must_process('/Plone/include'))
        self.assertTrue(view.must_process('/Plone/include/testdocument'))

    def test_no_include_and_drop(self):
        view = NoIncludeAndDrop(None, None)
        self.assertFalse(view.should_drop('/Plone/testdocument'))
        self.assertTrue(view.should_drop('/Plone/drop'))
        self.assertTrue(view.should_drop('/Plone/drop/testdocument'))

        self.assertFalse(view.should_include('/Plone/drop/testdocument'))
        self.assertFalse(view.should_include('/Plone/testdocument'))

        self.assertFalse(view.must_process('/Plone/drop'))
        self.assertTrue(view.must_process('/Plone/testdocument'))
        self.assertFalse(view.must_process('/Plone/drop/testdocument'))

    def test_include_and_drop(self):
        view = IncludeAndDrop(None, None)

        self.assertTrue(view.should_drop('/Plone/drop'))
        self.assertFalse(view.should_drop('/Plone/testdocument'))
        self.assertTrue(view.should_drop('/Plone/drop/testdocument'))
        self.assertFalse(view.should_drop('/Plone/include/testdocument'))
        self.assertTrue(view.should_drop('/Plone/include/drop/testdocument'))
        self.assertFalse(view.should_drop('/Plone/include'))
        self.assertTrue(view.should_drop('/Plone/include/drop'))

        self.assertFalse(view.should_include('/Plone/drop'))
        self.assertFalse(view.should_include('/Plone/testdocument'))
        self.assertFalse(view.should_include('/Plone/drop/testdocument'))
        self.assertTrue(view.should_include('/Plone/include/testdocument'))
        self.assertTrue(view.should_include('/Plone/include/drop/testdocument'))
        self.assertTrue(view.should_include('/Plone/include'))
        self.assertTrue(view.should_include('/Plone/include/drop'))

        self.assertFalse(view.must_process('/Plone/drop'))
        self.assertFalse(view.must_process('/Plone/testdocument'))
        self.assertFalse(view.must_process('/Plone/drop/testdocument'))
        self.assertTrue(view.must_process('/Plone/include/testdocument'))
        self.assertFalse(view.must_process('/Plone/include/drop/testdocument'))
        self.assertTrue(view.must_process('/Plone/include'))
        self.assertFalse(view.must_process('/Plone/include/drop'))
