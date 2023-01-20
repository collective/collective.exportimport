# -*- coding: utf-8 -*-
"""Installer for the collective.exportimport package."""

from setuptools import find_packages
from setuptools import setup

import sys


long_description = "\n\n".join(
    [
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]
)

install_requires = [
    "setuptools",
    "plone.api >= 1.8.4",
    "hurry.filesize",
    "ijson",
    "six",
]

if sys.version_info[0] < 3:
    install_requires.append("beautifulsoup4 < 4.10")
    install_requires.append("plone.restapi < 8.0.0")
    # plone.restapi depends on plone.schema, which depends on jsonschema,
    # which has a Py3-only release since September 2021.
    install_requires.append("jsonschema < 4")
    install_requires.append("pyrsistent < 0.16.0")
else:
    install_requires.append("plone.restapi")
    install_requires.append("beautifulsoup4")


setup(
    name="collective.exportimport",
    version="1.7",
    description="An add-on for Plone to Export and import content, members, relations, translations and localroles.",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 4.3",
        "Framework :: Plone :: 5.0",
        "Framework :: Plone :: 5.1",
        "Framework :: Plone :: 5.2",
        "Framework :: Plone :: 6.0",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="Python Plone CMS",
    author="Philip Bauer (for starzel.de)",
    author_email="info@starzel.de",
    url="https://github.com/collective/collective.exportimport",
    project_urls={
        "PyPI": "https://pypi.python.org/pypi/collective.exportimport",
        "Source": "https://github.com/collective/collective.exportimport",
        "Tracker": "https://github.com/collective/collective.exportimport/issues",
        "Documentation": "https://github.com/collective/collective.exportimport#readme",
    },
    license="GPL version 2",
    packages=find_packages("src", exclude=["ez_setup"]),
    namespace_packages=["collective"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*",
    install_requires=install_requires,
    extras_require={
        "test": [
            "plone.app.testing",
            # needed as test dependency of plone.app.event:
            "plone.app.robotframework",
            "plone.app.contenttypes",
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = collective.exportimport.locales.update:update_locale
    """,
)
