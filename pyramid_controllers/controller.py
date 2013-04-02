# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.controller
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2012/10/26
# copy: (C) Copyright 2012 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
Provides an abstract interface for controllers in
pyramid_controllers. The base class provides the following attributes:

* ``Controller().request``::

  When a controller is instantiated for a particular request (for
  example, during a @lookup() resolution), then the ``request``
  constructor parameter can point to this request, which will in
  turn be made the value of ``self.request``. Defaults to ``None``.

* ``Controller()._pyramid_controllers``::

  Attribute reserved for storing pyramid_controllers' specific
  settings and helper functions. There is currently no possibility
  of being able to control the name of this attribute.
'''

from .util import adict

#------------------------------------------------------------------------------
class Controller(object):
  '''
  The base class of any traversable object in pyramid_controllers that
  is capable of receiving a request during dispatch.
  '''

  #----------------------------------------------------------------------------
  def __init__(self, request=None, expose=True):
    '''
    Constructor, accepts the following parameters:

    :param request:

      The :class:`pyramid.request.Request` object that this controller
      is specifically being instantiated to handle. If this controller
      is being instantiated as a singleton (the **MUCH** preferred
      approach), then `request` must be ``None`` (the default).

    :param expose:

      Whether or not this object is exposed to standard request
      dispatching when it is an attribute of another
      Controller. Typically, this is set to ``True`` (the default),
      however when a Controller is being used as a lookup handler, it
      is useful to be able to advertise it's presence. For example::

        class RootController(Controller):
          model = ModelDispatcher()

        class ModelDispatcher(Controller):
          MODELID = ModelController(expose=False)
          @lookup
          def _lookup(self, request, path, *rem):
            request.model = get_model_for_id(path)
            return (self.MODELID, *rem)

        class ModelController(Controller):
          @expose
          def action(self, request):
            return Response(...)

      would create a URL pattern ``/model/{MODELID}/action`` which is
      not directly invocable unless "MODELID" is replaced with a valid
      model id. Benefits to this approach (rather than creating the
      ModelController on the fly) are that:

      * The ModelController only needs to be instantiated once.

      * The URL pattern /model/{MODELID}/action can be auto-discovered
        (if one assumes the convention that non-exposed attribute
        controlers are lookup-targets).
    '''
    self._pyramid_controllers = adict(expose=expose)
    self.request = request

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
