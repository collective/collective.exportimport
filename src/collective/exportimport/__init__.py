"""Init and utils."""

from importlib.metadata import PackageNotFoundError  # noqa: F401
from importlib.metadata import version as get_version  # noqa: F401
from zope.i18nmessageid import MessageFactory

_ = MessageFactory("collective.exportimport")
