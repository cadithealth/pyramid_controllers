# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.util
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import sys, pkg_resources
from .adict import adict, pick

PY3 = sys.version_info[0] == 3

#------------------------------------------------------------------------------
def getMethod(request):
  name = request.params.get('_method', '').strip()
  if len(name) > 0:
    return name.upper()
  return request.method

#------------------------------------------------------------------------------
def getVersion(package='pyramid_controllers', default='unknown'):
  try:
    return pkg_resources.require(package)[0].version
  except:
    return default

#------------------------------------------------------------------------------
if PY3:
  def isstr(obj):
    return isinstance(obj, str)
else:
  def isstr(obj):
    return isinstance(obj, basestring)

#------------------------------------------------------------------------------
def isiter(obj):
  return hasattr(obj, '__iter__') and not isstr(obj)

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
