import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RepairChunkTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("repair_chunk")
        self.assertIsNotNone(spec, "repair_chunk module must exist")
        if spec is None:
            return None
        return importlib.import_module("repair_chunk")

    def test_rejects_same_provider_repair(self):
        module = self._module()
        if module is None:
            return
        with self.assertRaises(RuntimeError):
            module.execute_repair(
                original_provider_id="github-actions-public",
                provider_id="github-actions-public",
                executor=lambda: {"provider_id": "github-actions-public"},
            )

    def test_rejects_returned_provider_identity_mismatch(self):
        module = self._module()
        if module is None:
            return
        with self.assertRaises(RuntimeError):
            module.execute_repair(
                original_provider_id="github-actions-public",
                provider_id="wandbox-public",
                executor=lambda: {"provider_id": "github-actions-public"},
            )

    def test_marks_valid_cross_provider_result_as_repair(self):
        module = self._module()
        if module is None:
            return
        raw = {
            "provider_id": "wandbox-public",
            "attempt": "primary",
            "chunk_index": 4,
            "local_compute_used": False,
        }
        result = module.execute_repair(
            original_provider_id="github-actions-public",
            provider_id="wandbox-public",
            executor=lambda: raw,
        )
        self.assertEqual(result["attempt"], "repair")
        self.assertEqual(result["provider_id"], "wandbox-public")
        self.assertEqual(result["scheduled_provider_id"], "wandbox-public")
        self.assertEqual(result["original_provider_id"], "github-actions-public")
        self.assertFalse(result["local_compute_used"])


if __name__ == "__main__":
    unittest.main()
