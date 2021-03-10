# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import (
    applyProfile,
    FunctionalTesting,
    IntegrationTesting,
    PloneSandboxLayer,
)
from plone.testing import z2

import collective.exportimport


class CollectiveExportimportLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=collective.exportimport)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "collective.exportimport:default")


COLLECTIVE_EXPORTIMPORT_FIXTURE = CollectiveExportimportLayer()


COLLECTIVE_EXPORTIMPORT_INTEGRATION_TESTING = IntegrationTesting(
    bases=(COLLECTIVE_EXPORTIMPORT_FIXTURE,),
    name="CollectiveExportimportLayer:IntegrationTesting",
)


COLLECTIVE_EXPORTIMPORT_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(COLLECTIVE_EXPORTIMPORT_FIXTURE,),
    name="CollectiveExportimportLayer:FunctionalTesting",
)


COLLECTIVE_EXPORTIMPORT_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        COLLECTIVE_EXPORTIMPORT_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="CollectiveExportimportLayer:AcceptanceTesting",
)
