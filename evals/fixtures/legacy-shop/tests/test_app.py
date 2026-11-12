import unittest

import app


class SmokeTest(unittest.TestCase):
    def test_unknown_customer_exits_one(self):
        self.assertEqual(1, app.main(["app.py", "report", "Nobody"]))

    def test_usage_exits_two(self):
        self.assertEqual(2, app.main(["app.py"]))


if __name__ == "__main__":
    unittest.main()
