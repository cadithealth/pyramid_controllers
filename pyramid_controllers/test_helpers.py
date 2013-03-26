# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.test_helpers
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/20
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
Helper functions for pyramid-controllers unit testing.
'''

import unittest, urllib
from pyramid import testing
from pyramid.request import Request
from pyramid.response import Response

#------------------------------------------------------------------------------
def reprRendererFactory(info):
  def _render(value, system):
    return repr(value)
  return _render

#------------------------------------------------------------------------------
def xnl(text):
  return text.replace('><', '>\n<')

#------------------------------------------------------------------------------
class TestHelper(unittest.TestCase):

  maxDiff = None

  def setUp(self):
    self.renderers = dict(repr=reprRendererFactory)

  def _setup(self, rootController, requestPath,
             rootPath='/', rootName='root',
             dispatcher=None,
             method='GET',
             ):
    self.reqpath  = requestPath
    self.rootpath = rootPath
    self.rootctrl = rootController
    self.request  = request = Request.blank(requestPath)
    self.request.method = method
    self.config   = testing.setUp(request=request)
    self.registry = request.registry = self.config.registry
    self.settings = self.registry.settings = {}
    self.config.include('pyramid_controllers')
    self.views    = []
    def dummy_add_view(**kw):
      self.views.append(kw)
    self.config.add_view = dummy_add_view
    if rootPath is not None:
      self.config.add_controller(rootName, rootPath, self.rootctrl, dispatcher=dispatcher)
    for name, factory in self.renderers.items():
      self.config.add_renderer(name, factory)

  def send(self, rootController, requestPath, **kw):
    self._setup(rootController, requestPath, **kw)
    # todo: there *must* be a better way to do this... there *must* be a
    #       way to leverage pyramid to do this...
    if requestPath == self.rootpath:
      view = self.views[0]['view']
      self.request.matchdict = {}
      return view(self.request)
    if not requestPath.startswith(self.rootpath):
      raise HTTPNotFound()
    view = self.views[1]['view']
    self.request.matchdict = {
      'pyramid_controllers_path':
        # note that the URL-escaping going on here is *only* to emulate
        # what pyramid does... it is *NOT* the desired behavior though!
        urllib.unquote(requestPath[len(self.rootpath):])
      }
    return view(self.request)

  def assertResponse(self, res, status, body=None, location=None, xml=False):
    self.assertEqual(res.status_code, status)
    if body is not None:
      if xml:
        self.assertMultiLineEqual(xnl(res.body), xnl(body))
      else:
        self.assertMultiLineEqual(res.body, body)
    if location is not None:
      self.assertEqual(res.headers['Location'], location)

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
