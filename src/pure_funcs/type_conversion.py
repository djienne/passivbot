"""
Type conversion utilities for converting between numpy and Python native types.
"""
from collections import OrderedDict

import numpy as np


def numpyize(x):
    """Recursively convert lists/tuples to numpy arrays."""
    if isinstance(x, (list, tuple)):
        return np.array([numpyize(e) for e in x])
    elif isinstance(x, dict):
        numpyd = {}
        for k, v in x.items():
            numpyd[k] = numpyize(v)
        return numpyd
    else:
        return x


def denumpyize(x):
    """Recursively convert numpy types to Python native types."""
    if isinstance(x, (np.float64, np.float32, np.float16)):
        return float(x)
    elif isinstance(x, (np.int64, np.int32, np.int16, np.int8)):
        return int(x)
    elif isinstance(x, np.ndarray):
        return [denumpyize(e) for e in x]
    elif isinstance(x, np.bool_):
        return bool(x)
    elif isinstance(x, (dict, OrderedDict)):
        denumpyd = {}
        for k, v in x.items():
            denumpyd[k] = denumpyize(v)
        return denumpyd
    elif isinstance(x, list):
        return [denumpyize(z) for z in x]
    elif isinstance(x, tuple):
        return tuple([denumpyize(z) for z in x])
    else:
        return x


def denanify(x, nan=0.0, posinf=0.0, neginf=0.0):
    """Replace NaN, positive infinity, and negative infinity values."""
    try:
        assert not isinstance(x, str)
        _ = float(x)
        return np.nan_to_num(x, nan=nan, posinf=posinf, neginf=neginf)
    except (AssertionError, TypeError, ValueError):
        if isinstance(x, list):
            return [denanify(e) for e in x]
        elif isinstance(x, tuple):
            return tuple(denanify(e) for e in x)
        elif isinstance(x, np.ndarray):
            return np.array([denanify(e) for e in x], dtype=x.dtype)
        elif isinstance(x, dict):
            denanified = {}
            for k, v in x.items():
                denanified[k] = denanify(v)
            return denanified
        else:
            return x
