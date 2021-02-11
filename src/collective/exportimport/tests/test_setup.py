# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from collective.exportimport.testing import COLLECTIVE_EXPORTIMPORT_INTEGRATION_TESTING  # noqa: E501

import unittest


try:
    from Products.CMFPlone.utils import get_installer
except ImportError:
    get_installer = None


class TestSetup(unittest.TestCase):
    """Test that collective.exportimport is properly installed."""

    layer = COLLECTIVE_EXPORTIMPORT_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if collective.exportimport is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'collective.exportimport'))

    def test_browserlayer(self):
        """Test that ICollectiveExportimportLayer is registered."""
        from collective.exportimport.interfaces import (
            ICollectiveExportimportLayer)
        from plone.browserlayer import utils
        self.assertIn(
            ICollectiveExportimportLayer,
            utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = COLLECTIVE_EXPORTIMPORT_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.installer.uninstallProducts(['collective.exportimport'])
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if collective.exportimport is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'collective.exportimport'))

    def test_browserlayer_removed(self):
        """Test that ICollectiveExportimportLayer is removed."""
        from collective.exportimport.interfaces import \
            ICollectiveExportimportLayer
        from plone.browserlayer import utils
        self.assertNotIn(
            ICollectiveExportimportLayer,
            utils.registered_layers())
