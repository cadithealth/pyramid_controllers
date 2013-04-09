# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.test_dispatcher
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/16
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
Unit test the pyramid-controllers dispatching mechanisms.
'''

import unittest, urllib
from pyramid import testing
from pyramid.request import Request
from pyramid.response import Response
from pyramid.httpexceptions import \
    HTTPNotFound, HTTPFound, HTTPMethodNotAllowed, \
    HTTPException, WSGIHTTPException
from pyramid_controllers import \
    includeme, \
    Controller, Dispatcher, \
    expose, index, lookup, default, fiddle, expose_defaults
from .test_helpers import TestHelper

#------------------------------------------------------------------------------
class TestDispatcher(TestHelper):

  def test_includeme_adds_index_and_root_views(self):
    'Calling config.include("pyramid_controllers") adds controller directive'
    self._setup(Controller(), '/')
    self.assertEqual([v['route_name'] for v in self.views], ['root-index', 'root'])

  #----------------------------------------------------------------------------
  # TEST @INDEX
  #----------------------------------------------------------------------------

  def test_root_index(self):
    'Index requests at the root level'
    class RootIndex(Controller):
      @index
      def index(self, request): return 'ok.index'
    self.assertResponse(self.send(RootIndex(), '/'), 200, 'ok.index')

  def test_root_index_without_forceSlash(self):
    'Index requests at the root level with forceSlash disabled'
    class RootIndex(Controller):
      @index(forceSlash=False)
      def index(self, request): return 'ok.index'
    self.assertResponse(self.send(RootIndex(), '/'), 200, 'ok.index')

  def test_sub_index(self):
    'Index requests at sub-controllers'
    class Sub(Controller):
      @index
      def index(self, request):
        return 'ok.sub.index'
    class Root(Controller):
      sub = Sub()
    self.assertResponse(self.send(Root(), '/sub/'), 200, 'ok.sub.index')
    self.assertResponse(self.send(Root(), '/sub'),  302, location='/sub/')

  def test_sub_index_without_forceSlash(self):
    'Index requests at sub-controllers with forceSlash disabled'
    class Sub(Controller):
      @index(forceSlash=False)
      def index(self, request):
        return 'ok.sub.index'
    class Root(Controller):
      sub = Sub()
    self.assertResponse(self.send(Root(), '/sub/'), 200, 'ok.sub.index')
    self.assertResponse(self.send(Root(), '/sub'),  200, 'ok.sub.index')

  def test_sub_index_with_nonstandard_name(self):
    'Index requests at sub-controllers using non-standard method name'
    class Sub(Controller):
      @index
      def index_nonstandard_name(self, request):
        return 'ok.sub.index'
    class Root(Controller):
      sub = Sub()
    self.assertResponse(self.send(Root(), '/sub/'), 200, 'ok.sub.index')

  def test_root_index_anchored_non_slash(self):
    'Index requests at the root controller not anchored at "/"'
    class RootIndex(Controller):
      @index
      def index(self, request): return 'ok.index'
    self.assertResponse(self.send(RootIndex(), '/anchor/', rootPath='/anchor'), 200, 'ok.index')

  # # TODO: this unit test currently fails... re-enable when fixed.
  # def test_root_index_anchored_non_slash_without_slash_redirects(self):
  #   'Index requests at the root controller not anchored at "/" redirect to trailing slash'
  #   class RootIndex(Controller):
  #     @index
  #     def index(self, request): return 'ok.index'
  #   self.assertResponse(self.send(RootIndex(), '/anchor/', rootPath='/anchor'),
  #                                 302, location='/anchor/')

  def test_root_index_anchored_non_slash_without_forceSlash(self):
    'Index requests at the root controller not anchored at "/" with forceSlash disabled'
    class RootIndex(Controller):
      @index(forceSlash=False)
      def index(self, request): return 'ok.index'
    self.assertResponse(self.send(RootIndex(), '/anchor/', rootPath='/anchor'), 200, 'ok.index')
    self.assertResponse(self.send(RootIndex(), '/anchor',  rootPath='/anchor'), 200, 'ok.index')

  def test_index_renderer(self):
    '@index can specify a custom rendering engine'
    class Root(Controller):
      @index(renderer='repr')
      def index(self, request):
        return dict(foo='bar')
    self.assertResponse(self.send(Root(), '/'), 200, "{'foo': 'bar'}")

  #----------------------------------------------------------------------------
  # TEST @EXPOSE
  #----------------------------------------------------------------------------

  def test_root_method(self):
    'Method resolution at the root level'
    class Root(Controller):
      @expose
      def method(self, request): return 'ok.method'
    self.assertResponse(self.send(Root(), '/method'), 200, 'ok.method')

  def test_sub_method(self):
    'Method resolution at the root level'
    class Sub(Controller):
      @expose
      def method(self, request): return 'ok.sub.method'
    class Root(Controller):
      sub = Sub()
    self.assertResponse(self.send(Root(), '/sub/method'), 200, 'ok.sub.method')

  def test_controller_expose(self):
    'A sub-controller can be "unexposed", i.e. not directly available'
    class Sub(Controller):
      @expose
      def method(self, request):
        return 'ok.sub.method'
    class Root(Controller):
      sub = Sub()
      sub2 = Sub(expose=False)
    self.assertResponse(self.send(Root(), '/sub/method'),  200, 'ok.sub.method')
    self.assertResponse(self.send(Root(), '/sub2/method'), 404)

  def test_not_found(self):
    'Non-existent methods result in 404 response status'
    class Root(Controller):
      @expose
      def method(self, request): return 'ok.method'
    self.assertResponse(self.send(Root(), '/no-such-method'), 404, '')

  def test_not_exposed(self):
    'Unexposed methods result in 404 response status'
    class Root(Controller):
      def notexposed(self, request): return 'uh-oh.notexposed'
    self.assertResponse(self.send(Root(), '/notexposed'), 404, '')

  def test_expose_renderer(self):
    '@expose can specify a custom rendering engine'
    class Root(Controller):
      @expose(renderer='repr')
      def method(self, request):
        return dict(foo='bar')
    self.assertResponse(self.send(Root(), '/method'), 200, "{'foo': 'bar'}")

  #----------------------------------------------------------------------------
  # TEST @EXPOSE ALIASING
  #----------------------------------------------------------------------------

  def test_handler_aliasing(self):
    'Controller methods with @expose `name` attribute perform aliasing'
    class Name(Controller):
      @expose(name='data.json')
      def data(self, request):
        return Response('ok.name.data')
    self.assertResponse(self.send(Name(), '/data.json'), 200, 'ok.name.data')
    self.assertResponse(self.send(Name(), '/data'),      404)

  def test_handler_multi_aliasing(self):
    'Controller methods with variations on @expose `name` attribute perform multiple aliasing'
    class Name(Controller):
      @expose(name='data.json')
      @expose
      def data(self, request):
        return Response('ok.name.data')
    self.assertResponse(self.send(Name(), '/data.json'), 200, 'ok.name.data')
    self.assertResponse(self.send(Name(), '/data'),      200, 'ok.name.data')

  def test_handler_extension_aliasing(self):
    'Controller methods with @expose `ext` attribute perform aliasing based on method name'
    class Ext(Controller):
      @expose(ext='less', renderer='raw')
      @expose(ext='css', renderer='lessc')
      def style(self, request): return dict(msg='ok.name.style')
    def raw(info):
      def _render(value, system):
        return 'RAW:' + value['msg']
      return _render
    def lessc(info):
      def _render(value, system):
        return 'COMPILED:' + value['msg']
      return _render
    self.renderers['raw'] = raw
    self.renderers['lessc'] = lessc
    self.assertResponse(self.send(Ext(), '/style.less'), 200, 'RAW:ok.name.style')
    self.assertResponse(self.send(Ext(), '/style.css'),  200, 'COMPILED:ok.name.style')
    self.assertResponse(self.send(Ext(), '/style'),      404)

  def test_expose_name_and_ext_collision(self):
    '@expose parameters "ext" and "name" are mutually exclusive'
    with self.assertRaises(ValueError):
      class Bad(Controller):
        @expose(name='foo', ext='css')
        def method(self, request): pass

  def test_expose_ext_list(self):
    '@expose parameters "ext" and "name" can accept lists'
    class Ext(Controller):
      @expose(ext=('txt', 'rst'))
      def ext(self, request): return 'ok.ext:' + request.path
      @expose(name=('foo', 'bar'))
      def name(self, request): return 'ok.name:' + request.path
    self.assertResponse(self.send(Ext(), '/ext.txt'), 200, 'ok.ext:/ext.txt')
    self.assertResponse(self.send(Ext(), '/ext.rst'), 200, 'ok.ext:/ext.rst')
    self.assertResponse(self.send(Ext(), '/foo'),     200, 'ok.name:/foo')
    self.assertResponse(self.send(Ext(), '/bar'),     200, 'ok.name:/bar')
    self.assertResponse(self.send(Ext(), '/name'),    404)

  #----------------------------------------------------------------------------
  # TEST @FIDDLE
  #----------------------------------------------------------------------------

  def test_fiddle_decorator(self):
    'Simple request fiddling during hierarchy traversal'
    class Sub(Controller):
      @fiddle
      def _fiddle(self, request):
        request.fiddled = True
      @expose
      def data(self, request):
        return 'ok.sub.data:fiddled=%r' % (getattr(request, 'fiddled', False),)
    class Root(Controller):
      sub = Sub()
    self.assertResponse(self.send(Root(), '/sub/data'), 200, 'ok.sub.data:fiddled=True')

  def test_fiddle_decorator_with_nonstandard_name(self):
    'Request fiddling with non-standard decorator name'
    class Sub(Controller):
      @fiddle
      def fiddle_nonstandard_name(self, request):
        request.fiddled = True
      @expose
      def data(self, request):
        return 'ok.sub.data:nsn-fiddled=%r' % (getattr(request, 'fiddled', False),)
    class Root(Controller):
      sub = Sub()
    self.assertResponse(self.send(Root(), '/sub/data'), 200, 'ok.sub.data:nsn-fiddled=True')

  def test_fiddle_with_subclassing(self):
    'Multiple @fiddles coming from both sub-class and super-class should apply'
    class Base(Controller):
      @fiddle
      def basefiddle(self, request):
        request.base = 'y'
    class Sub(Base):
      @fiddle
      def subfiddle(self, request):
        request.sub = 'y'
      @expose
      def chk(self, request):
        return 'ok:base=%s,sub=%s' % (getattr(request, 'base', 'n'), getattr(request, 'sub', 'n'))
    self.assertResponse(self.send(Sub(), '/chk'), 200, 'ok:base=y,sub=y')

  def test_fiddle_with_subclassing_and_override(self):
    'Multiple @fiddles coming from both sub-class and super-class should apply'
    class Base(Controller):
      @fiddle
      def fiddle(self, request):
        request.base = 'y'
    class Sub(Base):
      @fiddle
      def fiddle(self, request):
        request.sub = 'y'
      @expose
      def chk(self, request):
        return 'ok:base=%s,sub=%s' % (getattr(request, 'base', 'n'), getattr(request, 'sub', 'n'))
    self.assertResponse(self.send(Sub(), '/chk'), 200, 'ok:base=n,sub=y')

  def test_fiddle_with_subclassing_and_super_cascade(self):
    'Multiple @fiddles coming from both sub-class and super-class should apply'
    class Base(Controller):
      @fiddle
      def fiddle(self, request):
        request.base = 'y'
    class Sub(Base):
      @fiddle
      def fiddle(self, request):
        super(Sub, self).fiddle(request)
        request.sub = 'y'
      @expose
      def chk(self, request):
        return 'ok:base=%s,sub=%s' % (getattr(request, 'base', 'n'), getattr(request, 'sub', 'n'))
    self.assertResponse(self.send(Sub(), '/chk'), 200, 'ok:base=y,sub=y')

  #----------------------------------------------------------------------------
  # TEST @LOOKUP
  #----------------------------------------------------------------------------

  def test_lookup(self):
    'Dynamic traversal with @lookup'
    class Sub(Controller):
      @expose
      def echo(self, request):
        return 'ok.sub.echo:%s' % (str(getattr(request, 'echo', None)),)
    class Lookup(Controller):
      @lookup
      def _lookup(self, request, value, *rem):
        request.echo = value
        return (Sub(), rem)
    class Root(Controller):
      sub = Sub()
      lookup = Lookup()
    self.assertResponse(self.send(Root(), '/lookup/foo/echo'), 200, 'ok.sub.echo:foo')
    self.assertResponse(self.send(Root(), '/sub/echo'),        200, 'ok.sub.echo:None')

  def test_lookup_with_nonstandard_name(self):
    'Dynamic traversal with @lookup using non-standard method name'
    class Sub(Controller):
      @expose
      def echo(self, request):
        return 'ok.sub.echo:%s' % (str(getattr(request, 'echo', None)),)
    class Root(Controller):
      sub = Sub()
      @lookup
      def lookup_nonstandard_name(self, request, value, *rem):
        request.echo = value
        return (Sub(), rem)
    self.assertResponse(self.send(Root(), '/foo/echo'), 200, 'ok.sub.echo:foo')
    self.assertResponse(self.send(Root(), '/sub/echo'), 200, 'ok.sub.echo:None')

  #----------------------------------------------------------------------------
  # TEST @DEFAULT
  #----------------------------------------------------------------------------

  def test_default(self):
    'Fallback to @default handler'
    class Root(Controller):
      @expose
      def somemethod(self, request):
        return 'ok.somemethod'
      @default
      def _default(self, request, curpath, *rem):
        return 'ok.default:%s' % (curpath,)
    self.assertResponse(self.send(Root(), '/no-such-path'), 200, 'ok.default:no-such-path')
    self.assertResponse(self.send(Root(), '/'),             200, 'ok.default:None')

  def test_default_with_nonstandard_name(self):
    'Fallback to @default handler with non-standard method name'
    class Root(Controller):
      @expose
      def somemethod(self, request):
        return 'ok.somemethod'
      @default
      def default_nonstandard_name(self, request, curpath, *rem):
        return 'ok.default:%s' % (curpath,)
    self.assertResponse(self.send(Root(), '/no-such-path'), 200, 'ok.default:no-such-path')
    self.assertResponse(self.send(Root(), '/'),             200, 'ok.default:None')

  def test_default_renderer(self):
    '@default can specify a custom rendering engine'
    class Root(Controller):
      @default(renderer='repr')
      def index(self, request, curpath, *remainder):
        return dict(args=[curpath, list(remainder)])
    self.assertResponse(self.send(Root(), '/zag/zig/zog'), 200, "{'args': ['zag', ['zig', 'zog']]}")

  #----------------------------------------------------------------------------
  # TEST CUSTOM DISPATCHER
  #----------------------------------------------------------------------------

  def test_weird_error_no_custom_dispatcher(self):
    'Unhandled exceptions bubble up and out'
    class Weird(Exception): pass
    class Root(Controller):
      @expose
      def weird(self, request):
        raise Weird()
    self.assertRaises(
      Weird,
      self.send, Root(), '/weird')

  def test_weird_error_with_custom_dispatcher(self):
    'Custom dispatcher allows handling of unhandled exceptions before rollback'
    class Weird(Exception): pass
    class Root(Controller):
      @expose
      def weird(self, request):
        raise Weird()
    class CustomDispatcher(Dispatcher):
      def dispatch(self, request, controller):
        try:
          return super(CustomDispatcher, self).dispatch(request, controller)
        except Weird:
          return Response('that was weird')
    self.assertResponse(self.send(Root(), '/weird', dispatcher=CustomDispatcher()), 200, 'that was weird')

  #----------------------------------------------------------------------------
  # TEST CONTROLLER EXPOSE DEFAULTING
  #----------------------------------------------------------------------------

  def test_expose_defaults_renderer(self):
    'Controllers can specify default renderers for member @expose/@index/@default calls'
    @expose_defaults(renderer='repr')
    class Root(Controller):
      @index
      def index(self, request): return dict(foo='idx')
      @expose
      def method(self, request): return dict(foo='bar')
      @expose(renderer='raw')
      def raw(self, request): return dict(foo='raw')
      @default
      def default(self, request, path): return dict(foo=path)
    def raw(info):
      def _render(value, system):
        return 'RAW:' + repr(value)
      return _render
    self.renderers['raw'] = raw
    self.assertResponse(self.send(Root(), '/method'),  200, "{'foo': 'bar'}")
    self.assertResponse(self.send(Root(), '/raw'),     200, "RAW:{'foo': 'raw'}")
    self.assertResponse(self.send(Root(), '/'),        200, "{'foo': 'idx'}")
    self.assertResponse(self.send(Root(), '/zig-zag'), 200, "{'foo': 'zig-zag'}")

  def test_expose_defaults_renderer_with_subclassing(self):
    @expose_defaults(renderer='repr')
    class Base(Controller):
      @expose
      def rep(self, request): return dict(m='rep')
      @expose(renderer='raw')
      def raw(self, request): return dict(m='raw')
    class Root(Base):
      @expose
      def srep(self, request): return dict(m='srep')
      @expose(renderer='raw')
      def sraw(self, request): return dict(m='sraw')
    def raw(info):
      def _render(value, system):
        return 'RAW:' + repr(value)
      return _render
    self.renderers['raw'] = raw
    self.assertResponse(self.send(Root(), "/rep"),  200, "{'m': 'rep'}")
    self.assertResponse(self.send(Root(), "/raw"),  200, "RAW:{'m': 'raw'}")
    self.assertResponse(self.send(Root(), "/srep"), 200, "{'m': 'srep'}")
    self.assertResponse(self.send(Root(), "/sraw"), 200, "RAW:{'m': 'sraw'}")

  # def test_expose_defaults_does_not_pollute(self):
  #   class Base(Controller):
  #     def __init__(self):
  #       super(Base,self).__init__()
  #       self.count = 0
  #     @expose
  #     def m(self, request):
  #       self.count += 1
  #       return dict(c=self.count)
  #   @expose_defaults(renderer='raw')
  #   class Raw(Base):
  #     pass
  #   @expose_defaults(renderer='repr')
  #   class Rep(Base):
  #     pass
  #   class Root(Controller):
  #     raw = Raw()
  #     rep = Rep()
  #   def raw(info):
  #     def _render(value, system):
  #       return 'RAW:' + repr(value)
  #     return _render
  #   self.renderers['raw'] = raw
  #   root = Root()
  #   self.assertResponse(self.send(root, '/raw/m'), 200, "RAW:{'c': 1}")
  #   self.assertResponse(self.send(root, '/rep/m'), 200, "{'c': 2}")
  #   self.assertResponse(self.send(root, '/raw/m'), 200, "RAW:{'c': 3}")

  def test_expose_defaults_ext(self):
    'Controllers can specify default extensions for member @expose calls'
    @expose_defaults(ext='json')
    class Root(Controller):
      @expose
      def foo(self, request): return 'foo'
      @expose
      def bar(self, request): return 'bar'
      @expose(ext='js')
      def zag(self, request): return 'zag'
      @expose(name='zig.css')
      def zig(self, request): return 'zig'
      @expose(ext=None)
      def zog(self, request): return 'zog'
    self.assertResponse(self.send(Root(), '/foo.json'), 200, 'foo')
    self.assertResponse(self.send(Root(), '/foo'),      404)
    self.assertResponse(self.send(Root(), '/bar.json'), 200, 'bar')
    self.assertResponse(self.send(Root(), '/bar'),      404)
    self.assertResponse(self.send(Root(), '/zag.js'),   200, 'zag')
    self.assertResponse(self.send(Root(), '/zag.json'), 404)
    self.assertResponse(self.send(Root(), '/zag'),      404)
    self.assertResponse(self.send(Root(), '/zig.css'),  200, 'zig')
    self.assertResponse(self.send(Root(), '/zig.json'), 404)
    self.assertResponse(self.send(Root(), '/zig'),      404)
    self.assertResponse(self.send(Root(), '/zog'),      200, 'zog')
    self.assertResponse(self.send(Root(), '/zog.json'), 404)
    self.assertResponse(self.send(Root(), '/zog.js'),   404)
    self.assertResponse(self.send(Root(), '/zog.css'),  404)

  def test_expose_defaults_with_subclassing_from_base(self):
    @expose_defaults(ext='json')
    class Base(Controller):
      @expose
      def foo(self, request): return 'foo'
    class Root(Base):
      @expose
      def bar(self, request): return 'bar'
    self.assertResponse(self.send(Root(), '/foo.json'), 200, 'foo')
    self.assertResponse(self.send(Root(), '/foo'),      404)
    self.assertResponse(self.send(Root(), '/bar.json'), 200, 'bar')
    self.assertResponse(self.send(Root(), '/bar'),      404)

  def test_expose_defaults_with_subclassing_to_base(self):
    class Base(Controller):
      @expose
      def foo(self, request): return 'foo'
    @expose_defaults(ext='json')
    class Root(Base):
      @expose
      def bar(self, request): return 'bar'
    self.assertResponse(self.send(Root(), '/foo.json'), 200, 'foo')
    self.assertResponse(self.send(Root(), '/foo'),      404)
    self.assertResponse(self.send(Root(), '/bar.json'), 200, 'bar')
    self.assertResponse(self.send(Root(), '/bar'),      404)

  def test_expose_defaults_with_subclassing_and_override(self):
    @expose_defaults(ext='json')
    class Base(Controller):
      @expose
      def foo(self, request): return 'foo'
    @expose_defaults(ext='js')
    class Root(Base):
      @expose
      def bar(self, request): return 'bar'
    self.assertResponse(self.send(Root(), '/foo.json'), 200, 'foo')
    self.assertResponse(self.send(Root(), '/foo'),      404)
    self.assertResponse(self.send(Root(), '/bar.js'),   200, 'bar')
    self.assertResponse(self.send(Root(), '/bar.json'), 404)
    self.assertResponse(self.send(Root(), '/bar'),      404)

  def test_expose_defaults_with_override(self):
    @expose_defaults(ext='json')
    class Root(Controller):
      @expose
      def foo(self, request): return 'foo'
      @expose(ext=None)
      def bar(self, request): return 'bar'
    self.assertResponse(self.send(Root(), '/foo.json'), 200, 'foo')
    self.assertResponse(self.send(Root(), '/foo'),      404)
    self.assertResponse(self.send(Root(), '/bar'),      200, 'bar')
    self.assertResponse(self.send(Root(), '/bar.json'), 404)

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
