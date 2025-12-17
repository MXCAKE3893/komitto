import pytest
from komitto.config import load_config

def test_load_config_defaults():
    """Verify that load_config returns default values when no config files exist."""
    # We can rely on the fact that no komitto.toml exists in the temp dir ideally, 
    # but in a real environment it might pick up user config. 
    # We verify it returns at least the 'prompt' key.
    config = load_config()
    assert isinstance(config, dict)
    assert "prompt" in config
    assert "system" in config["prompt"]
