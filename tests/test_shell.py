"""Tests for shell execution: pipes, redirects, variables, logical operators."""
import os
import sys
import unittest
from io import StringIO


def _run(shell, line):
    """Execute a line, capture stdout, return (output, returncode)."""
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = shell.execute_line(line)
    finally:
        sys.stdout = old
    return buf.getvalue(), rc


class TestVariableAssignment(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_assign_and_expand(self):
        self.s.execute_line('name=hello')
        out, rc = _run(self.s, 'echo $name')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), 'hello')

    def test_assign_braces(self):
        self.s.execute_line('name=world')
        out, rc = _run(self.s, 'echo ${name}')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), 'world')

    def test_multiple_vars(self):
        self.s.execute_line('a=1')
        self.s.execute_line('b=2')
        out, rc = _run(self.s, 'echo $a $b')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), '1 2')

    def test_var_in_string(self):
        self.s.execute_line('x=42')
        out, rc = _run(self.s, 'echo "value is $x"')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), 'value is 42')


class TestArithmetic(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_arithmetic(self):
        out, rc = _run(self.s, "echo $((2 + 3))")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "5")

    def test_arithmetic_complex(self):
        out, rc = _run(self.s, "echo $((10 * 2 + 1))")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "21")

    def test_arithmetic_with_var(self):
        self.s.execute_line('x=10')
        out, rc = _run(self.s, "echo $((x + 5))")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "15")


class TestPipes(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "pipe_test.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_simple_pipe(self):
        fp = os.path.join(self.cwd, "pipe_test.txt")
        with open(fp, "w") as f:
            f.write("alpha\nbeta\ngamma\n")
        out, rc = _run(self.s, f"cat {fp} | sort")
        self.assertEqual(rc, 0)
        lines = out.strip().split("\n")
        self.assertEqual(lines, ["alpha", "beta", "gamma"])

    def test_pipe_to_grep(self):
        fp = os.path.join(self.cwd, "pipe_test.txt")
        with open(fp, "w") as f:
            f.write("hello\nworld\nhello again\n")
        out, rc = _run(self.s, f"cat {fp} | grep hello")
        self.assertEqual(rc, 0)
        self.assertIn("hello", out)
        self.assertNotIn("world", out)


class TestRedirects(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        for f in ["redir_out.txt", "redir_append.txt"]:
            p = os.path.join(self.cwd, f)
            if os.path.exists(p):
                os.remove(p)

    def test_output_redirect(self):
        fp = os.path.join(self.cwd, "redir_out.txt")
        self.s.execute_line(f"echo hello > {fp}")
        self.assertTrue(os.path.isfile(fp))
        with open(fp) as f:
            content = f.read().strip()
        self.assertEqual(content, "hello")

    def test_append_redirect(self):
        fp = os.path.join(self.cwd, "redir_append.txt")
        self.s.execute_line(f"echo line1 > {fp}")
        self.s.execute_line(f"echo line2 >> {fp}")
        with open(fp) as f:
            content = f.read()
        self.assertIn("line1", content)
        self.assertIn("line2", content)


class TestLogicalOperators(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_and_success(self):
        rc = self.s.execute_line("true && true")
        self.assertEqual(rc, 0)

    def test_and_short_circuit(self):
        rc = self.s.execute_line("false && true")
        self.assertNotEqual(rc, 0)

    def test_or_success(self):
        rc = self.s.execute_line("false || true")
        self.assertEqual(rc, 0)

    def test_or_failure(self):
        rc = self.s.execute_line("false || false")
        self.assertNotEqual(rc, 0)


class TestSemicolons(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_semicolons(self):
        rc = self.s.execute_line("true; true; true")
        self.assertEqual(rc, 0)

    def test_semicolons_with_output(self):
        out, rc = _run(self.s, "echo a; echo b")
        self.assertEqual(rc, 0)
        self.assertIn("a", out)
        self.assertIn("b", out)


class TestConditionals(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_if_true(self):
        out, rc = _run(self.s, "if [ 1 -eq 1 ]; then echo yes; fi")
        self.assertEqual(rc, 0)
        self.assertIn("yes", out)

    def test_if_false_else(self):
        out, rc = _run(self.s, "if [ 1 -eq 2 ]; then echo yes; else echo no; fi")
        self.assertEqual(rc, 0)
        self.assertIn("no", out)

    def test_if_file_test(self):
        fp = os.path.join(os.getcwd(), "if_test.txt")
        with open(fp, "w") as f:
            f.write("")
        out, rc = _run(self.s, f'if [ -f {fp} ]; then echo exists; fi')
        self.assertEqual(rc, 0)
        self.assertIn("exists", out)
        os.remove(fp)


class TestForLoop(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_for_in(self):
        out, rc = _run(self.s, "for i in 1 2 3; do echo $i; done")
        self.assertEqual(rc, 0)
        self.assertIn("1", out)
        self.assertIn("2", out)
        self.assertIn("3", out)


class TestWhileLoop(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_while(self):
        out, rc = _run(self.s, "i=0; while [ $i -lt 3 ]; do echo $i; i=$((i+1)); done")
        self.assertEqual(rc, 0)
        self.assertIn("0", out)
        self.assertIn("2", out)


class TestFunctions(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_function_def_and_call(self):
        out, rc = _run(self.s, "greet() { echo hello $1; }; greet world")
        self.assertEqual(rc, 0)
        self.assertIn("hello world", out)

    def test_function_keyword(self):
        out, rc = _run(self.s, "function greet2 { echo hi; }; greet2")
        self.assertEqual(rc, 0)
        self.assertIn("hi", out)


class TestCommandSubstitution(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_command_sub(self):
        out, rc = _run(self.s, "echo $(echo sub)")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "sub")


class TestQuoting(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_double_quotes(self):
        self.s.execute_line("name=world")
        out, rc = _run(self.s, 'echo "hello $name"')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "hello world")

    def test_backslash(self):
        out, rc = _run(self.s, r"echo hello\ world")
        self.assertEqual(rc, 0)
        self.assertIn("hello world", out)


if __name__ == "__main__":
    unittest.main()
