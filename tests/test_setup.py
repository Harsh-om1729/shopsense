"""Smoke tests for the Phase 0 environment."""

import importlib

import numpy as np
import pytest

from src import config


@pytest.mark.parametrize("module", ["numpy", "pandas", "sklearn", "matplotlib"])
def test_core_libraries_import(module):
    importlib.import_module(module)


@pytest.mark.parametrize(
    "path",
    [
        config.DATA_RAW_DIR,
        config.DATA_PROCESSED_DIR,
        config.MODELS_DIR,
        config.REPORTS_DIR,
    ],
)
def test_project_directories_exist(path):
    assert path.is_dir()


def test_random_seed_is_reproducible():
    first = np.random.default_rng(config.RANDOM_SEED).random(5)
    second = np.random.default_rng(config.RANDOM_SEED).random(5)
    assert np.array_equal(first, second)
