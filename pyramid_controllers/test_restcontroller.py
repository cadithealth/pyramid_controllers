# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.test_dispatcher
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/20
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
Unit test the pyramid-controllers RESTful controller helper class.
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
    Controller, RestController, Dispatcher, \
    expose, index, lookup, default, fiddle
from .test_helpers import TestHelper

#------------------------------------------------------------------------------
class TestRestController(TestHelper):

  #----------------------------------------------------------------------------
  def test_exposed_http_method(self):
    'RestControllers map HTTP methods to exposed controller methods'
    class RestRoot(RestController):
      @expose
      def get(self, request): return 'ok.get'
      @expose
      def put(self, request): return 'ok.put'
    self.assertResponse(self.send(RestRoot(), '/', method='GET'),    200, 'ok.get')
    self.assertResponse(self.send(RestRoot(), '/', method='PUT'),    200, 'ok.put')
    self.assertResponse(self.send(RestRoot(), '/', method='DELETE'), 405)

  #----------------------------------------------------------------------------
  def test_unexposed_http_method(self):
    'RestControllers respond with "405 Method Not Allowed" for un-exposed methods'
    class RestRoot(RestController):
      @expose
      def get(self, request): return 'ok.get'
      def put(self, request): return 'ok.put'
    self.assertResponse(self.send(RestRoot(), '/', method='GET'),    200, 'ok.get')
    self.assertResponse(self.send(RestRoot(), '/', method='PUT'),    405)
    self.assertResponse(self.send(RestRoot(), '/', method='DELETE'), 405)

  #----------------------------------------------------------------------------
  def test_rest_custom_renderer(self):
    'RestControllers support custom renderers in @exposed methods'
    class RestRoot(RestController):
      @expose(renderer='repr')
      def get(self, request): return dict(foo='bar')
    self.assertResponse(self.send(RestRoot(), '/', method='GET'), 200, "{'foo': 'bar'}")

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
