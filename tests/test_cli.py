import pytest
from komitto.main import main
import argparse

def test_main_import():
    """Verify that main can be imported."""
    assert callable(main)
