# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.util
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/09/13
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
class adict(dict):
  '''
  A dict subclass that allows attribute access to be synonymous with
  item access, e.g. ``mydict.attribute == mydict['attribute']``. It
  also provides two extra methods, :meth:`pick` and :meth:`omit`.
  '''
  def __getattr__(self, key):
    if key.startswith('__') and key.endswith('__'):
      # note: allows an adict to be pickled with protocols 0, 1, and 2
      #       which treat the following specially:
      #         __getstate__, __setstate__, __slots__, __getnewargs__
      return dict.__getattr__(self, key)
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
  def pick(self, *args):
    return adict({k: v for k, v in self.iteritems() if k in args})
  def omit(self, *args):
    return adict({k: v for k, v in self.iteritems() if k not in args})
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
def pick(source, *keys, **kw):
  '''
  Given a `source` dict or object, returns a new dict that contains a
  subset of keys (each key is a separate positional argument) and/or
  where each key is a string and has the specified `prefix`, specified
  as a keyword argument. Also accepts the optional keyword argument
  `dict` which must be a dict-like class that will be used to
  instantiate the returned object. Note that if `source` is an object
  without an `items()` iterator, then the selected keys will be
  extracted as attributes. The `prefix` keyword only works with
  dict-like objects.
  '''
  rettype = kw.pop('dict', dict)
  prefix = kw.pop('prefix', None)
  if kw:
    raise ValueError('invalid pick keyword arguments: %r' % (kw.keys(),))
  if not source:
    return rettype()
  if prefix is not None:
    source = {k[len(prefix):]: v
              for k, v in source.items()
              if getattr(k, 'startswith', lambda x: False)(prefix)}
  if len(keys) <= 0:
    return rettype(source)
  try:
    return rettype({k: v for k, v in source.items() if k in keys})
  except AttributeError:
    return rettype({k: getattr(source, k) for k in keys if hasattr(source, k)})

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
