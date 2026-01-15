"""
Cache I/O utilities for numpy arrays with gzip compression support.

This module provides common patterns for loading and saving numpy arrays
to cache files with optional gzip compression.
"""
import gzip
import os
from pathlib import Path
from typing import Optional, Union

import numpy as np


def load_numpy_array(
    filepath: Union[str, Path],
    compressed: Optional[bool] = None,
) -> np.ndarray:
    """
    Load a numpy array from file with optional gzip decompression.

    Args:
        filepath: Path to the .npy or .npy.gz file
        compressed: If True, use gzip decompression. If False, load directly.
                   If None, auto-detect based on .gz extension.

    Returns:
        The loaded numpy array

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    filepath = Path(filepath)

    if compressed is None:
        compressed = filepath.suffix == ".gz"

    if compressed:
        with gzip.open(filepath, "rb") as f:
            return np.load(f)
    else:
        return np.load(filepath)


def save_numpy_array(
    filepath: Union[str, Path],
    array: np.ndarray,
    compressed: bool = False,
    compresslevel: int = 1,
) -> int:
    """
    Save a numpy array to file with optional gzip compression.

    Args:
        filepath: Path to save the file (will add .gz if compressed and not present)
        array: The numpy array to save
        compressed: If True, use gzip compression
        compresslevel: Compression level (1-9), only used if compressed=True

    Returns:
        Size of the saved file in bytes
    """
    filepath = Path(filepath)

    if compressed:
        with gzip.open(filepath, "wb", compresslevel=compresslevel) as f:
            np.save(f, array)
    else:
        np.save(filepath, array)

    return filepath.stat().st_size


def load_numpy_array_safe(
    filepath: Union[str, Path],
    compressed: Optional[bool] = None,
    default: Optional[np.ndarray] = None,
) -> Optional[np.ndarray]:
    """
    Load a numpy array from file, returning default on failure.

    Args:
        filepath: Path to the .npy or .npy.gz file
        compressed: If True, use gzip decompression. If None, auto-detect.
        default: Value to return if loading fails

    Returns:
        The loaded numpy array, or default if loading fails
    """
    filepath = Path(filepath)

    if not filepath.exists():
        return default

    try:
        return load_numpy_array(filepath, compressed=compressed)
    except Exception:
        return default


def get_cache_filepath(
    cache_dir: Union[str, Path],
    name: str,
    compressed: bool = False,
) -> Path:
    """
    Get the full filepath for a cached numpy array.

    Args:
        cache_dir: Directory containing cache files
        name: Base name of the file (without extension)
        compressed: If True, append .npy.gz, else .npy

    Returns:
        Full path to the cache file
    """
    cache_dir = Path(cache_dir)
    ext = ".npy.gz" if compressed else ".npy"
    return cache_dir / f"{name}{ext}"


def cache_exists(
    cache_dir: Union[str, Path],
    name: str,
    compressed: bool = False,
) -> bool:
    """
    Check if a cache file exists.

    Args:
        cache_dir: Directory containing cache files
        name: Base name of the file (without extension)
        compressed: If True, check for .npy.gz, else .npy

    Returns:
        True if the cache file exists
    """
    return get_cache_filepath(cache_dir, name, compressed).exists()
