#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from __future__ import print_function

import sys
from setuptools import setup, find_packages

with open('README.rst') as file:
    long_description = file.read()

config = {
    'name' : 'django-s3-cache',
    'version' : '3.0.0',
    'packages' : find_packages(),
    'author' : 'Alexander Todorov',
    'author_email' : 'atodorov@MrSenko.com',
    'license' : 'BSD',
    'description' : 'Amazon Simple Storage Service (S3) cache backend for Django',
    'long_description' : long_description,
    'url' : 'https://github.com/atodorov/django-s3-cache',
    'keywords' : ['Amazon', 'S3', 'Django', 'cache'],
    'classifiers' : [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Framework :: Django',
        'Framework :: Django :: 5.0',
        'Framework :: Django :: 5.1',
        'Framework :: Django :: 5.2',
    ],
    'python_requires': '>=3.10',
    'zip_safe' : False,
    'install_requires' : ['boto3>=1.26.0', 'django-storages>=1.14', 'Django>=5.2,<6.0'],
}

if (len(sys.argv) >= 2) and (sys.argv[1] == '--requires'):
    for req in config['install_requires']:
        print(req)
else:
    setup(**config)
