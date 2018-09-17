# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.dispatcher
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2012/10/24
# copy: (C) Copyright 2012 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
``pyramid_controllers.dispatcher`` is the actual request dispatching
algorithm of the controller-based request dispatch mechanism.
'''

# todo: currently, an index request (ie. a trailing slash) to a
#       controller that does not have an @index, but *does* have
#       an @default receives ``None`` as the current path element
#       being requested instead of ''... is that what it should be?...

import os.path
import types
import re
import inspect
import types

import six
from six.moves import urllib
from pyramid.exceptions import ConfigurationError
from pyramid.response import Response
from pyramid.httpexceptions import HTTPException, HTTPError
from pyramid.httpexceptions import HTTPFound, HTTPNotFound, HTTPForbidden
from pyramid.renderers import render_to_response

from .controller import Controller
from . import decorator
from .util import adict, isstr

path2meth = re.compile('[^a-zA-Z0-9_]')

#------------------------------------------------------------------------------
class ControllerError(Exception): pass

#------------------------------------------------------------------------------
def getDispatcherFromStack():
  # TODO: is this efficient? is this cross-platform? is this causing
  #       reference cycles?... oh dear! make sure this is really the
  #       best way.
  for frame in inspect.stack():
    d = frame[0].f_locals.get('self', None)
    if isinstance(d, Dispatcher):
      return d
  return None

#------------------------------------------------------------------------------
class Dispatcher(object):
  '''
  The `Dispatcher` object is in charge of the mechanics of traversing
  and evaluating a pyramid-controllers Controller hierarchy.
  '''

  PCATTR = '__pyramid_controllers__'
  NAME_INDEX   = ''
  NAME_DEFAULT = '*'
  NAME_LOOKUP  = '...'

  #----------------------------------------------------------------------------
  def __init__(self,
               defaultForceSlash=True, raiseType=HTTPError, autoDecorate=True,
               defaultDashUnder=True,
               raiseErrors=None, # DEPRECATED
               *args, **kw):
    '''
    Creates a new Dispatcher for controller hierarchy traversal and
    request dispatching. Accepts the following parameters:

    :Parameters:

    defaultForceSlash : bool, default: true

      Set the default value of @index's `forceSlash` parameter, which
      defaults to ``True``, i.e. index requests that do not have a
      trailing slash (``/``) will receive a 302 redirect with the
      slash appended.

    defaultDashUnder : bool, default: true

      Set the default value of @expose's `dashUnder` parameter, which
      defaults to ``True``, i.e. underscore-separated words in the
      method name will also match the dash-separated version. Note
      that explicitly setting the `name` parameter will make
      `dashUnder` be ignored.

    raiseType : { type-or-class, list(type-or-class) }, default: HTTPError

      Any responses or raised exceptions that are subclasses of
      `pyramid.httpexceptions.HTTPException` are handled specially: if
      they are subclasses of `raiseType` (which defaults to HTTPError;
      i.e. 4xx and 5xx response status codes) will cause the
      dispatcher to raise that exception, and the others (which
      defaults to 1xx and 2xx response status codes) are simply
      returned as-is.

      Non-HTTPException responses or exceptions are not changed in any
      way by the dispatcher.

      The primary impact of this is when `pyramid-controllers` is
      combined with `pyramid-tm` (the transaction manager) and the
      `pyramid_tm.default_commit_veto` (or similar) veto hook is used:
      when an exception is *raised* (no matter what kind), the
      transaction is rolled back. When a response is *returned*, it
      will be inspected by the `commit_veto` hook where only 4xx and
      5xx status codes will be rolled back IFF (if and only if) the
      x-tm:commit header is not set.

    raiseErrors : bool, DEPRECATED, default: null

      DEPRECATED -- only here for backward compatibility. Please use
      `raiseType` instead.

    autoDecorate : bool, default: true

      Primarily for internal purposes -- when set to truthy (the
      default), the result of doing a controller exposure instance
      inspection will be cached as an attribute on the controller
      (named the value of ``self.PCATTR``).

    Note: the standard dispatcher assumes that URL-encoded client
    paths will remain URL-encoded until they get to the Dispatcher.
    At that point the URL is split at slashes ('/'), and each
    component is then URL-decoded (but no further interpretation is
    done). The default Apache configuration violates this assumption
    -- to correct that, you can use the following Apache directive::

      AllowEncodedSlashes NoDecode
    '''
    super(Dispatcher, self).__init__(*args, **kw)
    self.defaultForceSlash = defaultForceSlash
    self.defaultDashUnder  = defaultDashUnder
    self.raiseType         = raiseType
    if raiseType is HTTPError and raiseErrors is not None:
      self.raiseType         = HTTPError if raiseErrors else ()
    self.autoDecorate      = autoDecorate

  #----------------------------------------------------------------------------
  def makeMeta(self, controller):
    meta = adict(fiddle=[], wrap=[], expose={}, index=[], lookup=[], default=[])
    cpc = getattr(controller, decorator.PCCTRLATTR, None)
    # TODO: this call has side-effects!... modify this so that it doesn't.
    if cpc:
      cpc.apply(controller)
    for name, attr in inspect.getmembers(controller):
      apc = getattr(attr, self.PCATTR, None)
      if not apc:
        continue
      for dectype in ('fiddle', 'wrap', 'lookup', 'default', 'index'):
        if getattr(apc, dectype, []):
          meta[dectype].append(attr)
      for exp in apc.expose or []:
        exp.name = self._handler_names(name, exp)
        exp.ext = None
        for ename in exp.name:
          if ename not in meta.expose:
            meta.expose[ename] = []
          meta.expose[ename].append(attr)
    return meta

  #----------------------------------------------------------------------------
  def _handler_names(self, name, spec):
    names = spec.name if spec.name else [ name ]
    if isinstance(names, six.string_types):
      names = [ names ]
    if '_' in name \
        and 'name' not in spec \
        and spec.dashUnder is not False \
        and ( spec.dashUnder is True or self.defaultDashUnder ):
      names += [ name.replace('_', '-') ]
    if 'ext' in spec and spec.ext is not None:
      names = [
        name + '.' + ext if ext is not None else name
        for ext in spec.ext
        for name in names
      ]
    return names

  #----------------------------------------------------------------------------
  def getMeta(self, controller):
    if not self.autoDecorate:
      return self.makeMeta(controller)
    # TODO: how to avoid this object attribute pollution?...
    # TODO: what if this controller uses dynamically generated methods
    #       or __getitem__?...
    pc = getattr(controller, self.PCATTR, None)
    if pc is None:
      pc = adict()
      setattr(controller, self.PCATTR, pc)
    if pc.meta is not None:
      return pc.meta
    pc.meta = self.makeMeta(controller)
    return pc.meta

  #----------------------------------------------------------------------------
  def _filter(self, request, response, controller, handler, dectype, spec, remainder):
    # TODO: implement all kinds of filtering...
    #         - request filtering:
    #           - check content-type
    #           - extensible filter function
    #         - response filtering:
    #           - check response object type
    #           - extensible filter function
    if dectype == 'expose':
      if spec.name and remainder[0] not in spec.name:
        return None
    if dectype in ('expose', 'index', 'default'):
      if spec.method and request.method not in spec.method:
        return None
    if response:
      if spec.renderer is None:
        return None
    return spec

  #----------------------------------------------------------------------------
  def _select(self, request, response, controller, handler, dectype, remainder, speclist):
    for spec in speclist:
      spec = self._filter(request, response, controller, handler, dectype, spec, remainder)
      if spec is not None:
        return spec
    return None

  #----------------------------------------------------------------------------
  def _getOp(self, request, controller, dectype, remainder, multi=False):
    if not isinstance(controller, Controller):
      raise TypeError('get-op called on non-controller')
    meta = self.getMeta(controller)
    ret = []
    for handler in meta[dectype]:
      apc = getattr(handler, self.PCATTR, None)
      if not apc:
        continue
      spec = self._select(request, None, controller, handler, dectype, remainder, getattr(apc, dectype, []))
      if spec is not None:
        if not multi:
          return (handler, spec)
        ret.append(handler)
    if multi:
      return (ret, None)
    return (None, None)

  #----------------------------------------------------------------------------
  def getEntries(self, controller, includeIndirect=False, sortcmp=None):
    '''
    Lists all the entrypoints exposed by `controller` - primarily used
    by DescribeController but done here so that access to and naming
    of the controller variables is managed centrally. The returned
    generator iterates over tuples of (NAME, HANDLER) in alphabetic
    order of the exposed NAME (or as specified by `sortcmp` if
    provided). The following special names are returned:

    * Dispatcher.NAME_INDEX   - @index handler
    * Dispatcher.NAME_DEFAULT - @default handler
    * Dispatcher.NAME_LOOKUP  - @lookup handler

    @index handlers are returned first, then @expose'd handlers,
    followed by @default and @lookup handlers.

    IMPORTANT: returned names and pairs may not be unique! For
    example, if two handlers are exposed with the same alias but have
    different rendering conditions, then they will both be returned in
    undefined order.
    '''
    meta = self.getMeta(controller)
    for meth in meta.index:
      yield (self.NAME_INDEX, meth)
    names = dict()
    for name, curexp in meta.expose.items():
      names[name] = curexp[:]
    # todo: it would probably be better to create a subclass of
    #       dict() that does this directly...
    def appto(name, attr):
      if name not in names:
        names[name] = []
      names[name].append(attr)
    hasIndirect = False
    for name, attr in inspect.getmembers(controller):
      if isinstance(attr, Controller):
        # todo: should this be `filtered` instead?...
        # todo: what if this is aliased...
        # todo: what about `dashUnder` implications?...
        if includeIndirect or attr._pyramid_controllers.expose is True:
          hasIndirect = hasIndirect or not attr._pyramid_controllers.expose
          appto(name, attr)
        continue
      if type(attr) in (types.TypeType, types.ClassType):
        # todo: check that type(handler()) == Controller...
        # todo: check handler()._pyramid_controllers.expose is True...
        appto(name, attr)
        continue
      if not callable(attr):
        continue
      apc = getattr(attr, self.PCATTR, None)
      if not apc:
        continue
      for exp in apc.expose or []:
        # todo: what about `dashUnder` implications?...
        if exp.name:
          continue
        appto(name, attr)
    for name in sorted(names.keys(), cmp=sortcmp):
      for attr in names[name]:
        yield (name, attr)
    for meth in meta.default:
      yield (self.NAME_DEFAULT, meth)
    if not hasIndirect:
      for meth in meta.lookup:
        yield (self.NAME_LOOKUP, meth)

  #----------------------------------------------------------------------------
  def getFiddlers(self, request, controller, remainder):
    return self._getOp(request, controller, 'fiddle', remainder, multi=True)[0]

  #----------------------------------------------------------------------------
  def getWrappers(self, request, controller, remainder):
    return self._getOp(request, controller, 'wrap', remainder, multi=True)[0]

  #----------------------------------------------------------------------------
  def getIndexHandler(self, request, controller, remainder):
    handler, spec = self._getOp(request, controller, 'index', remainder)
    if not handler:
      return None
    # check that the path ends in a '/' (which is the case if the last
    # path segment is '') - if not, check `forceSlash`...
    if ( len(remainder) == 1 and remainder[0] == '' ) \
          or spec.forceSlash is False:
      return handler
    if spec.forceSlash or self.defaultForceSlash:
      # todo: is this really the best way?...
      url = request.path + '/'
      if request.query_string:
        url += '?' + request.query_string
      raise HTTPFound(location=url)
    return handler

  #----------------------------------------------------------------------------
  def _filterNext(self, request, controller, remainder, handler, checkDashUnder=False):
    # TODO: this `checkDashUnder`... a total hack.
    if not handler:
      return None
    if isinstance(handler, Controller):
      # todo: should this be `filtered` instead?...
      # todo: what if this is aliased...
      if handler._pyramid_controllers.expose is not True:
        return None
      if checkDashUnder \
         and ( handler._pyramid_controllers.dashUnder is False
               or ( handler._pyramid_controllers.dashUnder is not True
                    and not self.defaultDashUnder )
         ):
        return None
      return handler
    if type(handler) in (types.TypeType, types.ClassType):
      # TODO: check that type(handler()) == Controller...
      # TODO: check handler()._pyramid_controllers.expose is True...
      return handler
    pc = getattr(handler, self.PCATTR, None)
    if not pc:
      return None
    for spec in pc.expose:
      spec = self._filter(request, None, controller, handler, 'expose', spec, remainder)
      if spec is not None:
        return handler
    return None

  #----------------------------------------------------------------------------
  def getNextHandler(self, request, controller, remainder):
    name    = remainder[0]
    aname   = name
    if six.PY2 and isinstance(name, unicode):
      # python2's getattr() seems to require a 'str' attribute name...
      aname = name.encode('utf-8')
    handler = getattr(controller, aname, None)
    handler = self._filterNext(request, controller, remainder, handler)
    if handler is not None:
      return handler
    if '-' in aname:
      handler = getattr(controller, aname.replace('-', '_'), None)
      handler = self._filterNext(request, controller, remainder, handler, checkDashUnder=True)
      if handler is not None:
        return handler
    meta = self.getMeta(controller)
    for alias in meta.expose.get(name, []):
      ret = self._filterNext(request, controller, remainder, alias)
      if ret:
        return ret
    return None

  #----------------------------------------------------------------------------
  def getLookupHandler(self, request, controller, remainder):
    return self._getOp(request, controller, 'lookup', remainder)[0]

  #----------------------------------------------------------------------------
  def getDefaultHandler(self, request, controller, remainder):
    return self._getOp(request, controller, 'default', remainder)[0]

  #----------------------------------------------------------------------------
  def dispatch(self, request, controller):
    try:
      # normalize the path
      opath = request.matchdict['pyramid_controllers_path']
      # prefixing with '///' so that leading '..' get dropped (the reason
      # that a simple '/' prefix is not sufficient is that normpath will not
      # collapse a leading '//'...)
      path = os.path.normpath('///' + opath)
      # normpath strips a trailing '/'... re-append if needed
      if opath.endswith('/') and not path.endswith('/'):
        path += '/'
      # strip leading '/'
      path = path[1:]
      # split at '/' and url-decode each component
      path = [urllib.parse.unquote(e) for e in path.split('/')]
      ret = self.walk(request, controller, path, [])
      if isinstance(ret, HTTPException) and isinstance(ret, self.raiseType or ()):
        raise ret
      return ret
    except (HTTPException,), exc:
      if isinstance(exc, self.raiseType or ()):
        raise
      return exc

  #----------------------------------------------------------------------------
  def walk(self, request, controller, remainder, wrappers):

    # todo: aren't some already-instantiated classes still 'callable'?...
    if callable(controller):
      controller = controller(request)

    # do request fiddling
    fiddlers = self.getFiddlers(request, controller, remainder)
    for fiddler in fiddlers:
      request = fiddler(request) or request

    # load wrappers
    wrappers.extend(self.getWrappers(request, controller, remainder))

    if len(remainder) <= 0 or len(remainder) == 1 and remainder[0] == '':
      handler = self.getIndexHandler(request, controller, remainder)
      dectype = 'index'
      args    = []
      if handler is None:
        handler = self.getDefaultHandler(request, controller, remainder)
        dectype = 'default'
        args    = [None]
      if handler is None:
        raise HTTPNotFound()
      return self.handle(
        request, controller, handler, dectype, remainder, wrappers, args=args)

    handler = self.getNextHandler(request, controller, remainder)
    if isinstance(handler, Controller) \
          or type(handler) in (types.TypeType, types.ClassType):
      return self.walk(request, handler, remainder[1:], wrappers)
    if handler is not None:
      if len(remainder) > 1:
        raise HTTPNotFound()
      return self.handle(
        request, controller, handler, 'expose', remainder, wrappers)

    lookup = self.getLookupHandler(request, controller, remainder)
    if lookup is not None:
      (controller, remainder) = lookup(request, *remainder)
      return self.walk(request, controller, remainder, wrappers)

    default = self.getDefaultHandler(request, controller, remainder)
    if default is not None:
      return self.handle(
        request, controller, default, 'default', remainder, wrappers, args=remainder)

    raise HTTPNotFound()

  #----------------------------------------------------------------------------
  def handle(self, request, controller, handler, dectype, remainder, wrappers, args=None):
    if handler is None or not callable(handler):
      raise HTTPNotFound()

    # TODO: resolve parameters...
    params = dict()

    if args is None:
      args = []

    # todo: should `args` and `params` be passed to the wrappers as well?...
    # todo: should i trap exceptions to allow @expose matching?...
    def recursive_handle(request):
      if wrappers:
        return wrappers.pop(0)(request, recursive_handle)
      return handler(request, *args, **params)

    response = recursive_handle(request)
    return self.render(request, response, controller, handler, dectype, remainder)

  #----------------------------------------------------------------------------
  def getPackageName(self, handler):
    try:
      return inspect.getmodule(handler).__name__
    except:
      return None

  #----------------------------------------------------------------------------
  def render(self, request, response, controller, handler, dectype, remainder):
    if isinstance(response, Response):
      return response
    if isinstance(response, six.text_type):
      request.response.text = response
      return request.response
    if isinstance(response, six.string_types):
      request.response.body = response
      return request.response
    package  = self.getPackageName(handler)
    renderer = getattr(request, 'override_renderer', None)
    if renderer is not None:
      return render_to_response(renderer, response, request, package)
    # NOTE: this is a *horrible* hack... see restcontroller.py why it
    #       is needed.
    handler, dectype, remainder = \
      getattr(request, '_restcontroller_snaghack', ( handler, dectype, remainder ))
    pc   = getattr(handler, self.PCATTR, adict())
    spec = self._select(request, response, controller, handler, dectype,
                        remainder, getattr(pc, dectype, []))
    if spec is None:
      raise ControllerError(
        'no renderer found for handler "%r", request "%r", and response "%r"'
        % (handler, request, response))
    return render_to_response(spec.renderer, response, request, package)


#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------
