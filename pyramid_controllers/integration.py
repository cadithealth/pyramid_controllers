# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.pyramid
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/02/12
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
``pyramid_controllers.pyramid`` offers the pyramid-specific way of
integrating the controller-based request dispatch mechanism.
'''

from .dispatcher import Dispatcher

#------------------------------------------------------------------------------
def add_controller(self,
                   route_name, pattern, controller,
                   dispatcher=None,
                   **kw):
  '''

  :param route_name:

    [required] Specify a route_name for this controller and it's
    decendant controllers.

  :param pattern:

    [optional] The URL entrypoint to attach the `controller` to. Note
    that this is a RegEx prefix-match (excluding any trailing slash).
    For example, ``'/foo/'`` will match requests for ``/foo``,
    ``/foo/bar``, and ``/foo/bar/``. Any standard URI pattern matching
    will, as usual, be made available in the ``request.matchdict``, but
    will not have any effect on the controller tree resolution.

  :param controller:

    [required] Either a dotted-string or an instance of a subclass of
    the :class:`pyramid_controllers.Controller` class to mount at the
    specified URL entrypoint specified by `pattern`.

  :param dispatcher:

    [optional] overrides the default dispatcher routine. If not
    specified, a default :class:`pyramid_controllers.Dispatcher` will
    be used (with all default options, including `defaultForceSlash`
    enabled).

  Any additional keyword parameters will be passed through to the
  `config.add_route()` call.

  '''

  # TODO: add a parameter that controls the name of the "require"
  #       attribute?...

  # normalizing controller anchor point to not include a trailing "/"
  # (so that index requests without it can be handled, and, if the
  # @index specifies it, can redirect with the appended slash)

  if pattern is None:
    pattern = ''
  if pattern.endswith('/'):
    pattern = pattern[:-1]

  controller = self.maybe_dotted(controller)

  # TODO: add permission walking...

  dispatcher = dispatcher or Dispatcher()

  # pyramid's routing fails to match subdirectories if the controller
  # is anchored at "/", thus building a workaround... otherwise i would
  # simply do this:
  #   pattern += '{pyramid_controllers_path:(/.*)?$}'
  # and only have a single route/view... UGH.

  # trap requests to the controller anchor URL
  def handleIndexRequest(request):
    request.matchdict['pyramid_controllers_path'] = '/'
    return dispatcher.dispatch(request, controller)
  self.add_route(route_name + '-index', pattern=pattern, **kw)
  self.add_view(view=handleIndexRequest, route_name=route_name + '-index')

  # trap requests to child content/directories...
  def handleContentRequest(request):
    # TODO: it seems that request.path is NOT pre-url-escaped
    #       but request.matchdict['pyramid_controllers_path'] *is*...
    #       therefore i need to use that in order to ensure that
    #       components are resolved as expected...
    request.matchdict['pyramid_controllers_path'] = '/' + request.matchdict['pyramid_controllers_path']
    return dispatcher.dispatch(request, controller)
  self.add_route(route_name, pattern=pattern + '/{pyramid_controllers_path:.*$}', **kw)
  self.add_view(view=handleContentRequest, route_name=route_name)

#------------------------------------------------------------------------------
def includeme(config):
  config.add_directive('add_controller', add_controller)

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
