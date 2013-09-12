#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/24
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import os, sys, re
from setuptools import setup, find_packages

# require python 2.7+
if sys.hexversion < 0x02070000:
  raise RuntimeError('This package requires python 2.7 or better')

heredir = os.path.abspath(os.path.dirname(__file__))
def read(*parts):
  try:    return open(os.path.join(heredir, *parts)).read()
  except: return ''

test_dependencies = [
  'nose                 >= 1.2.1',
  'coverage             >= 3.5.3',
  'WebTest              >= 1.4.0',
  ]

dependencies = [
  'distribute           >= 0.6.24',
  'argparse             >= 1.2.1',
  'pyramid              >= 1.4.2',
  'six                  >= 1.4.1',

  # todo: add optional dependency of PyYAML if format==yaml is desired
  # 'PyYAML               >= 3.10',

  ]

entrypoints = {
  }

classifiers = [
  'Development Status :: 4 - Beta',
  #'Development Status :: 5 - Production/Stable',
  'Intended Audience :: Developers',
  'Programming Language :: Python',
  'Framework :: Pyramid',
  'Environment :: Console',
  'Environment :: Web Environment',
  'Operating System :: OS Independent',
  'Topic :: Internet',
  'Topic :: Software Development',
  'Topic :: Internet :: WWW/HTTP',
  'Topic :: Internet :: WWW/HTTP :: WSGI',
  'Topic :: Software Development :: Libraries :: Application Frameworks',
  'Natural Language :: English',
  'License :: OSI Approved :: MIT License',
  'License :: Public Domain',
  ]

setup(
  name                  = 'pyramid_controllers',
  version               = '0.3.17',
  description           = 'A pyramid plugin that provides de-centralized hierarchical object dispatch.',
  long_description      = read('README.rst'),
  classifiers           = classifiers,
  author                = 'Philip J Grabner, Cadit Health Inc',
  author_email          = 'oss@cadit.com',
  url                   = 'http://github.com/cadithealth/pyramid_controllers',
  keywords              = 'web wsgi pyramid bfg pylons turbogears controller handler object-dispatch request-dispatch',
  packages              = find_packages(),
  platforms             = ['any'],
  include_package_data  = True,
  zip_safe              = True,
  install_requires      = dependencies,
  tests_require         = test_dependencies,
  test_suite            = 'pyramid_controllers',
  entry_points          = entrypoints,
  license               = 'MIT (http://opensource.org/licenses/MIT)',
  )

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
