import unittest

from harnesskit.prompt import PromptBuilder, Profile, normalize_json, system_payload


class PromptTests(unittest.TestCase):
    def test_dynamic_changes_keep_the_cache_key(self):
        b = PromptBuilder(["You are a coding agent.", "Read before you edit."])
        p1, k1 = b.build({"env": "date: Monday", "cwd": "/a"})
        p2, k2 = b.build({"env": "date: Tuesday", "cwd": "/b"})
        self.assertEqual(k1, k2)
        self.assertNotEqual(p1, p2)
        self.assertTrue(p1.startswith(b.static))
        self.assertTrue(p2.startswith(b.static))

    def test_static_changes_change_the_key(self):
        a = PromptBuilder(["one"]).cache_key()
        b = PromptBuilder(["one", "two"]).cache_key()
        self.assertNotEqual(a, b)

    def test_empty_dynamic_sections_are_skipped(self):
        p, _ = PromptBuilder(["s"]).build({"skills": "", "env": "x"})
        self.assertNotIn("<skills>", p)

    def test_json_is_byte_stable(self):
        self.assertEqual(normalize_json({"b": 1, "a": 2}), normalize_json({"a": 2, "b": 1}))
        self.assertEqual(normalize_json({"a": [1, 2]}), '{"a":[1,2]}')

    def test_profiles_shape_the_payload(self):
        bp = system_payload(Profile("a", "breakpoint"), "S", "D", "k")
        self.assertIn("cache_control", bp[0])
        self.assertNotIn("cache_control", bp[1])
        self.assertEqual(system_payload(Profile("b", "key"), "S", "D", "k")["prompt_cache_key"], "k")
        self.assertNotIn("prompt_cache_key", system_payload(Profile("c", "none"), "S", "D", "k"))


if __name__ == "__main__":
    unittest.main()
