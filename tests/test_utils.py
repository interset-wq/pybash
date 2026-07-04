"""Tests for utils: Tokenizer and Trie."""
import os
import unittest


class TestTrie(unittest.TestCase):
    def setUp(self):
        from pybash.utils import Trie
        self.trie = Trie()

    def test_insert_and_search(self):
        self.trie.insert("hello", "v1")
        self.assertEqual(self.trie.search("hello"), "v1")
        self.assertIsNone(self.trie.search("hell"))

    def test_starts_with(self):
        self.trie.insert("cat")
        self.trie.insert("car")
        self.trie.insert("card")
        results = self.trie.starts_with("ca")
        self.assertEqual(sorted(results), ["car", "card", "cat"])

    def test_starts_with_no_match(self):
        self.trie.insert("hello")
        results = self.trie.starts_with("xyz")
        self.assertEqual(results, [])

    def test_delete(self):
        self.trie.insert("hello")
        self.trie.delete("hello")
        self.assertIsNone(self.trie.search("hello"))

    def test_len(self):
        self.trie.insert("a")
        self.trie.insert("b")
        self.trie.insert("c")
        self.assertEqual(len(self.trie), 3)

    def test_clear(self):
        self.trie.insert("a")
        self.trie.insert("b")
        self.trie.clear()
        self.assertEqual(len(self.trie), 0)

    def test_overwrite(self):
        self.trie.insert("key", "old")
        self.trie.insert("key", "new")
        self.assertEqual(self.trie.search("key"), "new")


class TestTokenizerExpandVariables(unittest.TestCase):
    def setUp(self):
        from pybash.shell import ShellState
        from pybash.utils import Tokenizer
        self.state = ShellState()
        self.state.vars = {"name": "world", "count": "42"}
        self.Tokenizer = Tokenizer

    def test_simple_var(self):
        result = self.Tokenizer.expand_variables("hello $name", self.state)
        self.assertEqual(result, "hello world")

    def test_braces(self):
        result = self.Tokenizer.expand_variables("hello ${name}", self.state)
        self.assertEqual(result, "hello world")

    def test_missing_var(self):
        result = self.Tokenizer.expand_variables("hello $missing", self.state)
        self.assertEqual(result, "hello ")

    def test_question_mark(self):
        self.state.last_return = 7
        result = self.Tokenizer.expand_variables("$?", self.state)
        self.assertEqual(result, "7")

    def test_pid(self):
        result = self.Tokenizer.expand_variables("$$", self.state)
        self.assertEqual(result, str(os.getpid()))

    def test_positional(self):
        self.state.positional = ["a", "b", "c"]
        result = self.Tokenizer.expand_variables("$1", self.state)
        self.assertEqual(result, "a")

    def test_all_positional(self):
        self.state.positional = ["x", "y"]
        result = self.Tokenizer.expand_variables("$@", self.state)
        self.assertEqual(result, "x y")


class TestTokenizerExpandArithmetic(unittest.TestCase):
    def setUp(self):
        from pybash.shell import ShellState
        from pybash.utils import Tokenizer
        self.state = ShellState()
        self.state.vars = {"x": "10"}
        self.Tokenizer = Tokenizer

    def test_simple_arithmetic(self):
        result = self.Tokenizer.expand_arithmetic("$((2 + 3))", self.state)
        self.assertEqual(result, "5")

    def test_arithmetic_with_var(self):
        result = self.Tokenizer.expand_arithmetic("$((x + 5))", self.state)
        self.assertEqual(result, "15")

    def test_arithmetic_multiply(self):
        result = self.Tokenizer.expand_arithmetic("$((3 * 4))", self.state)
        self.assertEqual(result, "12")


class TestTokenizerSplitPipes(unittest.TestCase):
    def setUp(self):
        from pybash.utils import Tokenizer
        self.Tokenizer = Tokenizer

    def test_no_pipe(self):
        result = self.Tokenizer.split_pipes("echo hello")
        self.assertEqual(result, ["echo hello"])

    def test_single_pipe(self):
        result = self.Tokenizer.split_pipes("cat file | grep pattern")
        self.assertEqual(len(result), 2)
        self.assertIn("cat file", result[0])
        self.assertIn("grep pattern", result[1])

    def test_multi_pipe(self):
        result = self.Tokenizer.split_pipes("a | b | c")
        self.assertEqual(len(result), 3)

    def test_pipe_in_quotes(self):
        result = self.Tokenizer.split_pipes('echo "a|b"')
        self.assertEqual(result, ['echo "a|b"'])


class TestTokenizerTokenize(unittest.TestCase):
    def setUp(self):
        from pybash.shell import ShellState
        from pybash.utils import Tokenizer
        self.state = ShellState()
        self.state.vars = {}
        self.Tokenizer = Tokenizer

    def test_simple_tokens(self):
        result = self.Tokenizer.tokenize("echo hello world", self.state)
        self.assertEqual(result, ["echo", "hello", "world"])

    def test_single_quotes(self):
        result = self.Tokenizer.tokenize("echo 'hello world'", self.state)
        self.assertEqual(result, ["echo", "hello world"])

    def test_double_quotes(self):
        result = self.Tokenizer.tokenize('echo "hello world"', self.state)
        self.assertEqual(result, ["echo", "hello world"])

    def test_empty_string(self):
        result = self.Tokenizer.tokenize("", self.state)
        self.assertEqual(result, [])


class TestTokenizerGlob(unittest.TestCase):
    def setUp(self):
        from pybash.utils import Tokenizer
        self.Tokenizer = Tokenizer

    def test_no_glob(self):
        result = self.Tokenizer.expand_glob("hello")
        self.assertEqual(result, ["hello"])

    def test_literal_backslash_on_windows(self):
        import platform
        if platform.system() == "Windows":
            result = self.Tokenizer.expand_glob("C:\\Users\\test")
            self.assertEqual(result, ["C:\\Users\\test"])


if __name__ == "__main__":
    unittest.main()
