import unittest

from bridge.quick_chat.models import require_identifier, require_optional_string


class ModelValidationTests(unittest.TestCase):
    def test_identifier_must_be_non_empty_string(self):
        self.assertEqual(require_identifier("requestId", "req-1"), "req-1")
        for invalid in (None, "", "   ", 1):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    require_identifier("requestId", invalid)

    def test_optional_string_preserves_none_and_rejects_other_types(self):
        self.assertIsNone(require_optional_string("model", None))
        self.assertEqual(require_optional_string("model", "fast"), "fast")
        with self.assertRaises(ValueError):
            require_optional_string("model", False)


if __name__ == "__main__":
    unittest.main()
