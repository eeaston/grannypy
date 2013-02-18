#!/usr/bin/env python
from setuptools import setup

with open('README.rst') as ld_file:
    long_description = ld_file.read()

kw = dict(
    name = "grannypy",
    version = "0.1",
    description = "Sucks packages from one Python package index, builds a binary egg and imports it into another.",
    long_description = long_description,
    author = "Edward Easton",
    author_email = "eeaston@gmail.com",
    maintainer = "Edward Easton",
    maintainer_email = "eeaston@gmail.com",
    url = "http://github.com/eeaston/grannypy",
    license = "MIT License",
    py_modules = ['granny'],
    install_requires = ['distribute', 'docopt', 'requests'],
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)


if __name__ == '__main__':
    setup(**kw)
