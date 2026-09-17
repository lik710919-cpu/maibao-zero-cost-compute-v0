import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compute_chunk import partition_range, sum_squares_formula


class ComputeTests(unittest.TestCase):
    def test_partition_exact_coverage(self):
        ranges = [partition_range(10, 4, i) for i in range(4)]
        self.assertEqual(ranges, [(1, 3), (4, 6), (7, 8), (9, 10)])
        flattened = [value for start, end in ranges for value in range(start, end + 1)]
        self.assertEqual(flattened, list(range(1, 11)))

    def test_formula_known_values(self):
        self.assertEqual(sum_squares_formula(1, 10), 385)
        self.assertEqual(sum_squares_formula(4, 6), 77)

    def test_invalid_partition_rejected(self):
        with self.assertRaises(ValueError):
            partition_range(3, 4, 0)
        with self.assertRaises(ValueError):
            partition_range(10, 4, 4)


if __name__ == "__main__":
    unittest.main()
