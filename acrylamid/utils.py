# -*- encoding: utf-8 -*-
#
# Copyright 2012 Martin Zimmermann <info@posativ.org>. All rights reserved.
# License: BSD Style, 2 clauses -- see LICENSE.
#
# Utilities that do not depend on any further Acrylamid object

from __future__ import unicode_literals

import sys
import os
import io
import zlib
import locale
import functools
import itertools

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

try:
    import magic
except ImportError as e:
    if e.args[0].find('libmagic') > -1:
        raise
    magic = None

from acrylamid.compat import PY2K, string_types, map, filter, iteritems


def hash(*objs, **kw):

    # start with 0?
    rv = kw.get('start', 0)

    for obj in objs:
        if isinstance(obj, string_types):
            rv = zlib.crc32(obj.encode('utf-8'), rv)
        else:
            if isinstance(obj, tuple):
                hv = hash(*obj, start=rv)
            else:
                hv = obj.__hash__()

            rv = zlib.crc32(repr(hv).encode('utf-8'), rv)

    return rv & 0xffffffff


def rchop(original_string, substring):
    """Return the given string after chopping of a substring from the end.

    :param original_string: the original string
    :param substring: the substring to chop from the end
    """
    if original_string.endswith(substring):
        return original_string[:-len(substring)]
    return original_string


def lchop(string, prefix):
    """Return the given string after chopping the prefix from the begin.

    :param string: the original string
    :oaram prefix: prefix to chop of
    """

    if string.startswith(prefix):
        return string[len(prefix):]
    return string


if sys.version_info[0] == 2:
    def force_unicode(string):  # This function can be removed with Python 3

        if isinstance(string, unicode):
            return string

        try:
            return string.decode('utf-8')
        except UnicodeDecodeError:
            return string.decode(locale.getpreferredencoding())
else:
    force_unicode = lambda x: x


def total_seconds(td):  # timedelta.total_seconds, required for 2.6
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


class cached_property(object):
    """A property that is only computed once per instance and then replaces
    itself with an ordinary attribute. Deleting the attribute resets the
    property.

    Copyright (c) 2012, Marcel Hellkamp. License: MIT."""

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        if obj is None: return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


class classproperty(property):
    # via http://stackoverflow.com/a/1383402
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


class memoized(object):
    """Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated)."""

    def __init__(self, func):
        self.func = func
        self.cache = {}
        self.__doc__ = func.__doc__

    def __call__(self, *args):
        try:
            return self.cache[args]
        except KeyError:
            value = self.func(*args)
            self.cache[args] = value
            return value
        except TypeError:
            # uncachable -- for instance, passing a list as an argument.
            # Better to not cache than to blow up entirely.
            return self.func(*args)

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)


def find(fname, directory):
    """Find `fname` in `directory`, if not found try the parent folder until
    we find `fname` (as full path) or raise an :class:`IOError`."""

    directory = directory.rstrip('/')

    while directory:
        try:
            return os.path.join(directory, next(filter(
                lambda p: p == fname, os.listdir(directory))))
        except (OSError, StopIteration):
            directory = directory.rsplit('/', 1)[0]
    else:
        raise IOError


def execfile(path, ns):
    """Python 2 and 3 compatible way to execute a file into a namespace."""
    with io.open(path, 'rb') as fp:
        exec(fp.read(), ns)


def batch(iterable, count):
    """batch a list to N items per slice"""
    result = []
    for item in iterable:
        if len(result) == count:
            yield result
            result = []
        result.append(item)
    if result:
        yield result


def groupby(iterable, keyfunc=lambda x: x):
    """:func:`itertools.groupby` wrapper for :func:`neighborhood`."""
    for k, g in itertools.groupby(iterable, keyfunc):
        yield k, list(g)


def neighborhood(iterable, prev=None):
    """yield previous and next values while iterating"""
    iterator = iter(iterable)
    item = next(iterator)
    for new in iterator:
        yield (prev, item, new)
        prev, item = item, new
    yield (prev, item, None)


class Metadata(dict):
    """A nested :class:`dict` used for post metadata."""

    def __init__(self, dikt={}):
        super(Metadata, self).__init__(self)
        self.update(dict(dikt))


    def __setitem__(self, key, value):
        try:
            key, other = key.split('.', 1)
            self.setdefault(key, Metadata())[other] = value
        except ValueError:
            super(Metadata, self).__setitem__(key, value)

    def __getattr__(self, attr):
        return self[attr]

    def update(self, dikt):
        for key, value in iteritems(dikt):
            self[key] = value

    def redirect(self, old, new):

        self[new] = self[old]
        del self[old]


def import_object(name):
    if '.' not in name:
        return __import__(name)

    parts = name.split('.')
    obj = __import__('.'.join(parts[:-1]), None, None, [parts[-1]], 0)
    return getattr(obj, parts[-1])


class Struct(OrderedDict):
    """A dictionary that provides attribute-style access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super(Struct, self).__setattr__(key, value)
        else:
            self[key] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(name)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash(*itertools.chain(self.keys(), self.values()))


class HashableList(list):

    def __hash__(self):
        return hash(*self)
