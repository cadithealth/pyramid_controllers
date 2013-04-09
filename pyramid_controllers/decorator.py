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

PCATTR = '__pyramid_controllers__'
# todo: fix this so that both attributes can use the same name
PCCTRLATTR = '__pyramid_controllers_class__'

#------------------------------------------------------------------------------
class MethodDecoration(object):
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
    if not hasattr(wrapped, PCATTR):
      setattr(wrapped, PCATTR, MethodDecoration())
    self.enhance(wrapped, getattr(wrapped, PCATTR), self.kw)
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

      @expose(ext='html', renderer='mymodule:path/to/template.mako')
      @expose(ext=('json', 'js'), renderer='json')
      def resource(self, request):
        return dict(count=12)

  ''')

#------------------------------------------------------------------------------
index = makeDecorator(IndexDecorator, doc='''\

  Decorates a :class:`Controller` method to indicate that it will
  handle requests that resolve to the controller, but do not have any
  further path arguments. Accepts the following optional parameters:

  :param forceSlash:

    Boolean that controls whether or not an index request that does
    not have a trailing slash ("/") should be 302 redirected to a
    version of the URL with a trailing slash. The default behaviour is
    controlled by the :class:`pyramid_controllers.Dispatcher` in
    effect for the current request (which, by default, is set to
    true).

  :param renderer:

    Specifies the renderer to use.

  Examples::

    class SubController(Controller):

      @index(forceSlash=False)
      def index(self, request):
        # responds with a 200 to both '/sub' and '/sub/'
        return 'sub-index'

    class RootController(Controller):

      sub = SubController()

      @index
      def index(self, request):
        return 'index'

  ''')

#------------------------------------------------------------------------------
default = makeDecorator(DefaultDecorator, doc='''\

  Decorates a :class:`Controller` method to indicate that it will
  handle requests that the pyramid_controllers framework could not
  otherwise find an appropriate handler for. Without a default
  handler, a "404 Not Found" response would be generated. The default
  handler is passed the standard `request` parameter, and then all of
  the remaining path components as positional arguments, and is
  expected to complete the handling of the request - i.e. to generate
  a response. The ``@default`` decorator accepts the following
  optional parameters:

  :param renderer:

    Specifies the renderer to use.

  Examples::

    class SubController(Controller):

      @expose
      def method(self, request): return 'reachable'

      def unreacheable(self, request):
        return 'not-exposed'

      @default(renderer='mymodule:path/to/template.mako')
      def default(self, request, current, *rem):
        if len(rem) > 0:
          raise HTTPNotFound()
        return dict(page=current)

    class RootController(Controller):

      sub = SubController()

      @default
      def default(self, request, *paths):
        return 'Remaining: ' + ', '.join(paths)

  In this controller configuration, the following requests would be
  handled as follows:

  * ``/zig/zag``:
    Response: ``Remaining: zig, zag``.

  * ``/sub/foo``:

    Response: the output from the ``path/to/template.mako`` template
    with the dictionary ``{'page': 'foo'}`` as template data.

  * ``/sub/foo/bar``:

    Response: "404 Not Found" error.

  Note that ``@lookup`` decorated methods take precedence.
  ''')

#------------------------------------------------------------------------------
lookup = makeDecorator(LookupDecorator, doc='''\

  Similar to the ``@default`` decorator, this indicates that the
  method should be called for any request that did not match standard
  request dispatching. Unlike the default handler, however, this
  method is **NOT** expected to handle the request, i.e. it is not
  intended to return a Response (or equivalent) object. Instead, it is
  expected to determine the *next* controller to invoke in the process
  of walking the request URL path components. It should return a tuple
  of ``(Controller, remainingPaths)``, where `remainingPaths` is a
  list of path elements that were not consumed (the @lookup method can
  consume as many elements as needed). The @lookup decorator itself
  does not currently accept any parameters.

  The lookup handler is typically used for dynamically resolved URL
  components which identify, usually, an object ID. This is the most
  common when creating "RESTful" URLs. For example, given the URL
  pattern ``/resource/RESOURCE_ID/action``, a @lookup handler could be
  used for the ``RESOURCE_ID`` section. An implementation of this
  example::

    class ResourceController(Controller):

      @expose
      def action(self, request):
        return 'Action taken on object ID "%s".' % (request.res.id,)

    class ResourceDispatcher(Controller):

      RESOURCE_ID = ResourceController(expose=False)

      @lookup
      def lookup(self, request, res_id, *rem):
        request.res = get_resource_by_id(res_id)
        if not request.res:
          raise HTTPNotFound()
        return (self.RESOURCE_ID, rem)

    class RootController(Controller):

      resource = ResourceDispatcher()

  In this example, assuming that ``get_resource_by_id`` returns an
  object by ID, the request for URL ``/resource/15/action`` will
  receive the response ``Action taken on object ID "15".`` (given that
  the object with ID "15" exists).
  ''')

#------------------------------------------------------------------------------
fiddle = makeDecorator(FiddleDecorator, doc='''\

  The ``@fiddle`` decorator indicates that the decorated
  :class:`Controller` method should be called before dispatch to any
  handlers or sub-controllers. This is typically done to implement
  access control in a custom Controller base class.

  Example::

    class BaseController(Controller):

      @fiddle
      def fiddle(self, request):
        require = getattr(self, 'require', None)
        if require == 'valid-user':
          if not is_valid_user(request):
            raise HTTPUnauthorized()

    class MyController(Controller):

      require = 'valid-user'

      @expose
      def action(self, request):
        return 'You are a valid user!'

  ''')


#------------------------------------------------------------------------------
class ClassDecoration(object):
  def __init__(self):
    self.defaults = []
    self.meta     = None
  def apply(self, wrapped):
    for defs in reversed(self.defaults):
      for name, attr in inspect.getmembers(wrapped):
        apc = getattr(attr, PCATTR, None)
        if not apc:
          continue
        for dectype in ('expose', 'index', 'default'):
          for spec in getattr(apc, dectype, []):
            if 'renderer' in defs:
              if 'renderer' not in spec:
                spec.renderer = defs.renderer
        for dectype in ('expose',):
          for spec in getattr(apc, dectype, []):
            if 'ext' in defs:
              if 'name' not in spec and 'ext' not in spec:
                if isstr(defs.ext):
                  spec.name = [name + '.' + defs.ext]
                else:
                  spec.name = [name + '.' + e for e in defs.ext]

#------------------------------------------------------------------------------
class ExposeDefaultsDecorator(object):
  def __init__(self, **kw):
    self.kw = adict(kw)
  def __call__(self, wrapped):
    if not hasattr(wrapped, PCCTRLATTR):
      setattr(wrapped, PCCTRLATTR, ClassDecoration())
    pc = getattr(wrapped, PCCTRLATTR)
    pc.defaults.append(self.kw)
    pc.apply(wrapped)
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
