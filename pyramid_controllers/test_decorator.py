# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2017/02/25
# copy: (C) Copyright 2017-EOT Cadit Inc., All Rights Reserved.
#------------------------------------------------------------------------------

import unittest
from inspect import isclass

from pyramid.httpexceptions import HTTPException, HTTPForbidden

from pyramid_controllers import \
  Controller, RestController, expose, lookup, expose_defaults
from .test_helpers import TestHelper

#------------------------------------------------------------------------------
class TestDecorator(TestHelper):

  #----------------------------------------------------------------------------
  def test_expose_with_other_decorators(self):
    def validate(action):
      def _wrapper(wrapped):
        def _validate(self, request, *args, **kw):
          if isclass(action) and issubclass(action, HTTPException):
            raise action()
          return wrapped(self, request, *args, **kw)
        _validate.__doc__ = wrapped.__doc__
        for key, value in wrapped.__dict__.items():
          setattr(_validate, key, value)
        return _validate
      return _wrapper
    class Root(Controller):
      @expose
      def plain(self, request): return 'ok:' + request.path
      @expose
      @validate(HTTPForbidden)
      def forbidden(self, request): return 'ok:' + request.path
      @expose
      @validate(None)
      def allowed(self, request): return 'ok:' + request.path
    root = Root()
    self.assertResponse(self.send(root, '/plain'),                    200, 'ok:/plain')
    self.assertResponse(self.send(root, '/forbidden'),                403)
    self.assertResponse(self.send(root, '/allowed'),                  200, 'ok:/allowed')


#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------
