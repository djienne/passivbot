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


def compare_dicts(dict1, dict2, path=""):
    """Print differences between two nested dictionaries."""
    for key in sorted(set(dict1.keys()) | set(dict2.keys())):
        if key not in dict1:
            print(f"{path}{key}: Missing in first dict. Value in second dict: {dict2[key]}")
        elif key not in dict2:
            print(f"{path}{key}: Missing in second dict. Value in first dict: {dict1[key]}")
        elif isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
            compare_dicts(dict1[key], dict2[key], f"{path}{key}.")
        elif dict1[key] != dict2[key]:
            print(f"{path}{key}: Values differ. First dict:  {dict1[key]} Second dict: {dict2[key]}")


def compare_dict_keys(dict1, dict2):
    """Check if two dictionaries have the same key structure (including nested keys)."""
    def get_all_keys(d):
        keys = set(d.keys())
        for value in d.values():
            if isinstance(value, dict):
                keys.update(get_all_keys(value))
        return keys

    return get_all_keys(dict1) == get_all_keys(dict2)


def check_keys(dict0, dict1):
    """Check if dict0's key structure is a subset of dict1's."""
    def check_nested(d0, d1):
        for key, value in d0.items():
            if key not in d1:
                return False
            if isinstance(value, dict):
                if not isinstance(d1[key], dict):
                    return False
                if not check_nested(value, d1[key]):
                    return False
        return True

    return check_nested(dict0, dict1)
