import unittest
from ona import Truth_Deduction

# FILE: test_ona.py


class TestTruthDeduction(unittest.TestCase):
    
    def test_case_1(self):
        v1 = (2, 3)
        v2 = (4, 5)
        result = Truth_Deduction(v1, v2)
        self.assertEqual(result, (16, 240))
    
    def test_case_2(self):
        v1 = (1, 2)
        v2 = (3, 4)
        result = Truth_Deduction(v1, v2)
        self.assertEqual(result, (9, 72))
    
    def test_case_3(self):
        v1 = (0, 1)
        v2 = (2, 3)
        result = Truth_Deduction(v1, v2)
        self.assertEqual(result, (4, 12))



if __name__ == '__main__':
    unittest.main()