"""Tab completion for readline (Linux/macOS) and Console API (Windows)."""
import os
import platform
from pybash.utils import Trie

IS_WINDOWS = platform.system() == "Windows"


class ReadlineCompleter:
    """Readline-based tab completer for Linux/macOS."""

    def __init__(self, shell):
        self.shell = shell
        self._rl_matches = []

    def setup(self):
        import readline
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set completion-ignore-case on")
        readline.set_completer(self.complete)
        readline.set_completer_delims(' \t\n|&;<>()$')

    def complete(self, text, state):
        if state == 0:
            self.shell._invalidate_path_cache(self.shell.state.cwd)
            self._rl_matches = self._get_completions(text)
        try:
            return self._rl_matches[state]
        except (IndexError, AttributeError):
            return None

    def _get_completions(self, text):
        import readline
        line = readline.get_line_buffer()
        before = line[:len(line) - len(text)]

        tokens = before.split()
        is_first_word = len(tokens) == 0

        if is_first_word:
            return self.shell._cmd_trie.starts_with(text)
        else:
            if '/' in text or '\\' in text:
                dir_part = os.path.dirname(text) or '.'
                base_part = os.path.basename(text)
            else:
                dir_part = '.'
                base_part = text
            trie = self.shell._get_path_trie(dir_part)
            return trie.starts_with(base_part)


class WindowsCompleter:
    """Windows Console API-based tab completer using ctypes."""

    def __init__(self, shell):
        self.shell = shell

    def tab_complete(self, buf):
        self.shell._invalidate_path_cache(self.shell.state.cwd)
        tokens = buf.split()
        is_first_word = not ' ' in buf.rstrip()

        if not buf or buf.endswith(' '):
            word = ""
        else:
            word = tokens[-1] if tokens else ""

        if is_first_word:
            matches = self.shell._cmd_trie.starts_with(word) if word else []
        else:
            if '/' in word or '\\' in word:
                dir_part = os.path.dirname(word) or '.'
                base_part = os.path.basename(word)
            else:
                dir_part = '.'
                base_part = word
            trie = self.shell._get_path_trie(dir_part)
            matches = trie.starts_with(base_part) if base_part else []

        if not matches:
            return buf

        common = os.path.commonprefix(matches)
        if len(common) > len(word):
            suffix = common[len(word):]
            import sys
            sys.stdout.write(suffix)
            sys.stdout.flush()
            return buf + suffix

        if len(matches) == 1:
            suffix = matches[0][len(word):]
            import sys
            sys.stdout.write(suffix)
            sys.stdout.flush()
            return buf + suffix

        if is_first_word:
            sorted_matches = self.shell._sort_cmds(matches)
            first = sorted_matches[0]
            suffix = first[len(word):]
            import sys
            sys.stdout.write(suffix)
            sys.stdout.flush()
            return buf + suffix

        return buf

    def list_matches(self, buf):
        self.shell._invalidate_path_cache(self.shell.state.cwd)
        tokens = buf.split()
        is_first_word = not ' ' in buf.rstrip()

        if not buf or buf.endswith(' '):
            word = ""
        else:
            word = tokens[-1] if tokens else ""

        if is_first_word:
            matches = self.shell._cmd_trie.starts_with(word) if word else []
        else:
            if '/' in word or '\\' in word:
                dir_part = os.path.dirname(word) or '.'
                base_part = os.path.basename(word)
            else:
                dir_part = '.'
                base_part = word
            trie = self.shell._get_path_trie(dir_part)
            matches = trie.starts_with(base_part) if base_part else []

        if not matches:
            import sys
            sys.stdout.write('\a')
            sys.stdout.flush()
            return

        sorted_matches = self.shell._sort_cmds(matches) if is_first_word else sorted(matches)

        import sys
        sys.stdout.write('\n')
        for m in sorted_matches:
            sys.stdout.write(f"  {m}\n")
        sys.stdout.flush()
