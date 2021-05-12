Using the development buildout
==============================

Create a virtualenv in the package::

    $ virtualenv --clear .

Install requirements with pip::

    $ ./bin/pip install -r requirements.txt

Run buildout::

    $ ./bin/buildout

Start Plone in foreground:

    $ ./bin/instance fg


Running tests
-------------

    $ tox

list all tox environments:

    $ tox -l
    plone43-py27
    plone50-py27
    plone51-py27
    plone52-py27
    plone52-py36
    plone52-py37
    plone52-py38

run a specific tox env:

    $ tox -e plone52-py38

