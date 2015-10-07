=========
ChangeLog
=========


v0.3.24
=======

* Removed `distribute` dependency


v0.3.23
=======

* Added dispatcher parameter `raiseType` and deprecated `raiseErrors`
* Changed meaning of ``raiseErrors=True`` to raise on 4xx and 5xx
  *only* (by aliasing to ``raiseType=HTTPError``)
* Added workaround for issue #2 (RestController renders prematurely)


v0.3.22
=======

* Added support for generic request wrapping via @wrap
* Added 404 response if extra, non-existent, path components are requested


v0.3.21
=======

* Added support for unicode path components


v0.3.20
=======

* First tagged release
* Added Dispatcher `raiseErrors` parameter
