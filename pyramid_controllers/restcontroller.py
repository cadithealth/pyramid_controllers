# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.restcontroller
# desc: provides a REST-based object dispatcher for pyramid_controllers
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2012/10/26
# copy: (C) Copyright 2012 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

# todo: review the following resources to make sure that all bases are covered:
#   - https://github.com/TurboGears/tg2/blob/master/tg/controllers/restcontroller.py
#   - https://bitbucket.org/percious/crank/src/15245a449614/crank/restdispatcher.py

import re
from pyramid.httpexceptions import HTTPMethodNotAllowed
from .controller import Controller
from .decorator import index
from .util import getMethod
from .dispatcher import getDispatcherFromStack, Dispatcher

HTTP_METHODS = (

  # shamelessly scrubbed from:
  #   http://annevankesteren.nl/2007/10/http-methods
  # todo: need to do some real research and bump this.

  # RFC 2616 (HTTP 1.1):
  'OPTIONS',
  'GET',
  'HEAD',
  'POST',
  'PUT',
  'DELETE',
  'TRACE',
  'CONNECT',

  # RFC 2518 (WebDAV):
  'PROPFIND',
  'PROPPATCH',
  'MKCOL',
  'COPY',
  'MOVE',
  'LOCK',
  'UNLOCK',

  # RFC 3253 (WebDAV versioning):
  'VERSION-CONTROL',
  'REPORT',
  'CHECKOUT',
  'CHECKIN',
  'UNCHECKOUT',
  'MKWORKSPACE',
  'UPDATE',
  'LABEL',
  'MERGE',
  'BASELINE-CONTROL',
  'MKACTIVITY',

  # RFC 3648 (WebDAV collections):
  'ORDERPATCH',

  # RFC 3744 (WebDAV access control):
  'ACL',

  # draft-dusseault-http-patch:
  'PATCH',

  # draft-reschke-webdav-search:
  'SEARCH',

)

def meth2action(meth):
  return re.sub('[^a-z]+', '_', meth.lower())

def action2meth(action):
  return re.sub('[^A-Z]+', '-', action.upper())

#------------------------------------------------------------------------------
class RestController(Controller):

  #----------------------------------------------------------------------------
  @index(forceSlash=False)
  def index(self, request, *args, **kw):
    method     = meth2action(getMethod(request))
    dispatcher = getDispatcherFromStack() or Dispatcher(autoDecorate=False)
    remainder  = [method]
    handler    = dispatcher.getNextHandler(request, self, remainder)
    if not handler:
      return HTTPMethodNotAllowed()
    # TODO: would this hack be "much better solved" by using @lookup instead?...
    # *** HACKALERT *** HACKALERT *** HACKALERT *** HACKALERT *** HACKALERT ***
    # TODO: this is an *elaborate* hack to keep the "sub" dispatcher from
    #       rendering the response... since it will be rendered when i return
    #       it here... (to address issue #2)
    class SnagException(Exception): pass
    def snagger(request, handler):
      raise SnagException(handler(request))
    try:
      return dispatcher.handle(request, self, handler, 'expose', remainder, [snagger])
    except SnagException as se:
      # NOTE: this `_restcontroller_snaghack` is GROSS! it basically
      #       is a major, super-ugly, disgusting hack-on-a-hack that
      #       allows the RestController method to override the
      #       "renderer" in its @expose().
      request._restcontroller_snaghack = (handler, 'expose')
      return se.args[0]
    # /HACKALERT
    # THE OLD NON-HACK WAY (but that breaks `@wrap` handling)
    # # TODO: this feels wrong... perhaps this should be using @lookup instead?...
    # return dispatcher.handle(request, self, handler, 'expose', remainder, [])

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
