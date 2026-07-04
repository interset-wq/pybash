"""Tests for built-in commands."""
import os
import sys
import unittest
from io import StringIO


def _run(shell, line):
    """Execute a line in the shell, capture stdout, return (output, returncode)."""
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = shell.execute_line(line)
    finally:
        sys.stdout = old
    return buf.getvalue(), rc


class TestEcho(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_echo_simple(self):
        out, rc = _run(self.s, "echo hello")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "hello")

    def test_echo_empty(self):
        out, rc = _run(self.s, "echo")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "\n")

    def test_echo_multiple(self):
        out, rc = _run(self.s, "echo a b c")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "a b c")


class TestPrintf(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_printf_string(self):
        out, rc = _run(self.s, "printf %s hello")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "hello")

    def test_printf_int(self):
        out, rc = _run(self.s, "printf %d 42")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "42")


class TestPwd(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_pwd(self):
        out, rc = _run(self.s, "pwd")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), os.getcwd())


class TestCd(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.orig = os.getcwd()

    def tearDown(self):
        os.chdir(self.orig)

    def test_cd_dot(self):
        rc = self.s.execute_line("cd .")
        self.assertEqual(rc, 0)

    def test_cd_dotdot(self):
        rc = self.s.execute_line("cd ..")
        self.assertEqual(rc, 0)
        self.assertEqual(os.getcwd(), os.path.dirname(self.orig))

    def test_cd_nonexistent(self):
        out, rc = _run(self.s, "cd /nonexistent/path/xyz")
        self.assertEqual(rc, 1)


class TestMkdirRmdir(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_mkdir_and_rmdir(self):
        d = os.path.join(self.cwd, "test_mkdir_dir")
        rc = self.s.execute_line(f"mkdir {d}")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isdir(d))
        rc = self.s.execute_line(f"rmdir {d}")
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(d))

    def test_mkdir_p(self):
        d = os.path.join(self.cwd, "a", "b", "c")
        rc = self.s.execute_line(f"mkdir -p {d}")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isdir(d))
        import shutil
        shutil.rmtree(os.path.join(self.cwd, "a"))


class TestTouch(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "test_touch.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_touch_creates_file(self):
        fp = os.path.join(self.cwd, "test_touch.txt")
        rc = self.s.execute_line(f"touch {fp}")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(fp))


class TestCpMvRm(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        for f in ["cp_src.txt", "cp_dst.txt", "mv_src.txt", "mv_dst.txt", "rm_test.txt"]:
            p = os.path.join(self.cwd, f)
            if os.path.exists(p):
                os.remove(p)

    def test_cp(self):
        src = os.path.join(self.cwd, "cp_src.txt")
        dst = os.path.join(self.cwd, "cp_dst.txt")
        with open(src, "w") as f:
            f.write("hello")
        rc = self.s.execute_line(f"cp {src} {dst}")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(dst))
        with open(dst) as f:
            self.assertEqual(f.read(), "hello")

    def test_mv(self):
        src = os.path.join(self.cwd, "mv_src.txt")
        dst = os.path.join(self.cwd, "mv_dst.txt")
        with open(src, "w") as f:
            f.write("data")
        rc = self.s.execute_line(f"mv {src} {dst}")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(dst))
        self.assertFalse(os.path.isfile(src))

    def test_rm(self):
        fp = os.path.join(self.cwd, "rm_test.txt")
        with open(fp, "w") as f:
            f.write("delete me")
        rc = self.s.execute_line(f"rm {fp}")
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.isfile(fp))


class TestCat(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "cat_test.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_cat(self):
        fp = os.path.join(self.cwd, "cat_test.txt")
        with open(fp, "w") as f:
            f.write("line1\nline2\n")
        out, rc = _run(self.s, f"cat {fp}")
        self.assertEqual(rc, 0)
        self.assertIn("line1", out)
        self.assertIn("line2", out)


class TestGrep(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "grep_test.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_grep_match(self):
        fp = os.path.join(self.cwd, "grep_test.txt")
        with open(fp, "w") as f:
            f.write("hello\nworld\nhello again\n")
        out, rc = _run(self.s, f"grep hello {fp}")
        self.assertEqual(rc, 0)
        self.assertIn("hello", out)
        self.assertNotIn("world", out)

    def test_grep_no_match(self):
        fp = os.path.join(self.cwd, "grep_test.txt")
        with open(fp, "w") as f:
            f.write("hello\nworld\n")
        out, rc = _run(self.s, f"grep xyz {fp}")
        self.assertEqual(rc, 1)


class TestSort(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "sort_test.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_sort(self):
        fp = os.path.join(self.cwd, "sort_test.txt")
        with open(fp, "w") as f:
            f.write("c\na\nb\n")
        out, rc = _run(self.s, f"sort {fp}")
        self.assertEqual(rc, 0)
        lines = out.strip().split("\n")
        self.assertEqual(lines, ["a", "b", "c"])

    def test_sort_r(self):
        fp = os.path.join(self.cwd, "sort_test.txt")
        with open(fp, "w") as f:
            f.write("c\na\nb\n")
        out, rc = _run(self.s, f"sort -r {fp}")
        self.assertEqual(rc, 0)
        lines = out.strip().split("\n")
        self.assertEqual(lines, ["c", "b", "a"])


class TestWc(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "wc_test.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_wc_l(self):
        fp = os.path.join(self.cwd, "wc_test.txt")
        with open(fp, "w") as f:
            f.write("a\nb\nc\n")
        out, rc = _run(self.s, f"wc -l {fp}")
        self.assertEqual(rc, 0)
        self.assertIn("3", out)


class TestHeadTail(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()
        self.cwd = os.getcwd()

    def tearDown(self):
        p = os.path.join(self.cwd, "ht_test.txt")
        if os.path.exists(p):
            os.remove(p)

    def test_head(self):
        fp = os.path.join(self.cwd, "ht_test.txt")
        with open(fp, "w") as f:
            for i in range(20):
                f.write(f"line{i}\n")
        out, rc = _run(self.s, f"head -n 3 {fp}")
        self.assertEqual(rc, 0)
        self.assertIn("line0", out)
        self.assertIn("line2", out)

    def test_tail(self):
        fp = os.path.join(self.cwd, "ht_test.txt")
        with open(fp, "w") as f:
            for i in range(20):
                f.write(f"line{i}\n")
        out, rc = _run(self.s, f"tail -n 3 {fp}")
        self.assertEqual(rc, 0)
        self.assertIn("line19", out)


class TestDate(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_date(self):
        out, rc = _run(self.s, "date")
        self.assertEqual(rc, 0)
        self.assertTrue(len(out.strip()) > 0)


class TestUname(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_uname(self):
        out, rc = _run(self.s, "uname")
        self.assertEqual(rc, 0)
        self.assertTrue(len(out.strip()) > 0)


class TestType(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_type_builtin(self):
        out, rc = _run(self.s, "type ls")
        self.assertEqual(rc, 0)
        self.assertIn("shell builtin", out)

    def test_type_alias(self):
        out, rc = _run(self.s, "type dir")
        self.assertEqual(rc, 0)
        self.assertIn("aliased to", out)


class TestWhich(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_which_builtin(self):
        out, rc = _run(self.s, "which ls")
        self.assertEqual(rc, 0)
        self.assertIn("shell built-in", out)


class TestHelp(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_help(self):
        out, rc = _run(self.s, "help")
        self.assertEqual(rc, 0)
        self.assertIn("PyBash", out)


class TestEval(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_eval(self):
        out, rc = _run(self.s, "eval echo eval_works")
        self.assertEqual(rc, 0)
        self.assertIn("eval_works", out)


class TestExport(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def tearDown(self):
        os.environ.pop("PYBASH_TEST_VAR", None)

    def test_export_and_printenv(self):
        self.s.execute_line("export PYBASH_TEST_VAR=hello")
        out, rc = _run(self.s, "printenv PYBASH_TEST_VAR")
        self.assertEqual(rc, 0)
        self.assertIn("hello", out)


class TestSeq(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_seq_3(self):
        out, rc = _run(self.s, "seq 3")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "1\n2\n3")

    def test_seq_range(self):
        out, rc = _run(self.s, "seq 2 4")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "2\n3\n4")


class TestSleep(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_sleep_returns_zero(self):
        import time
        start = time.time()
        rc = self.s.execute_line("sleep 0.01")
        elapsed = time.time() - start
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(elapsed, 0.01)


class TestLs(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_ls(self):
        out, rc = _run(self.s, "ls")
        self.assertEqual(rc, 0)
        self.assertIn("pybash", out)

    def test_ls_l(self):
        out, rc = _run(self.s, "ls -l")
        self.assertEqual(rc, 0)
        self.assertIn("pybash", out)

    def test_ls_a(self):
        out, rc = _run(self.s, "ls -a")
        self.assertEqual(rc, 0)
        self.assertIn(".git", out)


class TestTrueFalse(unittest.TestCase):
    def setUp(self):
        from pybash.shell import Shell
        self.s = Shell()

    def test_true(self):
        rc = self.s.execute_line("true")
        self.assertEqual(rc, 0)

    def test_false(self):
        rc = self.s.execute_line("false")
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
