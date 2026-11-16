# -*- coding: utf-8 -*-
"""Init and utils."""
from zope.i18nmessageid import MessageFactory


try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as get_version
except ImportError:  # Python 2.7 and Python 3 < 3.8
    from pkg_resources import DistributionNotFound as PackageNotFoundError  # noqa: F401
    from pkg_resources import get_distribution

    def get_version(name):
        return get_distribution(name).version


_ = MessageFactory("collective.exportimport")
