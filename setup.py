# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/24
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import os, sys
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
try:
  README = open(os.path.join(here, 'README.txt')).read()
except IOError:
  README = ''
try:
  VERSION = open(os.path.join(here, 'VERSION.txt')).read()
except IOError:
  VERSION = 'unknown'

# require python 2.7+
assert(sys.version_info[0] > 2
       or sys.version_info[0] == 2
       and sys.version_info[1] >= 7)

test_requires = [
  'nose                 >= 1.2.1',
  'coverage             >= 3.5.3',
  ]

requires = [
  'pyramid              >= 1.4',
  'distribute           >= 0.6.24',
  ]

# todo: add dependency of format_yaml on requirement:
#         'PyYAML               >= 3.10',

setup(
  name                  = 'pyramid_controllers',
  version               = VERSION,
  description           = 'A pyramid plugin that provides de-centralized hierarchical object dispatch.',
  long_description      = README,
  classifiers           = [
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
    ],
  author                = 'Philip J Grabner, Cadit Health Inc',
  author_email          = 'oss@cadit.com',
  url                   = 'http://github.com/cadithealth/pyramid_controllers',
  keywords              = 'web wsgi pyramid bfg pylons turbogears controller handler object-dispatch request-dispatch',
  packages              = find_packages(),
  include_package_data  = True,
  zip_safe              = True,
  install_requires      = requires,
  tests_require         = test_requires,
  test_suite            = 'pyramid_controllers',
  entry_points          = '',
  license               = 'MIT (http://opensource.org/licenses/MIT)',
  )

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
