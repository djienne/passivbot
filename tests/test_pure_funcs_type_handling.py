"""
Regression tests for pure_funcs type handling functions.

These tests capture the exact behavior of functions that use type checking,
ensuring that refactoring from `type(x) ==` to `isinstance(x, ...)` does not
change behavior.
"""
import pytest
import numpy as np
from collections import OrderedDict

from pure_funcs import (
    numpyize,
    denumpyize,
    denanify,
    flatten_dict,
    nullify,
    tuplify,
    round_values,
)


class TestNumpyize:
    """Regression tests for numpyize function."""

    def test_list_conversion(self):
        result = numpyize([1, 2, 3])
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, np.array([1, 2, 3]))

    def test_tuple_conversion(self):
        result = numpyize((1, 2, 3))
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, np.array([1, 2, 3]))

    def test_nested_list(self):
        result = numpyize([[1, 2], [3, 4]])
        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 2)

    def test_dict_with_lists(self):
        result = numpyize({"a": [1, 2], "b": [3, 4]})
        assert isinstance(result, dict)
        np.testing.assert_array_equal(result["a"], np.array([1, 2]))
        np.testing.assert_array_equal(result["b"], np.array([3, 4]))

    def test_scalar_passthrough(self):
        assert numpyize(42) == 42
        assert numpyize(3.14) == 3.14
        assert numpyize("string") == "string"

    def test_empty_list(self):
        result = numpyize([])
        assert isinstance(result, np.ndarray)
        assert len(result) == 0

    def test_nested_dict_with_lists(self):
        result = numpyize({"outer": {"inner": [1, 2, 3]}})
        assert isinstance(result, dict)
        assert isinstance(result["outer"], dict)
        np.testing.assert_array_equal(result["outer"]["inner"], np.array([1, 2, 3]))


class TestDenumpyize:
    """Regression tests for denumpyize function."""

    def test_numpy_float64(self):
        result = denumpyize(np.float64(3.14))
        assert isinstance(result, float)
        assert result == pytest.approx(3.14)

    def test_numpy_float32(self):
        result = denumpyize(np.float32(3.14))
        assert isinstance(result, float)

    def test_numpy_int64(self):
        result = denumpyize(np.int64(42))
        assert isinstance(result, int)
        assert result == 42

    def test_numpy_int32(self):
        result = denumpyize(np.int32(42))
        assert isinstance(result, int)
        assert result == 42

    def test_numpy_array(self):
        result = denumpyize(np.array([1.0, 2.0, 3.0]))
        assert isinstance(result, list)
        assert result == [1.0, 2.0, 3.0]

    def test_numpy_bool(self):
        result = denumpyize(np.bool_(True))
        assert isinstance(result, bool)
        assert result is True

    def test_numpy_bool_false(self):
        result = denumpyize(np.bool_(False))
        assert isinstance(result, bool)
        assert result is False

    def test_dict_with_numpy_values(self):
        result = denumpyize({"a": np.float64(1.5), "b": np.int32(10)})
        assert isinstance(result, dict)
        assert isinstance(result["a"], float)
        assert isinstance(result["b"], int)

    def test_ordered_dict(self):
        result = denumpyize(OrderedDict([("a", np.float64(1.0))]))
        assert isinstance(result, dict)
        assert isinstance(result["a"], float)

    def test_list_passthrough(self):
        result = denumpyize([1, 2, 3])
        assert result == [1, 2, 3]

    def test_tuple_preserved(self):
        result = denumpyize((1, 2, 3))
        assert isinstance(result, tuple)
        assert result == (1, 2, 3)

    def test_nested_numpy_array(self):
        result = denumpyize(np.array([[1, 2], [3, 4]]))
        assert isinstance(result, list)
        assert isinstance(result[0], list)

    def test_string_passthrough(self):
        result = denumpyize("hello")
        assert result == "hello"


class TestDenanify:
    """Regression tests for denanify function."""

    def test_nan_replacement(self):
        result = denanify(np.nan)
        assert result == 0.0

    def test_inf_replacement(self):
        result = denanify(np.inf)
        assert result == 0.0

    def test_neginf_replacement(self):
        result = denanify(-np.inf)
        assert result == 0.0

    def test_list_with_nan(self):
        result = denanify([1.0, np.nan, 3.0])
        assert result == [1.0, 0.0, 3.0]

    def test_tuple_with_nan(self):
        result = denanify((1.0, np.nan))
        assert isinstance(result, tuple)
        assert result == (1.0, 0.0)

    def test_dict_with_nan(self):
        result = denanify({"a": np.nan, "b": 1.0})
        assert result == {"a": 0.0, "b": 1.0}

    def test_numpy_array_with_nan(self):
        result = denanify(np.array([1.0, np.nan, 3.0]))
        np.testing.assert_array_equal(result, np.array([1.0, 0.0, 3.0]))

    def test_custom_nan_value(self):
        result = denanify(np.nan, nan=-1.0)
        assert result == -1.0

    def test_custom_posinf_value(self):
        result = denanify(np.inf, posinf=999.0)
        assert result == 999.0

    def test_custom_neginf_value(self):
        result = denanify(-np.inf, neginf=-999.0)
        assert result == -999.0

    def test_string_passthrough(self):
        result = denanify("hello")
        assert result == "hello"

    def test_normal_float_passthrough(self):
        result = denanify(3.14)
        assert result == pytest.approx(3.14)


class TestFlattenDict:
    """Regression tests for flatten_dict function."""

    def test_simple_flatten(self):
        result = flatten_dict({"a": {"b": 1, "c": 2}})
        assert result == {"a_b": 1, "a_c": 2}

    def test_no_nesting(self):
        result = flatten_dict({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_deep_nesting(self):
        result = flatten_dict({"a": {"b": {"c": 1}}})
        assert result == {"a_b_c": 1}

    def test_custom_separator(self):
        result = flatten_dict({"a": {"b": 1}}, sep=".")
        assert result == {"a.b": 1}

    def test_mixed_nesting(self):
        result = flatten_dict({"a": {"b": 1}, "c": 2})
        assert result == {"a_b": 1, "c": 2}

    def test_empty_dict(self):
        result = flatten_dict({})
        assert result == {}


class TestNullify:
    """Regression tests for nullify function."""

    def test_number_to_zero(self):
        assert nullify(42) == 0.0
        assert nullify(3.14) == 0.0

    def test_list_nullification(self):
        result = nullify([1, 2, 3])
        assert result == [0.0, 0.0, 0.0]

    def test_tuple_nullification(self):
        result = nullify((1, 2))
        # Note: returns list, not tuple
        assert result == [0.0, 0.0]

    def test_dict_nullification(self):
        result = nullify({"a": 1, "b": 2})
        assert result == {"a": 0.0, "b": 0.0}

    def test_bool_preserved_true(self):
        assert nullify(True) is True

    def test_bool_preserved_false(self):
        assert nullify(False) is False

    def test_numpy_bool_preserved(self):
        assert nullify(np.bool_(True)) is np.bool_(True)
        assert nullify(np.bool_(False)) is np.bool_(False)

    def test_numpy_array(self):
        result = nullify(np.array([1, 2, 3]))
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, np.array([0.0, 0.0, 0.0]))

    def test_nested_dict(self):
        result = nullify({"a": {"b": 1}})
        assert result == {"a": {"b": 0.0}}


class TestTuplify:
    """Regression tests for tuplify function."""

    def test_list_to_tuple(self):
        result = tuplify([1, 2, 3])
        assert result == (1, 2, 3)

    def test_nested_list(self):
        result = tuplify([[1, 2], [3, 4]])
        assert result == ((1, 2), (3, 4))

    def test_dict_to_tuple(self):
        result = tuplify({"a": 1, "b": 2})
        assert isinstance(result, tuple)
        # Dict items are converted to tuple of (key, value) pairs
        assert set(result) == {("a", 1), ("b", 2)}

    def test_ordered_dict_to_tuple(self):
        result = tuplify(OrderedDict([("a", 1), ("b", 2)]))
        assert isinstance(result, tuple)

    def test_sorted_option(self):
        result = tuplify([3, 1, 2], sort=True)
        assert result == (1, 2, 3)

    def test_scalar_passthrough(self):
        assert tuplify(42) == 42
        assert tuplify("hello") == "hello"

    def test_empty_list(self):
        result = tuplify([])
        assert result == ()


class TestRoundValues:
    """Regression tests for round_values function."""

    def test_float_rounding(self):
        result = round_values(3.14159, 3)
        # Uses pbr.round_dynamic, verify it runs without error
        assert isinstance(result, float)

    def test_numpy_float64_rounding(self):
        result = round_values(np.float64(3.14159), 3)
        assert isinstance(result, float)

    def test_dict_rounding(self):
        result = round_values({"a": 3.14159, "b": 2.71828}, 2)
        assert isinstance(result, dict)
        assert "a" in result
        assert "b" in result

    def test_list_rounding(self):
        result = round_values([3.14159, 2.71828], 2)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_numpy_array_rounding(self):
        result = round_values(np.array([3.14159, 2.71828]), 2)
        assert isinstance(result, np.ndarray)

    def test_tuple_rounding(self):
        result = round_values((3.14159, 2.71828), 2)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_ordered_dict_rounding(self):
        result = round_values(OrderedDict([("a", 3.14159)]), 2)
        assert isinstance(result, OrderedDict)

    def test_int_passthrough(self):
        result = round_values(42, 2)
        assert result == 42

    def test_string_passthrough(self):
        result = round_values("hello", 2)
        assert result == "hello"
