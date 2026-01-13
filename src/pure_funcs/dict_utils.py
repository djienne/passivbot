"""
Dictionary utilities for manipulation and transformation.
"""


def flatten_dict(d, parent_key="", sep="_"):
    """Flatten a nested dictionary into a single-level dictionary."""
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def sort_dict_keys(d):
    """Recursively sort dictionary keys."""
    if isinstance(d, list):
        return [sort_dict_keys(e) for e in d]
    if not isinstance(d, dict):
        return d
    return {key: sort_dict_keys(d[key]) for key in sorted(d)}


def remove_OD(d: dict) -> dict:
    """Recursively convert OrderedDicts to regular dicts."""
    if isinstance(d, dict):
        return {k: remove_OD(v) for k, v in d.items()}
    if isinstance(d, list):
        return [remove_OD(x) for x in d]
    return d


def dict_keysort(d: dict):
    """Sort dictionary items by value."""
    return sorted(d.items(), key=lambda x: x[1])


def extract_and_sort_by_keys_recursive(nested_dict):
    """
    Extracts values from a nested dictionary of arbitrary depth, sorted by their keys.

    Args:
    nested_dict (dict): A dictionary where each value may be another dictionary.

    Returns:
    list: A list of values, where each value is a list of values from inner dictionaries sorted by their keys.
    """
    if not isinstance(nested_dict, dict):
        return nested_dict

    sorted_values = []
    for key in sorted(nested_dict.keys()):
        value = nested_dict[key]
        sorted_values.append(extract_and_sort_by_keys_recursive(value))

    return sorted_values
