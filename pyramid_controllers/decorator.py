# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.decorator
# desc: provides method decorators to control controller method exposure.
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2012/10/26
# copy: (C) Copyright 2012 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import types, inspect
from .util import adict, isstr

#------------------------------------------------------------------------------
class Decoration(object):
  def __init__(self):
    self.fiddle  = []
    self.expose  = []
    self.index   = []
    self.lookup  = []
    self.default = []

#------------------------------------------------------------------------------
class Decorator(object):
  attribute = None
  def __init__(self, **kw):
    self.kw = adict(kw)
  def __call__(self, wrapped):
    if not hasattr(wrapped, '__pyramid_controllers__'):
      wrapped.__pyramid_controllers__ = Decoration()
    self.enhance(wrapped, wrapped.__pyramid_controllers__, self.kw)
    return wrapped
  def enhance(self, wrapped, decoration, kw):
    getattr(decoration, self.attribute).append(kw)

#------------------------------------------------------------------------------
class ExposeDecorator(Decorator):
  attribute = 'expose'
  def enhance(self, wrapped, decoration, kw):
    if kw.name and isstr(kw.name):
      kw.name = [kw.name]
    if kw.ext:
      if kw.name:
        raise ValueError('@expose collision: "ext" and "name" are mutually exclusive')
      kw = adict(kw)
      if isstr(kw.ext):
        kw.name = [wrapped.__name__ + '.' + kw.ext]
      else:
        kw.name = [wrapped.__name__ + '.' + e for e in kw.ext]
      del kw.ext
    super(ExposeDecorator, self).enhance(wrapped, decoration, kw)

#------------------------------------------------------------------------------
class FiddleDecorator(Decorator):  attribute = 'fiddle'
class IndexDecorator(Decorator):   attribute = 'index'
class LookupDecorator(Decorator):  attribute = 'lookup'
class DefaultDecorator(Decorator): attribute = 'default'

#------------------------------------------------------------------------------
def makeDecorator(klass, doc=None):
  def decorator(*args, **kw):
    if len(args) == 1 and len(kw) == 0 and type(args[0]) == types.FunctionType:
      return klass()(args[0])
    return klass(*args, **kw)
  decorator.__doc__ = doc
  return decorator

#------------------------------------------------------------------------------
expose = makeDecorator(ExposeDecorator, doc='''\

  Decorates a :class:`Controller` method to indicate that it can be
  invoked and traversed by the request dispatcher. Accepts the
  following optional parameters:

  :param renderer:

    Specifies the renderer to use.

  :param name:

    Specifies the name or list of names that this method exposes for
    dispatch. This is typically used when the external URL comprises
    special characters or reserved words (such as ``def``). Note that
    if this option is used, then the normal method name itself will no
    longer be exposed unless explicitly listed.

  :param ext:

    Specifies the extension or list of extensions that this method
    must be appended to for dispatch. This is typically used to
    associate different renderers for different extensions. Note that
    this option cannot be used in conjunction with `name` and that the
    bare method name itself will no longer be exposed unless
    explicitly listed.

  Examples::

    class MyController(Controller):

      @expose
      def action(self, request):
        return 'reaction'

      @expose(renderer='json')
      def api(self, request):
        return dict(state='enabled')

      @expose(ext='html', renderer='module:path/to/template')
      @expose(ext=('json', 'js'), renderer='json')
      def resource(self, request):
        return dict(count=12)

  ''')

# todo: add documentation for each decorator...
index   = makeDecorator(IndexDecorator)
lookup  = makeDecorator(LookupDecorator)
default = makeDecorator(DefaultDecorator)
fiddle  = makeDecorator(FiddleDecorator)

#------------------------------------------------------------------------------
class ExposeDefaultsDecorator(object):
  def __init__(self, **kw):
    self.kw = adict(kw)
  def __call__(self, wrapped):
    for name, attr in inspect.getmembers(wrapped):
      apc = getattr(attr, '__pyramid_controllers__', None)
      if not apc:
        continue
      for dectype in ('expose', 'index', 'default'):
        for spec in getattr(apc, dectype, []):
          if 'renderer' in self.kw:
            if 'renderer' not in spec:
              spec.renderer = self.kw.renderer
      for dectype in ('expose',):
        for spec in getattr(apc, dectype, []):
          if 'ext' in self.kw:
            if 'name' not in spec and 'ext' not in spec:
              if isstr(self.kw.ext):
                spec.name = [name + '.' + self.kw.ext]
              else:
                spec.name = [name + '.' + e for e in self.kw.ext]
    return wrapped

#------------------------------------------------------------------------------
def expose_defaults(*args, **kw):
  '''
  Decorates a :class:`Controller` with default parameters that are
  used by the @expose, @index, and @default method decorators. In the
  following example, '/types' and '/people' will receive a
  JSON-encoded response created by the 'json' renderer, but '/html'
  will receive the output of the ``templates/show.mako`` template that
  took the output of the other two methods as input::

    @expose_defaults(renderer='json')
    class JsonInterface(Controller):

      @index
      def types(self, request):
        return [dict(name='people'), dict(name='books')]

      @expose
      def people(self, request):
        return [dict(name='Jane'), dict(name='John')]

      @expose(renderer='module:templates/list.mako')
      def html(self, request):
        return dict(people=self.people(request), types=self.types(request))

  Currently, the following parameters can be used in @expose_defaults:

  :param renderer:

    any @index, @default, and @expose decorated methods that do not
    have a pre-existing `renderer` definition will inherit this value.

  :param ext:

    any @expose decorated methods that have neither a `name` or an
    `ext` definition will inherit this value.

  '''
  if len(args) == 1 and len(kw) == 0 and type(args[0]) == types.FunctionType:
    return ExposeDefaultsDecorator()(args[0])
  return ExposeDefaultsDecorator(*args, **kw)

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
