# Sourced by the references that add the tests of query_params to test_links.py.
python3 -I -B - <<'PY'
from pathlib import Path

tests = Path("test_links.py")
text = tests.read_text(encoding="utf-8")
text = text.replace(
    "from links import with_trailing_slash", "from links import query_params, with_trailing_slash"
)
text = text.replace(
    '\n\nif __name__ == "__main__":',
    '''

class QueryParamsTest(unittest.TestCase):
    def test_repeated_names_keep_their_order(self):
        self.assertEqual(
            query_params("https://x.test/p?a=1&a=2&b="), {"a": ["1", "2"], "b": [""]}
        )

    def test_escapes_and_plus_are_decoded(self):
        self.assertEqual(
            query_params("https://x.test/p?q=caf%C3%A9+au+lait&tag=%2B"),
            {"q": ["café au lait"], "tag": ["+"]},
        )

    def test_a_name_with_no_value_is_kept(self):
        self.assertEqual(query_params("https://x.test/p?flag"), {"flag": [""]})

    def test_the_fragment_and_a_missing_query_are_left_out(self):
        self.assertEqual(query_params("https://x.test/p?a=1#b=2"), {"a": ["1"]})
        self.assertEqual(query_params("https://x.test/p"), {})


if __name__ == "__main__":''',
)
tests.write_text(text, encoding="utf-8")
PY
