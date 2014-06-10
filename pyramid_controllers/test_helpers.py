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

import unittest
from webtest import TestApp
from pyramid.config import Configurator

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

  def makeApp(self, controller,
              path=None, name=None, dispatcher=None, config_hook=None):
    config = Configurator(settings={})
    config.include('pyramid_controllers')
    try:
      config.include('pyramid_tm')
    except ImportError:
      pass
    config.add_controller(name or 'root', path or '/', controller, dispatcher)
    for name, factory in self.renderers.items():
      config.add_renderer(name, factory)
    if config_hook:
      config_hook(config)
    return config.make_wsgi_app()

  def send(self, rootController, requestPath,
           method=None, rootPath=None, dispatcher=None, config_hook=None):
    testapp = TestApp(self.makeApp(
      rootController,
      path        = rootPath,
      dispatcher  = dispatcher,
      config_hook = config_hook,
    ))
    call = getattr(testapp, (method or 'GET').lower())
    response = call(requestPath, status='*')
    return response

  def assertResponse(self, res, status, body=None, location=None, xml=False):
    self.assertEqual(res.status_code, status)
    if body is not None:
      if xml:
        # todo: compare parsed XML
        self.assertMultiLineEqual(xnl(res.body), xnl(body))
      else:
        self.assertMultiLineEqual(res.body, body)
    if location is not None:
      self.assertEqual(res.headers['Location'], location)
    return res

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
