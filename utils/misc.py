import functools
from types import FunctionType, LambdaType
try:
    from sklearn.utils import is_scalar_nan
except ImportError:
    def is_scalar_nan(x):
        import numbers
        import numpy as np
        return bool(isinstance(x, (numbers.Real, np.floating)) and np.isnan(x))


def maybe_mkdir(path, warn=False):
    """ Create directory when it didn't exist."""
    import os
    import warnings

    try:
        os.makedirs(path)
    except FileExistsError as e:
        if warn:
            warnings.warn(e)


def print_source_code(obj):
    """ Print the source code of an object."""
    import inspect
    print(inspect.getsource(obj))


def check_same_length(f):
    """ A decorator that checks all the arguments to be the same length"""
    f_name = f.__name__
    @functools.wraps(f)
    def wrapped(*args):
        assert all(hasattr(i, '__len__') for i in args), 'Not all the arguments has attribute __len__'

        lens = [len(i) for i in args]
        if len(set(lens)) > 1:
            raise ValueError('{} expecting all the arguments to have same length.'.format(f_name))
        return f(*args)
    return wrapped


def ngram(iterable, n=2):
    """ Generating n-gram from iterable."""
    length = len(iterable)
    return [iterable[i:i+n] for i in range(length-n+1)]


def set_default(criteria=None, default_value=None):
    """ A decorator that checks the first argument, if meets the criteria then replace it with default_value
        The criteria can be a list of values or a callable that returns boolean. Default is [None]
    """
    criteria = criteria or [None]
    if isinstance(criteria, (list, tuple)):
        check_f = lambda x: x in criteria
    elif callable(criteria):
        check_f = criteria
    else:
        raise ValueError('The criteria should either be a list or a callable.')

    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            args = list(args)
            if check_f(args[0]):
                args[0] = default_value
            return f(*args, **kwargs)
        return wrapped
    return decorator


def return_default(criteria=None, default_value=None):
    """ A decorator that checks the first argument, if meets the criteria then simply return the default_value
        The criteria can be a list of values or a callable that returns boolean. Default is [None]
    """
    criteria = criteria or [None]
    if isinstance(criteria, (list, tuple)):
        check_f = lambda x: x in criteria
    elif callable(criteria):
        check_f = criteria
    else:
        raise ValueError('The criteria should either be a list or a callable.')

    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if check_f(args[0]):
                return default_value
            return f(*args, **kwargs)
        return wrapped
    return decorator


na_return_default = functools.partial(return_default, criteria=is_scalar_nan)
na_set_default = functools.partial(set_default, criteria=is_scalar_nan)

