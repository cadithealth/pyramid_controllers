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
    res = self.send(RootIndex(), '/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.index')

  def test_root_index_without_forceSlash(self):
    'Index requests at the root level with forceSlash disabled'
    class RootIndex(Controller):
      @index(forceSlash=False)
      def index(self, request): return 'ok.index'
    res = self.send(RootIndex(), '/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.index')

  def test_sub_index(self):
    'Index requests at sub-controllers'
    class Sub(Controller):
      @index
      def index(self, request):
        return 'ok.sub.index'
    class Root(Controller):
      sub = Sub()
    res = self.send(Root(), '/sub/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.index')
    res = self.send(Root(), '/sub')
    self.assertEqual(res.status_code, 302)
    self.assertEqual(res.headers['Location'], '/sub/')

  def test_sub_index_without_forceSlash(self):
    'Index requests at sub-controllers with forceSlash disabled'
    class Sub(Controller):
      @index(forceSlash=False)
      def index(self, request):
        return 'ok.sub.index'
    class Root(Controller):
      sub = Sub()
    res = self.send(Root(), '/sub/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.index')
    res = self.send(Root(), '/sub')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.index')

  def test_sub_index_with_nonstandard_name(self):
    'Index requests at sub-controllers using non-standard method name'
    class Sub(Controller):
      @index
      def index_nonstandard_name(self, request):
        return 'ok.sub.index'
    class Root(Controller):
      sub = Sub()
    res = self.send(Root(), '/sub/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.index')

  def test_root_index_anchored_non_slash(self):
    'Index requests at the root controller not anchored at "/"'
    class RootIndex(Controller):
      @index
      def index(self, request): return 'ok.index'
    res = self.send(RootIndex(), '/anchor/', rootPath='/anchor')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.index')

  # # TODO: this unit test currently fails... re-enable when fixed.
  # def test_root_index_anchored_non_slash_without_slash_redirects(self):
  #   'Index requests at the root controller not anchored at "/" redirect to trailing slash'
  #   class RootIndex(Controller):
  #     @index
  #     def index(self, request): return 'ok.index'
  #   res = self.send(RootIndex(), '/anchor', rootPath='/anchor')
  #   self.assertEqual(res.status_code, 302)
  #   self.assertEqual(res.headers['Location'], '/anchor/')

  def test_root_index_anchored_non_slash_without_forceSlash(self):
    'Index requests at the root controller not anchored at "/" with forceSlash disabled'
    class RootIndex(Controller):
      @index(forceSlash=False)
      def index(self, request): return 'ok.index'
    res = self.send(RootIndex(), '/anchor/', rootPath='/anchor')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.index')
    res = self.send(RootIndex(), '/anchor', rootPath='/anchor')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.index')

  def test_index_renderer(self):
    '@index can specify a custom rendering engine'
    class Root(Controller):
      @index(renderer='repr')
      def index(self, request):
        return dict(foo='bar')
    res = self.send(Root(), '/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "{'foo': 'bar'}")

  #----------------------------------------------------------------------------
  # TEST @EXPOSE
  #----------------------------------------------------------------------------

  def test_root_method(self):
    'Method resolution at the root level'
    class Root(Controller):
      @expose
      def method(self, request): return 'ok.method'
    res = self.send(Root(), '/method')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.method')

  def test_sub_method(self):
    'Method resolution at the root level'
    class Sub(Controller):
      @expose
      def method(self, request): return 'ok.sub.method'
    class Root(Controller):
      sub = Sub()
    res = self.send(Root(), '/sub/method')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.method')

  def test_controller_expose(self):
    'A sub-controller can be "unexposed", i.e. not directly available'
    class Sub(Controller):
      @expose
      def method(self, request):
        return 'ok.sub.method'
    class Root(Controller):
      sub = Sub()
      sub2 = Sub(expose=False)
    res = self.send(Root(), '/sub/method')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.method')
    res = self.send(Root(), '/sub2/method')
    self.assertEqual(res.status_code, 404)

  def test_not_found(self):
    'Non-existent methods result in 404 response status'
    class Root(Controller):
      @expose
      def method(self, request): return 'ok.method'
    res = self.send(Root(), '/no-such-method')
    self.assertEqual(res.status_code, 404)
    self.assertEqual(res.body, '')

  def test_not_exposed(self):
    'Unexposed methods result in 404 response status'
    class Root(Controller):
      def notexposed(self, request): return 'uh-oh.notexposed'
    res = self.send(Root(), '/notexposed')
    self.assertEqual(res.status_code, 404)
    self.assertEqual(res.body, '')

  def test_expose_renderer(self):
    '@expose can specify a custom rendering engine'
    class Root(Controller):
      @expose(renderer='repr')
      def method(self, request):
        return dict(foo='bar')
    res = self.send(Root(), '/method')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "{'foo': 'bar'}")

  #----------------------------------------------------------------------------
  # TEST @EXPOSE ALIASING
  #----------------------------------------------------------------------------

  def test_handler_aliasing(self):
    'Controller methods with @expose `name` attribute perform aliasing'
    class Name(Controller):
      @expose(name='data.json')
      def data(self, request):
        return Response('ok.name.data')
    res = self.send(Name(), '/data.json')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.name.data')
    res = self.send(Name(), '/data')
    self.assertEqual(res.status_code, 404)

  def test_handler_multi_aliasing(self):
    'Controller methods with variations on @expose `name` attribute perform multiple aliasing'
    class Name(Controller):
      @expose(name='data.json')
      @expose
      def data(self, request):
        return Response('ok.name.data')
    res = self.send(Name(), '/data.json')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.name.data')
    res = self.send(Name(), '/data')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.name.data')

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
    res = self.send(Ext(), '/style.less')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'RAW:ok.name.style')
    res = self.send(Ext(), '/style.css')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'COMPILED:ok.name.style')
    res = self.send(Ext(), '/style')
    self.assertEqual(res.status_code, 404)

  def test_expose_name_and_ext_collision(self):
    '@expose parameters "ext" and "name" are mutually exclusive'
    def createBadController():
      class Bad(Controller):
        @expose(name='foo', ext='css')
        def method(self, request): pass
      return Bad
    with self.assertRaises(ValueError):
      createBadController()

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
    res = self.send(Root(), '/sub/data')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.data:fiddled=True')

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
    res = self.send(Root(), '/sub/data')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.data:nsn-fiddled=True')

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
    res = self.send(Root(), '/lookup/foo/echo')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.echo:foo')
    res = self.send(Root(), '/sub/echo')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.echo:None')

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
    res = self.send(Root(), '/foo/echo')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.echo:foo')
    res = self.send(Root(), '/sub/echo')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.sub.echo:None')

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
    res = self.send(Root(), '/no-such-path')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.default:no-such-path')
    res = self.send(Root(), '/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.default:None')

  def test_default_with_nonstandard_name(self):
    'Fallback to @default handler with non-standard method name'
    class Root(Controller):
      @expose
      def somemethod(self, request):
        return 'ok.somemethod'
      @default
      def default_nonstandard_name(self, request, curpath, *rem):
        return 'ok.default:%s' % (curpath,)
    res = self.send(Root(), '/no-such-path')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.default:no-such-path')
    res = self.send(Root(), '/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'ok.default:None')

  def test_default_renderer(self):
    '@default can specify a custom rendering engine'
    class Root(Controller):
      @default(renderer='repr')
      def index(self, request, curpath, *remainder):
        return dict(args=[curpath, list(remainder)])
    res = self.send(Root(), '/zag/zig/zog')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "{'args': ['zag', ['zig', 'zog']]}")

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
    res = self.send(Root(), '/weird', dispatcher=CustomDispatcher())
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, 'that was weird')

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
    res = self.send(Root(), '/method')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "{'foo': 'bar'}")
    res = self.send(Root(), '/raw')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "RAW:{'foo': 'raw'}")
    res = self.send(Root(), '/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "{'foo': 'idx'}")
    res = self.send(Root(), '/zig-zag')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.body, "{'foo': 'zig-zag'}")

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

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
