# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_controllers.describe
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/03/11
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
The `pyramid_controllers.describe` module provides the
:class:`DescribeController` class which can output information about a
controller hierarchy in either as plain-text tree, reStructuredText,
HTML, WADL, YAML, or XML descriptor file.
'''

# TODO: the Entry.isLeaf is not a useful concept, as it implies that
#       a node is either a leaf or a branch, but controllers can be both...
#       (due to the @index decorator). so, move to something like
#       Entry.isHandler methinks...

import os, types, re, textwrap, inspect, cgi, json
import xml.etree.ElementTree as ET
from pyramid.response import Response
from pyramid.settings import asbool
from .controller import Controller
from .restcontroller import RestController, meth2action, action2meth, HTTP_METHODS
from .decorator import expose, index
from .dispatcher import getDispatcherFromStack, Dispatcher
from .util import adict, pick, getVersion, isstr

HTTP_METHODS_NORM = [meth2action(v) for v in HTTP_METHODS]

#------------------------------------------------------------------------------
class Entry(adict):
  '''
  Represents an entry in the controller hierarchy. Entries can have
  the following attributes:

    name
      The name of the entry, relative to the parent entry.
    parent
      A reference to the parent entry.
    controller
      If defined, a reference to the Controller instance that
      this entry represents.
    handler
      If defined, a reference to the method or class that
      this entry represents.
    method
      The name of the HTTP method for RESTful verb entries.
    isMethod
      True IFF the parent is a RestController and this is
      a RESTful verb handler.
    isHandler
      True IFF it is an endpoint that is capable of handling
      requests. this is always true if `handler` is defined,
      but not necessarily the case if `controller` is defined.
      the latter is only the case IFF an @index has been defined
      for the controller.
    isLeaf
      True IFF there are no URL entries beyond this point.
    isIndirect
      True IFF the dispatcher will not send requests directly
      at this controller - typically that means it must be
      returned via a @lookup method.
    isRest
      True IFF the `controller` is an instance of RestController.
    isUndef
      True IFF the `handler` is not an inspectable class (i.e.
      it is not an instantiated method)
    parents
      A generator of entry parents, starting with the closest first.
    rparents
      A reversed version of `parents`, ie. starting at the root first.

  An entry can have many more attributes however, including the
  following which are added by the default implementation of
  :meth:`Dispatcher.decorateEntry()`:

    doc
      The documentation for this entry.
    path
      The full path to this entry.
    dname
      The "decorated" version of `name`.
    dpath
      The "decorated" version of `path`.

  '''
  @property
  def parents(self):
    entry = self
    while entry.parent:
      yield entry.parent
      entry = entry.parent
  @property
  def rparents(self):
    if self.parent:
      for parent in self.parent.rparents:
        yield parent
      yield self.parent

#------------------------------------------------------------------------------
def normLines(text, indent=None):
  if not text:
    return ''
  text = str(text).replace('\r\n', '\n').replace('\r', '\n')
  if not indent:
    return text
  return text.replace('\n', '\n' + ( ' ' * indent ))

#------------------------------------------------------------------------------
class DescribeController(Controller):
  # todo: the docstring for the class was originally the first sentence,
  #       and the full documentation was for the :meth:`index()` method.
  #       unfortunately, that means that the output documentation cannot
  #       be controlled from __init__ as::
  #         self.index.__doc__ = doc
  #       results in the following exception::
  #         AttributeError: attribute '__doc__' of 'instancemethod' objects is not writable
  '''
  Describes a pyramid-controller's path hierarchy in several different
  formats, include plain-text tree, reStructuredText, HTML, JSON,
  WADL, YAML, and XML. Depending on configuration and output format,
  the following parameters can be toggled to adjust the output as
  follows:

  * `pruneIndex`:    @index documentation is merged into the controller.
  * `showSelf`:      DescribeController entry is displayed.
  * `showRest`:      lists supported RESTful methods.
  * `showImpl`:      shows implementation resolver path.
  * `showInfo`:      shows documentation.
  * `showDynamic`:   shows presence of dynamically evaluated attributes.
  * `maxdepth`:      limits the number of path components to display.
  * `width`:         the width of text-based output (default: 79).

  With some exceptions, options are derived from the following sources
  descending order of preference (i.e. the first source overrides the
  last source):

  * instance-specific override options (provided in the constructor)
  * format-specific override options
  * request.override dictionary
  * request parameters (i.e. provided by the user) -- see below
  * request.options dictionary
  * format-specific default options
  * instance-specific default options (provided in the constructor)
  * default options

  The following options cannot be controlled by the user:

  * `restVerbs`
  * `showUnderscore`
  * `showUndoc`

  Note that `maxdepth` specifies the maximum controller depth to
  descend -- this is primarily to avoid endless loops since detection
  of circular references is currently not implemented. Defaults to
  1024.
  '''

  xmlns = dict(
    wadl = 'http://research.sun.com/wadl/2006/10',
    xsd  = 'http://www.w3.org/2001/XMLSchema',
    xsi  = 'http://www.w3.org/2001/XMLSchema-instance',
    doc  = 'http://github.com/cadithealth/pyramid_controllers/xmlns/0.1/doc',
    )

  wadlTypeRemap = {
    'int': 'xsd:int',
    'str': 'xsd:string',
    }

  legend = (
    ('{NAME}',
     'Placeholder -- usually replaced with an ID or other'
     ' identifier of a RESTful object.'),
    ('<NAME>',
     'Not an actual endpoint, but the HTTP method to use.'),
    (u'¿NAME?',
     'Dynamically evaluated endpoint, so no further information can be'
     ' determined without specific contextual request details.'),
    (Dispatcher.NAME_DEFAULT,
     'This endpoint is a `default` handler, and is therefore free to interpret'
     ' path arguments dynamically, so no further information can be determined'
     ' without specific contextual request details.'),
    (Dispatcher.NAME_LOOKUP,
     'This endpoint is a `lookup` handler, and is therefore free to interpret'
     ' path arguments dynamically, so no further information can be determined'
     ' without specific contextual request details.'),
    )

  #----------------------------------------------------------------------------
  def __init__(self, root,
               formats=('txt', 'rst', 'html', 'json', 'wadl', 'yaml', 'xml'),
               path=None, restVerbs=None, doc=None,
               include=None, exclude=None,
               options=None, override=None,
               *args, **kw):
    '''
    Initializes a DescribeController. Accepts the following parameters
    (in addition to the standard :class:`Controller` parameters),
    where only `root` is required:

    :param root:

      The starting controller that will be inspected to extract the
      URL tree. Note that all sub-controllers and methods will be
      described unless limited by the `include` and `exclude`
      parameters. Controller attributes that are not instances (i.e.
      classes) are assumed to be dynamically instantiated for a
      request and can therefore not be inspected and traversed.

    :param formats:

      A list of formats that are allowed to be generated. Currently
      supported formats include: 'txt', 'rst', 'html', 'json', 'wadl',
      'yaml', 'xml', and 'et', respectively for output in plain-text
      hierarchy, reStructuredText, HTML, JSON, WADL, YAML, XML, and
      ElementTree. The default set includes all supported formats
      except 'et' as it, unlike the others, does not directly render
      to a Response() object.

    :param path:

      The path that `root` is anchored at, which defaults to '/'.

    :param restVerbs:

      Specify the list of "known HTTP verbs". If not provided,
      defaults to
      :const:`pyramid_controllers.restcontroller.HTTP_METHODS`.  This
      list is used when documentation about a RestController sub-class
      is being constructed: methods that are found in this list will
      be specially marked as "RESTful" and treated differently,
      whereas methods that are not in this list will be treated
      normally by the dispatcher.

    :param doc:

      Overrides the Controller.__doc__ -- primarily intended to
      allow callers to control the documentation of this endpoint
      in the output. See also `options.showSelf`.

    :param include:

      A regular expression (or list of regular expressions) that each
      endpoint's full path name (including `path`) will be matched
      against to determine if it should be included in the output. If
      a list, any match will cause the endpoint to be included. If not
      specified, all endpoints will be included. See also `exclude`.

      Note that the regular expression can be either a string, or
      an already-compiled :class:`re.RegexObject` object.

    :param exclude:

      Similar to the `include`, but any matches will remove the
      endpoint from the output. `include`'s are applied first, and
      then `exclude`'s.

    :param options:

      Specifies the default options to use. See
      :class:`DescribeController` for a list of all available options.

    :param override:

      Specifies the override options to use. See
      :class:`DescribeController` for a list of all available options.

    '''
    # todo: instruct the dispatcher that i can accept extension modifiers
    super(DescribeController, self).__init__(*args, **kw)
    if not isinstance(root, Controller):
      raise TypeError(
        'the DescribeController `root` parameter must be a Controller, not %r'
        % (type(root),))
    self._root     = root
    self.path      = re.sub('/*$', '', (path or '').strip()) or '/'
    self.formats   = formats or ('txt', 'rst', 'html', 'json', 'wadl', 'yaml', 'xml')
    self.restVerbs = [meth2action(v) for v in restVerbs] if restVerbs \
        else HTTP_METHODS_NORM
    self.options   = adict(options or {})
    self.override  = adict(override or {})
    if doc is not None:
      self.__doc__ = doc
    self.include   = include
    self.exclude   = exclude
    if self.include:
      if isstr(self.include):
        self.include = [self.include]
      self.include = [re.compile(expr) if isstr(expr) else expr
                      for expr in self.include]
    if self.exclude:
      if isstr(self.exclude):
        self.exclude = [self.exclude]
      self.exclude = [re.compile(expr) if isstr(expr) else expr
                      for expr in self.exclude]

  #----------------------------------------------------------------------------
  def _getOptions(self, request, format=None):
    # todo: make options and override pull values from
    #       request.registry.settings as well...
    ret = adict(self.options)
    if format is not None:
      ret.update(getattr(self, 'options_' + format, None))
    ret.update(getattr(request, 'options', None))
    ret.update(request.params)
    ret.update(getattr(request, 'override', None))
    if format is not None:
      ret.update(getattr(self, 'override_' + format, None))
    ret.update(self.override)
    return ret

  #----------------------------------------------------------------------------
  @index(forceSlash=False)
  def index(self, request):
    options = adict(
      format         = self._getOptions(request).get('format'),
      restVerbs      = self.restVerbs,
      showUnderscore = asbool(self.options.get('showUnderscore', False)),
      showUndoc      = asbool(self.options.get('showUndoc', True)),
      )
    if options.format not in self.formats:
      options.format = self.formats[0]
    # get the generic options using fallback rules as defined in
    # the class documentation.
    cur_options = self._getOptions(request, options.format)
    # load the boolean options
    for name, default in (
      ('showLegend',     True),
      ('showBranches',   False),
      ('pruneIndex',     True),
      ('showSelf',       True),
      ('showRest',       True),
      ('showImpl',       False),
      ('showInfo',       True),
      ('showDynamic',    True),
      ('showGenerator',  True),
      ('showGenVersion', True),
      ('showLocation',   True),
      ):
      options[name] = asbool(cur_options.get(name, default))
    # load the integer options
    for name, default in (
      ('maxdepth',       1024),
      ('width',          79),
      ('maxDocColumn',   None),
      ('minDocLength',   20),
      ):
      try:
        if name in cur_options:
          options[name] = int(cur_options.get(name))
        else:
          options[name] = default
      except (ValueError, TypeError):
        options[name] = default
    options.dispatcher = getDispatcherFromStack() or Dispatcher(autoDecorate=False)
    options.request    = request
    entries = self._walkEntries(options)
    return getattr(self, 'format_' + options.format)(options, entries)

  #----------------------------------------------------------------------------
  def _walkEntries(self, options, entry=None):
    # todo: what about detecting circular references?...
    for ent in self._listAllEntries(options, entry):
      fent = self.filterEntry(options, ent)
      if fent and ( ent.isHandler or options.showBranches ):
        yield ent
      # todo: this maxdepth application is inefficient...
      if options.maxdepth is not None \
          and len(list(ent.parents)) >= options.maxdepth:
        continue
      for subent in self._walkEntries(options, ent):
        fsubent = self.filterEntry(options, subent)
        if fsubent and ( subent.isHandler or options.showBranches ):
          yield subent

  #----------------------------------------------------------------------------
  def _listAllEntries(self, options, entry):
    if entry is None:
      yield self.controller2entry(options, '', self._root, entry)
      return
    if entry.controller:
      for name, attr in options.dispatcher.getEntries(entry.controller, includeIndirect=True):
        if not options.showUnderscore and name.startswith('_'):
          continue
        if not options.showSelf and attr is self:
          continue
        if options.pruneIndex and name == '':
          continue
        # todo: DRY! see dispatcher for sharing...
        if isinstance(attr, Controller):
          subent = self.controller2entry(options, name, attr, entry)
          if subent:
            yield subent
          continue
        # todo: DRY! see dispatcher for sharing...
        if type(attr) in (types.TypeType, types.ClassType):
          subent = self.class2entry(options, name, attr, entry)
          if subent:
            yield subent
          continue
        subent = self.method2entry(options, name, attr, entry)
        if subent:
          yield subent

  #----------------------------------------------------------------------------
  def controller2entry(self, options, name, controller, parent):
    'Creates a Describer `entry` object for the specified Controller instance.'
    ret = Entry(name       = name,
                parent     = parent,
                controller = controller,
                isHandler  = True,
                isLeaf     = True,
                isIndirect = not controller._pyramid_controllers.expose,
                isRest     = isinstance(controller, RestController),
                )
    ret = self.decorateEntry(options, ret)
    for entry in self._listAllEntries(adict(options).update(showRest=True), ret):
      if ret.isRest and entry.isMethod:
        if ret.methods is None:
          ret.methods = []
        ret.methods.append(entry)
        continue
      ret.isLeaf = False
    if ret.isRest:
      ret.isHandler = True
    else:
      meta = options.dispatcher.getCachedMeta(controller)
      ret.isHandler = bool(meta.index)
    return ret

  #----------------------------------------------------------------------------
  def class2entry(self, options, name, klass, parent):
    'Converts an uninstantiated class to an entry.'
    if not options.showDynamic:
      return None
    ret = Entry(name       = name,
                parent     = parent,
                handler    = klass,
                isHandler  = True,
                isLeaf     = True,
                isUndef    = True,
                )
    return self.decorateEntry(options, ret)

  #----------------------------------------------------------------------------
  def method2entry(self, options, name, method, parent):
    'Converts an object method to an entry.'
    ret = Entry(name       = name,
                parent     = parent,
                handler    = method,
                isHandler  = True,
                isLeaf     = True,
                )
    if parent and isinstance(parent.controller, RestController) \
        and name in options.restVerbs:
      if not options.showRest:
        return None
      ret.method   = action2meth(name)
      ret.isRest   = True
      ret.isMethod = True
    return self.decorateEntry(options, ret)

  #----------------------------------------------------------------------------
  def filterEntry(self, options, entry):
    '''
    Checks to see if the specified `entry` should be included in the
    output. The returned object should either be the `entry`
    (potentially modified) or ``None``. In the latter case, the entry
    will be removed from the output.
    '''
    if self.include:
      match = False
      for include in self.include:
        if include.match(entry.path):
          match = True
          break
      if not match:
        return None
    if self.exclude:
      for exclude in self.exclude:
        if exclude.match(entry.path):
          return None
    return entry

  #----------------------------------------------------------------------------
  def decorateEntry(self, options, entry):
    '''
    Decorates the entry with additional attributes that may be useful
    in rendering the final output. Specifically, the following
    attributes are populated as and if possible:

    * `path`:  full path to the entry.
    * `dpath`: the full "decorated" path to the entry.
    * `ipath`: the full resolver path to the class or method.
    * `doc`:   the docstring for the entry or the index (see pruneIndex).

    Sub-classes may override & extend this functionality - noting that
    the returned object can either be the original decorated `entry`
    or a new one, in which case it will take the place of the passed-in
    entry.

    Although DescribeController does not extract or otherwise
    determine any attributes beyond the above specified attributes,
    there are additional attributes that some of the formatters will
    take advantage of. For this reason, sub-classes are encouraged to
    further decorate the entries where possible with the following
    attributes:

    * `params`: a list of objects that represent parameters that this
      entry accepts. The objects can have the following attributes:
      `name`, `type`, `optional`, `default`, and `doc`.

    * `returns`: a list of objects that documents the return values
      that can be expected from this method. The objects can have the
      following attributes: `type` and `doc`.

    * `raises`: a list of objects that specify what exceptions this
      method can raise. The objects can have the following attributes:
      `type` and `doc`.

    '''

    # determine the implementation path & type to this entry
    if entry.controller:
      kls = entry.controller.__class__
      entry.ipath = kls.__module__ + '.' + kls.__name__
      entry.itype = 'instance'
    elif entry.handler:
      if inspect.ismethod(entry.handler):
        entry.ipath = inspect.getmodule(entry.handler).__name__ \
            + '.' + entry.handler.__self__.__class__.__name__ \
            + '().' + entry.handler.__name__
        entry.itype = 'method'
      elif inspect.isfunction(entry.handler) \
            or inspect.isclass(entry.handler):
        entry.ipath = inspect.getmodule(entry.handler).__name__ \
            + '.' + entry.handler.__name__
        entry.itype = 'class' if inspect.isclass(entry.handler) else 'function'
      else:
        entry.ipath = entry.handler.__name__
        entry.itype = 'unknown'

    # determine the "decorated" path
    if entry.isIndirect:
      entry.dname = '{{{}}}'.format(entry.name)
    elif entry.isUndef:
      entry.dname = u'¿{}?'.format(entry.name)
    elif entry.isRest and entry.itype == 'method':
      entry.dname = '<{}>'.format(entry.method)
    else:
      entry.dname = entry.name

    # determine the full path (plain and "decorated") to this entry
    if not entry.parent:
      entry.path  = self.path
      entry.dpath = self.path
    else:
      entry.path  = entry.parent.path
      entry.dpath = entry.parent.dpath
    entry.path  = os.path.join(entry.path,  entry.name)
    entry.dpath = os.path.join(entry.dpath, entry.dname)

    # get the docstring
    if options.showInfo:
      entry.doc = inspect.getdoc(entry.controller or entry.handler)
      if options.pruneIndex and entry.controller:
        meta = options.dispatcher.getCachedMeta(entry.controller)
        for handler in meta.index or []:
          entry.doc = inspect.getdoc(handler) or entry.doc

    return entry

  #----------------------------------------------------------------------------
  def formattext_txt(self, options, text, width=None):
    return textwrap.fill(text, width=width or options.width)

  #----------------------------------------------------------------------------
  def formatdoc_txt(self, options, entry, width):
    '''
    Formats the `entry`'s documentation as plain-text to fit in the
    `width` specified. The default implementation simply collapses all
    whitespace and uses :meth:`textwrap.fill()` to wrap the resulting
    text, and then takes the first line with '...' appended if
    truncation occurred.

    Sub-classes are encouraged to perform more intelligent
    formatting.
    '''
    return textwrap.fill(entry.doc, width=width)

  #----------------------------------------------------------------------------
  def format_txt(self, options, entries):
    '''
    Formats the DescribeController output as a plain-text tree
    hierarchy.
    '''
    # TODO: handle entries with the same name... (ie. multi-condition aliasing)
    #         => this has ramifications on `entry._dlast`...
    ret = []
    # in order to show the tree nicely, i need to re-insert all branch
    # entries into the entry stream, but they're documentation should not
    # be shown... thus marking all current entries with '_dtext'. also
    # re-sorting by name unless RESTful - this is so that RESTful methods
    # show up first (since they technically don't exist in the URL path).
    def entcmp(e1, e2):
      if e1.parent is not e2.parent:
        return cmp(e1.path, e2.path)
      r1 = bool(e1.isMethod and e1.isRest)
      r2 = bool(e2.isMethod and e2.isRest)
      if r1 == r2:
        return cmp(e1.name, e2.name)
      if r1:
        return -1
      return 1
    entries = sorted(list(entries), cmp=entcmp)
    fullset = []
    last = None
    for entry in entries:
      entry._dtext = True
      if entry.parent and entry.parent not in fullset:
        toadd = []
        for parent in entry.parents:
          if parent not in fullset:
            toadd.append(parent)
            continue
          break
        fullset.extend(reversed(toadd))
      last = entry
      fullset.append(last)
    entries = fullset
    # decorate entries with '_dlast' attribute...
    for entry in entries:
      if entry.parent:
        if entry.parent._dchildren is None:
          entry.parent._dchildren = []
        entry.parent._dchildren.append(entry)
    for entry in entries:
      if entry._dchildren:
        entry._dchildren[-1]._dlast = True
    # generate the hierarchy
    for entry in entries:
      cur = ''
      indent = ''
      rparents = list(entry.rparents)
      for c in rparents[1:]:
        indent += '    ' if c._dlast else '|   '
      if len(rparents) > 0:
        cur += indent + ( '`-- ' if entry._dlast else '|-- ' )
        indent += '    ' if entry._dlast else '|   '
      else:
        cur += indent + self.path
      cur += entry.dname
      if not entry.isLeaf and not cur.endswith('/'):
        cur += '/'
      ret.append(cur)
    # add the documentation
    # note: this length check (entries vs ret) is currently redundant
    # (they will always be the same... but just in case someone
    # changes the code above without realizing this dependency
    # here...)
    if options.showInfo and len(entries) == len(ret) and len(ret) > 0:
      tlen = max([len(e) for e in ret]) + 3
      if options.maxDocColumn and tlen > options.maxDocColumn:
        tlen = options.maxDocColumn
      # the minus three here is to account for the addition of " # "
      # in the text formatting.
      dlen = options.width - tlen - 3
      if options.minDocLength and dlen < options.minDocLength:
        dlen = options.minDocLength
      # force an absolute minimum of 3 characters...
      if dlen >= 3:
        for idx, entry in enumerate(entries):
          if not entry.doc or not entry._dtext:
            continue
          doc = self.formattext_txt(options, entry.doc, options.width)
          doc = doc.strip().replace('\n', ' ')
          if len(doc) > dlen:
            doc = doc[:dlen - 3] + '...'
          ret[idx] = u'{l: <{w}} # {d}'.format(l=ret[idx], w=tlen, d=doc)
    resp = Response('\n'.join(ret) + '\n', content_type='text/plain')
    resp.charset = 'UTF-8'
    return resp

  #----------------------------------------------------------------------------
  def formattext_rst(self, options, text, width):
    return self.formattext_txt(options, text, width)

  #----------------------------------------------------------------------------
  def formatdoc_rst(self, options, entry, width):
    '''
    Formats the `entry`'s documentation as plain-text to fit in the
    `width` specified. The default implementation simply collapses all
    whitespace and uses :meth:`textwrap.fill()` to wrap the resulting
    text. Sub-classes are encouraged to perform more intelligent
    formatting.
    '''
    return entry.doc

  #----------------------------------------------------------------------------
  def format_rst(self, options, entries):
    '''
    Formats the DescribeController output as reStructuredText.
    '''
    ret = '# Contents of "{}"\n\n'.format(self.path)
    # TODO: handle entries with the same name... (ie. multi-condition aliasing)
    # TODO: i18n...
    for entry in entries:
      if entry.isRest and entry.itype == 'method':
        continue
      ret += '## ' + entry.dpath
      if not entry.isLeaf:
        if not ret.endswith('/'):
          ret += '/'
      ret += ':\n\n'
      if options.showImpl and entry.ipath:
        ipath = entry.ipath
        if entry.itype == 'instance':
          ipath += '()'
        ret += '  Handler: {} [{}]\n\n'.format(ipath, entry.itype)
      if options.showInfo and entry.doc:
        ret += '  '
        ret += normLines(self.formatdoc_rst(options, entry, options.width - 2), indent=2)
        ret += '\n\n'
      if options.showRest and entry.methods:
        ret += '  ### Supported Methods\n\n'
        for meth in entry.methods:
          ret += '  * **{}**:\n\n'.format(meth.method)
          if options.showInfo and meth.doc:
            ret += '    '
            ret += normLines(self.formatdoc_rst(options, meth, options.width - 4), indent=4)
            ret += '\n\n'
    if options.showLegend:
      ret += '# Legend\n\n'
      for item, desc in self.legend:
        ret += '  * `' + item + '`:\n\n    '
        ret += normLines(self.formattext_rst(options, desc, options.width - 4), indent=4)
        ret += '\n\n'
    if options.showGenerator:
      ret += '.. generator: pyramid-controllers'
      if options.showGenVersion:
        ret += '/{}'.format(getVersion())
      ret += ' [format=rst]\n'
    if options.showLocation:
      ret += '.. location: {}\n'.format(options.request.url)
    resp = Response(ret, content_type='text/plain')
    resp.charset = 'UTF-8'
    return resp

  #----------------------------------------------------------------------------
  def formattext_html(self, options, text):
    '''
    Formats the `text` for HTML output. The default implementation is
    *very* rudimentary (double newlines are replaced with paragraphs,
    and special characters are escaped)... sub-classes are highly
    encouraged to make this significantly more interesting!
    '''
    if not text:
      return ''
    text = normLines(text.strip()) \
        .replace('&', '&amp;') \
        .replace('<', '&lt;') \
        .replace('>', '&gt;') \
        .replace('\n\n', '</p>\n<p>')
    return '<p>' + text + '</p>'

  #----------------------------------------------------------------------------
  def formatdoc_html(self, options, entry):
    '''
    Formats the `entry`'s documentation as HTML and will be inserted
    *as-is* (i.e. special HTML characters such as ``&`` will not be
    escaped) into the definition list's <dd>...</dd> element after
    this entry's <dt> element.
    '''
    # TODO: i18n...
    ret = self.formattext_html(options, entry.doc) or ''
    if entry.params:
      ret += '<h4>Parameters</h4><dl class="params">'
      for param in entry.params:
        ret += u'<dt>{}</dt><dd><em>{}{}{}</em>{}</dd>'.format(
          cgi.escape(param.name or ''),
          cgi.escape(param.type or ''),
          ', optional' if param.optional else '',
          ( ', default ' + str(param.default) ) if param.default else '',
          ( '<br/>' + self.formattext_html(options, param.doc) ) if param.doc else '',
          )
      ret += '</dl>'
    if entry.returns:
      ret += '<h4>Returns</h4><dl class="returns">'
      for node in entry.returns:
        ret += u'<dt>{}</dt><dd>{}</dd>'.format(
          cgi.escape(node.type or ''),
          self.formattext_html(options, node.doc) if node.doc else '',
          )
      ret += '</dl>'
    if entry.raises:
      ret += '<h4>Raises</h4><dl class="raises">'
      for node in entry.raises:
        ret += u'<dt>{}</dt><dd>{}</dd>'.format(
          cgi.escape(node.type or ''),
          self.formattext_html(options, node.doc) if node.doc else '',
          )
      ret += '</dl>'
    if entry.methods:
      ret += '<h3>Supported Methods</h3><dl class="methods">'
      for meth in entry.methods:
        ret += u'<dt>{}</dt><dd>{}</dd>'.format(
          meth.method or meth.name or '',
          self.formatdoc_html(options, meth) or '',
          )
      ret += '</dl>'
    return ret

  #----------------------------------------------------------------------------
  def format_html(self, options, entries):
    '''
    Formats the DescribeController output for HTML output. Note that
    it is recommended that callers override this method and use a more
    powerful templating language (mako, jinja2, etc) to make the
    output attractive and useful.
    '''
    # todo: use an XSLT stylesheet transform from XML instead?...
    # TODO: i18n...
    ret = u'''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
 <head>
  <title>Contents of "{path}"</title>
  <meta http-equiv="content-type" content="text/html; charset=UTF-8"/>
  <meta name="generator" content="pyramid-controllers/{version}"/>
  <style type="text/css">
   dl{{margin-left: 2em;}}
   dt{{font-weight: bold;}}
   dd{{margin:0.5em 0 0.75em 2em;}}
  </style>
 </head>
 <body>
  <h1>Contents of "{path}"</h1>
  <dl class="endpoints">
'''.format(path=cgi.escape(self.path), version=getVersion())
    for entry in entries:
      if entry.isRest and entry.itype == 'method':
        continue
      ret += u'<dt>{}</dt><dd>{}</dd>'.format(
        cgi.escape(entry.dpath),
        self.formatdoc_html(options, entry) or '(Undocumented.)')
    ret += '</dl>'
    if options.showLegend:
      ret += '<h3>Legend</h3><dl>'
      for item, desc in self.legend:
        ret += u'<dt>{}</dt><dd>{}</dd>'.format(
          cgi.escape(item),
          self.formattext_html(options, desc) or '',
          )
      ret += '</dl>'
    ret += '''
 </body>
</html>
'''
    resp = Response(ret, content_type='text/html')
    resp.charset = 'UTF-8'
    return resp

  #----------------------------------------------------------------------------
  def _xentry(self, options, entry, xentry):
    if entry.params is not None:
      xpars = ET.SubElement(xentry, 'params')
      for param in entry.params:
        ET.SubElement(
          xpars, 'param',
          **{k: str(v) for k, v in
             pick(param, 'name', 'type', 'optional', 'default', 'doc').items()})
    if entry.returns is not None:
      xrets = ET.SubElement(xentry, 'returns')
      for ret in entry.returns:
        ET.SubElement(
          xrets, 'return',
          **{k: str(v) for k, v in pick(ret, 'type', 'doc').items()})
    if entry.raises is not None:
      xrzs = ET.SubElement(xentry, 'raises')
      for rz in entry.raises:
        x = ET.SubElement(
          xrzs, 'raise',
          **{k: str(v) for k, v in pick(rz, 'type', 'doc').items()})
    return xentry

  #----------------------------------------------------------------------------
  def _dentry(self, options, entry, dentry, dict=dict):
    if entry.params is not None:
      dentry['params'] = [
        dict(pick(e, 'name', 'type', 'optional', 'default', 'doc'))
        for e in entry.params]
    if entry.returns is not None:
      dentry['returns'] = [dict(pick(e, 'type', 'doc')) for e in entry.returns]
    if entry.raises is not None:
      dentry['raises'] = [dict(pick(e, 'type', 'doc')) for e in entry.raises]
    return dentry

  #----------------------------------------------------------------------------
  def format_et(self, options, entries):
    '''
    Returns the DescribeController output in an ElementTree structure.
    Since this method is used by the several other formatters,
    including HTML, JSON, WADL, YAML, and XML, it is recommended that
    callers override this method for generic impact, but must take
    care to not break the expected output structure. Alternatively,
    callers can override the :meth:`decorateEntry()` method and add
    extra attributes that the ET formatter is aware of -- as
    documented in the following example pseudo-structure::

      application:

        url: http://example.com/path

        endpoints:

          - endpoint:
              name: operation
              path: /path/to/operation
              decorated-name: operation
              decorated-path: /path/{to}/operation
              doc: some documentation about this endpoint

              methods:

                - method:

                    name: GET

                    # not currently provided by the default
                    # DescribeController.decorateEntry() implementation, but
                    # supported by the ET and other output renderers:

                    params:
                      - param:
                          name: size
                          type: int
                          optional: True
                          default: 1024
                          doc: the requested size

                    returns:
                      - return:
                          type: int
                          doc: the evaluated value

                    raises:
                      - raise:
                          type: TypeError
                          doc: when `size` is not an int

    '''

    root = ET.Element('application', url=options.request.host_url)
    xents = ET.SubElement(root, 'endpoints')
    for entry in entries:

      if entry.isRest and entry.itype == 'method':
        continue

      xent = ET.SubElement(xents, 'endpoint')
      xent.entry = entry
      xent.set('name', entry.name)
      xent.set('path', entry.path)
      xent.set('decorated-name', entry.dname)
      xent.set('decorated-path', entry.dpath)

      if entry.doc:
        ET.SubElement(xent, 'doc').text = entry.doc

      if entry.methods:
        for meth in entry.methods:
          xmeth = ET.SubElement(xent, 'method', name=meth.method)
          if meth.doc:
            ET.SubElement(xmeth, 'doc').text = meth.doc
          xmeth.entry = meth
          self._xentry(options, meth, xmeth)
      else:
        xmeth = ET.SubElement(xent, 'method', name='GET')
        xmeth.entry = entry
        self._xentry(options, entry, xmeth)

    return root

  #----------------------------------------------------------------------------
  def format_xml(self, options, entries):
    '''
    Formats the DescribeController ET output in XML.
    '''
    root = self.format_et(options, entries)
    resp = Response(ET.tostring(root, 'UTF-8'), content_type='text/xml')
    resp.charset = 'UTF-8'
    return resp

  #----------------------------------------------------------------------------
  def et2wadl(self, options, root):
    for ns, uri in self.xmlns.items():
      if ns == 'wadl':
        root.set('xmlns', uri)
      else:
        root.set('xmlns:' + ns, uri)
    root.set('xsi:schemaLocation', self.xmlns['wadl'] + ' wadl.xsd')
    rename = {
      'doc':       'doc:doc',
      'endpoints': 'resources',
      'endpoint':  'resource',
      'params':    'request',
      'returns':   'response',
      'return':    'representation',
      'raise':     'fault',
      }
    appUrl = None
    for elem in root.iter():
      if elem.tag in rename:
        elem.tag = rename[elem.tag]
      if elem.tag == 'application' and 'url' in elem.attrib:
        appUrl = elem.attrib.pop('url')
      if elem.tag == 'resources' and appUrl:
        elem.set('base', appUrl)
      elem.attrib.pop('decorated-name', None)
      elem.attrib.pop('decorated-path', None)
      if 'path' in elem.attrib and elem.attrib.get('path').startswith('/'):
        elem.attrib['path'] = elem.attrib.get('path')[1:]
      if elem.tag == 'resource':
        elem.attrib.pop('name', None)
      if elem.tag == 'method':
        faults = []
        for child in elem:
          if child.tag == 'raises':
            faults.extend(child.findall('fault'))
            faults.extend(child.findall('raise'))
            elem.remove(child)
        if faults:
          response = elem.find('response')
          if response is None:
            response = elem.find('returns')
          if response is None:
            response = ET.SubElement(elem, 'response')
          response.extend(faults)
      if elem.tag == 'representation':
        if 'type' in elem.attrib:
          val = elem.attrib.pop('type')
          elem.attrib['element'] = self.wadlTypeRemap.get(val, val)
        if 'doc' in elem.attrib:
          doc = elem.attrib.pop('doc')
          ET.SubElement(elem, 'doc:doc').text = doc
      if elem.tag == 'param':
        if 'optional' in elem.attrib:
          opt = asbool(elem.attrib.pop('optional'))
          elem.attrib['required'] = 'true' if not opt else 'false'
        if 'type' in elem.attrib:
          val = elem.attrib['type']
          if val in self.wadlTypeRemap:
            elem.attrib['type'] = self.wadlTypeRemap[val]
        if 'doc' in elem.attrib:
          doc = elem.attrib.pop('doc')
          ET.SubElement(elem, 'doc:doc').text = doc
      if elem.tag == 'fault':
        doc = elem.attrib.pop('doc', None)
        if doc:
          ET.SubElement(elem, 'doc:doc').text = doc
        if 'type' in elem.attrib:
          val = elem.attrib.pop('type')
          elem.attrib['element'] = self.wadlTypeRemap.get(val, val)
    return root

  #----------------------------------------------------------------------------
  def format_wadl(self, options, entries):
    '''
    Formats the DescribeController ET output in WADL. Note that it is
    recommended that callers override this method and use internal
    knowledge to render a more explicit WADL descriptor definition.
    '''
    # todo: use an XSLT stylesheet transform from XML instead?...
    root = self.et2wadl(options, self.format_et(options, entries))
    resp = Response(ET.tostring(root, 'UTF-8'), content_type='text/xml')
    resp.charset = 'UTF-8'
    return resp

  #----------------------------------------------------------------------------
  def format_struct(self, options, entries, dict=dict, includeEntry=False):
    '''
    Similar to :meth:`format_et()`, except that the return value is a
    dict structure instead of an ElementTree. See :meth:`format_et()`
    for details.
    '''
    root = dict(application=dict(url=options.request.host_url))
    app = root['application']
    app['endpoints'] = []
    for entry in entries:
      if entry.isRest and entry.itype == 'method':
        continue
      endpoint = dict(
        name          = entry.name,
        path          = entry.path,
        decoratedName = entry.dname,
        decoratedPath = entry.dpath,
        )
      if includeEntry:
        endpoint['entry'] = entry
      if entry.doc:
        endpoint['doc'] = entry.doc
      if entry.methods:
        endpoint['methods'] = []
        for meth in entry.methods:
          dmeth = dict(name=meth.method)
          if meth.doc:
            dmeth['doc'] = meth.doc
          if includeEntry:
            dmeth['entry'] = meth
          endpoint['methods'].append(self._dentry(options, meth, dmeth, dict=dict))
      app['endpoints'].append(endpoint)
    return root

  #----------------------------------------------------------------------------
  def format_json(self, options, entries):
    '''
    Formats the DescribeController ET output in JSON.
    '''
    resp = Response(json.dumps(self.format_struct(options, entries)),
                    content_type='application/json')
    resp.charset = 'UTF-8'
    return resp

  #----------------------------------------------------------------------------
  def format_yaml(self, options, entries):
    '''
    Formats the DescribeController ET output in YAML.
    '''
    import yaml
    resp = Response(yaml.dump(self.format_struct(options, entries)),
                    content_type='application/yaml')
    resp.charset = 'UTF-8'
    return resp

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
