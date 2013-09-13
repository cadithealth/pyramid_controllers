===================
pyramid_controllers
===================

The ``pyramid_controllers`` package is a pyramid plugin that provides
de-centralized hierarchical object dispatch, similar to how the
standard TurboGears request dispatch works. You may also be interested
in the pyramid-describe_ package, which can make these controllers
self-documenting.

TL;DR
=====

Install:

.. code-block:: bash

  $ pip install pyramid-controllers

Use:

.. code-block:: python

  # the following application serves these URLs:
  #   /
  #   /about/team
  #   /about/mission
  #   /resource/{RESOURCE_ID}   (RESTful: GET and PUT)

  # standard pyramid-controller imports
  from pyramid_controllers import \
    Controller, RestController, \
    expose, expose_defaults, index, default, lookup, fiddle

  # create a controller for "/about/team" and "/about/mission"
  class AboutController(Controller):
    @expose(renderer='mymodule:path/to/template.mako')
    def team(self, request): return dict(team=get_team_members())
    @expose
    def mission(self, request): return 'Our mission: rock the world.'

  # create a RESTful (GET, PUT) controller for "/resource/{RESOURCE_ID}"
  class ResourceController(RestController):
    @expose
    def get(self, request): return 'Name: ' + request.res.name
    @expose
    def put(self, request):
      request.res.name = request.params.get('name')
      return self.get(request)

  # create the dispatcher that will lookup resources by ID
  class ResourceDispatcher(Controller):
    RESOURCE_ID = ResourceController(expose=False)
    @lookup
    def lookup(self, request, res_id, *rem):
      request.res = get_resource_by_id(res_id)
      return (self.RESOURCE_ID, rem)

  # the root controller with support for "/" and sub-controllers
  class RootController(Controller):
    about = AboutController()
    resource = ResourceDispatcher()
    @index
    def index(self, request):
      return HTTPFound('/about/mission')

  # and hook it all into pyramid in the app's main()
  def main(global_config, **settings):
    # ... (the usual pyramid startup calls) ...
    config.include('pyramid_controllers')
    config.add_controller('root', '/', RootController())


Installation
============

You can manually install it by running:

.. code-block:: bash

  $ pip install pyramid-controllers

However, a better approach is to use standard python distribution
utilities, and add pyramid_controllers as a dependency to your
project's `install_requires` parameter in your ``setup.py``. Then run
a ``python setup.py develop``.

Then, enable the package either in your INI file via:

.. code-block:: text

  pyramid.includes = pyramid_controllers

or with code in your package's application initialization via:

.. code-block:: python

  def main(global_config, **settings):
    # ...
    config.include('pyramid_controllers')
    # ...

Usage
=====

Now that your pyramid application has access to the plugin, anchor the
root controller to a URL entrypoint via the
``config.add_controller()`` method. Note that unlike many of the other
controller approaches, a pyramid_controller route takes control of all
URLs that are prefixed with the specified entrypoint. For example, the
following:

.. code-block:: python

  def main(global_config, **settings):
    # ...
    config.include('pyramid_controllers')
    # ...
    config.add_controller('rootController', '/root', '.controllers.RootController')
    # ...

will allow the class ``.controllers.RootController`` to handle any request
for the URL ``/root`` or URLs that start with ``/root/...``.

Concept
=======

The basic gist of pyramid_controllers is that for any incoming URL, it
will be split into components based on forwarded slashes ("/") and
sequentially lookup the controller in the series while applying name
lookups, defaulting, access control, and generic request manipulation.

For example, assuming that ``RootController`` is anchored at "/", then
the following code will handle a request for ``/how/are/you`` by responding
with the "A-OK!" response.

.. code-block:: python

  from pyramid_controllers import Controller, expose

  # NOTE: These classes are defined in order of semantic use. For this
  #       to actually work, the controllers would need to be defined
  #       before they are invoked (so in opposite order), of course.

  class RootController(Controller):
    how = HowController()

  class HowController(Controller):
    are = AreController()

  class AreController(Controller):
    @expose
    def you(self, request):
      return 'A-OK!'

Here, the initial request is received by ``RootController``. A lookup
of the "how" attribute finds that it is associated with another
controller, so the request is dispatched to that object. The same
thing happens when the ``HowController`` receives the request, which
in turn dispatches it to the ``AreController``. When the framework
does a lookup of the "you" attribute, it finds that it is a method. To
control which methods are invocable via a URL, you must define the
method to be exposed to the framework via the ``@expose`` decorator.

At this point the framework hands the request to the object's method for
handling, providing the active ``request`` object as the first parameter,
in standard pyramid fashion.

TODO: add documentation about the various supported response and
exception types.

Controllers
===========

There exist several classes that can be subclassed to produce
controller classes:

* **pyramid_controllers.Controller**: this class is the base class
  of all controllers, and does not provide much functionality other
  than allowing the framework to know that a class is intended to
  handle requests in a pyramid_controllers approach.

* **pyramid_controllers.RestController**: this class routes the
  various RESTful verbs to controller methods by the same name
  (note that the method names are lower-cased).

Here is an example of the RestController, which will accept any of the
standard HTTP verbs (GET, PUT, POST, DELETE) to the URL "/hello" and
will emit a response that simply reflects the method used (with a
little poetic licence thrown in):

.. code-block:: python

  from pyramid_controllers import Controller, RestController

  class RootController(Controller):
    hello = ReflectController()

  class ReflectController(RestController):
    @expose
    def get(self, request):
      return 'I am *not* a dog, go GET it yourself!'
    @expose
    def put(self, request):
      return 'Apparently you golf. PUTting is just part of the game.'
    @expose
    def post(self, request):
      return 'People use email today, silly. Stop using the POST!'
    @expose
    def delete(self, request):
      return 'Hey! This is not the CIA, you cannot just DELETE me!'


Decorators
==========

There are several decorators provided by the pyramid_controllers
package that influence how a request is handled, as follows:

* **@expose**: the most common decorator, it simply declares that the
  decorated method is intended to handle incoming requests, and is
  therefore "exposed" to the request traversal and dispatching. Note
  that although it is exposed, access control restrictions may
  restrict who can actually access it.

* **@index**: declares that the decorated method is the method that
  will handle the request if no further components in the URL path
  exist. Think of this as the ``index.html`` in an htdocs directory.

* **@default**: if the standard component traversal strategy fails to
  match either a sub-controller or an exposed method to handle a
  request, then the framework searches for a method that has been
  decorated as a ``@default`` or ``@lookup`` method (``@lookup``
  decorators take precedence). The default method is expected to
  behave identically to an "exposed" method in that it should respond
  to the request.

* **@lookup**: similar to the ``@default`` decorator, the ``@lookup``
  decorator is invoked when the framework could not find another
  method or sub-controller to handle the request. The @lookup method,
  unlike the @default method, is **not** expected to handle the actual
  request, but instead to return a new controller with which the
  framework will continue the hierarchical request handling. See below
  for details on what parameters are passed and what is expected to be
  returned.

* **@fiddle**: a method declared as a "fiddler" will be called before
  any other method in the given controller and is expected to do
  nothing more than alter the request in some way (such as add
  additional attributes) or throw an exception. A fiddler method
  **MUST NOT** actually respond to a request via standard methods,
  however it can raise exceptions (such as ``HTTPForbidden``), which
  will terminate request dispatching.

* **@expose_defaults**: a Controller class decorator that sets default
  parameters for @expose, @index, and @default methods, such as the
  default renderer and extensions.


Complex Example
===============

.. code-block:: python

  from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound

  # import the controller base classes
  from pyramid_controllers import Controller, RestController

  # import the decorators
  from pyramid_controllers import expose, index, lookup, default, fiddle

  class RootController(Controller):
    public = PublicController()
    admin  = AdminController()
    member = MemberDispatchController()

  class PublicController(Controller):
    login = AuthController()
    @expose
    def about(self, request):
      return 'We are a snazy company!'

  class AuthController(RestController):
    @expose
    def get(self, request):
      return '<html><form><input name="u"/><input name="p"/></form></html>'
    @expose
    def post(self, request):
      # todo: perform authentication...

  class AdminController(Controller):
    @fiddle
    def checkAuth(self, request):
      if userHasAdminAccess(request): return
      raise HTTPForbidden()
    @index
    def index(self, request):
      return 'View the list of <a href="users">active users</a>.'
    @expose
    def users(self, request):
      return '<ul><li>you</li></ul>'

  class MemberDispatchController(Controller):
    @fiddle
    def checkAuth(self, request):
      if userHasMemberAccess(request): return
      raise HTTPForbidden()
    @lookup
    def _lookup(self, username, *rem):
      user = findUserByUsername(username)
      if not user:
        raise HTTPNotFound()
      return (MemberController(user), rem)

  class MemberController(Controller):
    def __init__(self, user):
      self.user = user
    @index
    def index(self, request):
      return 'Hi, my name is ' + self.user.name
    @expose
    def age(self, request):
      return 'I am %d years old.' % (self.user.age,)
    @default
    def _default(self, request, attribute, *rem):
      return 'My "%s" is "%r".' % (attribute, getattr(self.user, attribute))


.. _pyramid-describe: https://pypi.python.org/pypi/pyramid_describe
