# -*- coding: utf-8 -*-
"""Installer for the collective.exportimport package."""

from setuptools import find_packages
from setuptools import setup


long_description = "\n\n".join(
    [
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]
)


setup(
    name="collective.exportimport",
    version="1.1.dev0",
    description="An add-on for Plone to Export and import content, members, relations, translations and localroles.",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 5 - Stable",
        "Intended Audience :: Developers",
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 4.2",
        "Framework :: Plone :: 5.0",
        "Framework :: Plone :: 5.1",
        "Framework :: Plone :: 5.2",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
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
        # 'Documentation': 'https://collective.exportimport.readthedocs.io/en/latest/',
    },
    license="GPL version 2",
    packages=find_packages("src", exclude=["ez_setup"]),
    namespace_packages=["collective"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires="==2.7, >=3.6",
    install_requires=[
        "setuptools",
        "plone.api>=1.8.4",
        "plone.restapi",
        "hurry.filesize",
        "plone.app.contenttypes",
        "z3c.relationfield",
    ],
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = collective.exportimport.locales.update:update_locale
    """,
)
