import unittest
from komitto.config import resolve_config

class TestConfigResolution(unittest.TestCase):
    def test_independent_resolution(self):
        """Verify that resolving config does not mutate the original config or entangle results."""
        base_config = {
            "prompt": {
                "system": "Default"
            },
            "contexts": {
                "ctx1": {"template": "t1"},
                "ctx2": {"template": "t2"}
            },
            "templates": {
                "t1": {"system": "System 1"},
                "t2": {"system": "System 2"}
            }
        }

        # Resolve context 1
        config1 = resolve_config(base_config, context_name="ctx1")
        self.assertEqual(config1["prompt"]["system"], "System 1")
        self.assertEqual(base_config["prompt"]["system"], "Default", "Base config should not be mutated")

        # Resolve context 2
        config2 = resolve_config(base_config, context_name="ctx2")
        self.assertEqual(config2["prompt"]["system"], "System 2")
        self.assertEqual(config1["prompt"]["system"], "System 1", "Config 1 should not be affected by Config 2 resolution")
        self.assertEqual(base_config["prompt"]["system"], "Default")

if __name__ == '__main__':
    unittest.main()
