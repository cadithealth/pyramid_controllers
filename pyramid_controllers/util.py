# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.util
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import sys, pkg_resources

PY3 = sys.version_info[0] == 3

#------------------------------------------------------------------------------
class adict(dict):
  def __getattr__(self, key):
    return self.get(key, None)
  def __setattr__(self, key, value):
    self[key] = value
    return self
  def __delattr__(self, key):
    if key in self:
      del self[key]
    return self
  def update(self, *args, **kw):
    args = [e for e in args if e]
    dict.update(self, *args, **kw)
    return self
  @staticmethod
  def __dict2adict__(subject, recursive=False):
    if isinstance(subject, list):
      if not recursive:
        return subject
      return [adict.__dict2adict__(val, True) for val in subject]
    if not isinstance(subject, dict):
      return subject
    ret = adict(subject)
    if not recursive:
      return ret
    for key, val in ret.items():
      ret[key] = adict.__dict2adict__(val, True)
    return ret

#------------------------------------------------------------------------------
def pick(source, *args):
  ret = adict()
  for arg in args:
    if arg in source:
      ret[arg] = source[arg]
  return ret

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
