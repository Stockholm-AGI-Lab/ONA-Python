import unittest
from ona import truth_deduction, truth_w2c, truth_induction, truth_intersection

class TestONAFunctions(unittest.TestCase):

    def test_truth_deduction(self):
        self.assertEqual(truth_deduction((1, 0.5), (2, 0.8)), (4, 1.6))
        self.assertEqual(truth_deduction((2, 0.3), (3, 0.7)), (9, 1.89))
        self.assertEqual(truth_deduction((0, 1.0), (4, 0.6)), (16, 9.6))

    def test_truth_w2c(self):
        self.assertEqual(truth_w2c(2), 2 / (2 + 1.0))
        self.assertEqual(truth_w2c(5), 5 / (5 + 1.0))
        self.assertEqual(truth_w2c(0), 0 / (0 + 1.0))

    # def test_truth_induction(self):
    #     self.assertEqual(truth_induction((1, 0.5), (2, 0.8)), (2, truth_w2c(1 * 0.5 * 0.8)))
    #     self.assertEqual(truth_induction((2, 0.3), (3, 0.7)), (3, truth_w2c(2 * 0.3 * 0.7)))
    #     self.assertEqual(truth_induction((0, 1.0), (4, 0.6)), (4, truth_w2c(0 * 1.0 * 0.6)))

    def test_truth_intersection(self):
        self.assertEqual(truth_intersection((1, 0.5), (2, 0.8)), (2, 0.4))
        self.assertEqual(truth_intersection((2, 0.3), (3, 0.7)), (6, 0.21))
        self.assertEqual(truth_intersection((0, 1.0), (4, 0.6)), (0, 0.6))

if __name__ == '__main__':
    unittest.main()