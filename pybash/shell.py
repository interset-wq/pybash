"""
Core shell: REPL loop, command parsing, pipeline, redirection, variable expansion.
"""
import os
import sys
import re
import platform
import subprocess
import getpass
import socket
from pathlib import Path
from io import StringIO

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import Window, BufferControl, HSplit, Layout
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    HAS_PT = True
except ImportError:
    HAS_PT = False

from pybash.utils import Tokenizer, Trie

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    os.system("")


class ShellState:
    def __init__(self):
        self.vars = {}
        self.functions = {}
        self.last_return = 0
        self.running = True
        self.cwd = os.getcwd()
        self.history_file = str(Path.home() / ".pybash_history")
        self.alias_file = str(Path.home() / ".pybash_aliases")
        self.positional = []


from pybash.builtins import BuiltinCommands
from pybash.script import ScriptEngine


class RedirectHandler:
    @staticmethod
    def parse(tokens):
        cmd_tokens = []
        redirects = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ('>', '>>', '1>', '1>>'):
                mode = 'a' if '>>' in tok else 'w'
                if i + 1 < len(tokens):
                    redirects.append((1, mode, tokens[i + 1]))
                    i += 2
                else:
                    i += 1
            elif tok in ('2>', '2>>'):
                mode = 'a' if '>>' in tok else 'w'
                if i + 1 < len(tokens):
                    redirects.append((2, mode, tokens[i + 1]))
                    i += 2
                else:
                    i += 1
            elif tok in ('<', '0<'):
                if i + 1 < len(tokens):
                    redirects.append((0, 'r', tokens[i + 1]))
                    i += 2
                else:
                    i += 1
            elif re.match(r'^\d+>$', tok):
                fd = int(tok[:-1])
                if i + 1 < len(tokens):
                    redirects.append((fd, 'w', tokens[i + 1]))
                    i += 2
            elif re.match(r'^\d+>>$', tok):
                fd = int(tok[:-2])
                if i + 1 < len(tokens):
                    redirects.append((fd, 'a', tokens[i + 1]))
                    i += 2
            else:
                cmd_tokens.append(tok)
                i += 1
        return cmd_tokens, redirects

    @staticmethod
    def apply(redirects):
        saved = []
        saved_streams = []
        for fd, mode, filename in redirects:
            filename = os.path.expanduser(filename)
            try:
                saved_fd = os.dup(fd)
                saved.append((fd, saved_fd))
                if fd == 0:
                    f = open(filename, 'r', encoding='utf-8', errors='replace')
                else:
                    f = open(filename, mode, encoding='utf-8')
                os.dup2(f.fileno(), fd)
                if fd == 1:
                    saved_streams.append((1, sys.stdout))
                    sys.stdout = f
                elif fd == 2:
                    saved_streams.append((2, sys.stderr))
                    sys.stderr = f
                if fd == 0:
                    f.close()
            except Exception as e:
                print(f"pybash: redirect error: {e}", file=sys.stderr)
                RedirectHandler.restore(saved, saved_streams)
                return None
        return saved, saved_streams

    @staticmethod
    def restore(saved, saved_streams=None):
        if saved is None:
            return
        for fd, saved_fd in saved:
            try:
                os.dup2(saved_fd, fd)
                os.close(saved_fd)
            except Exception:
                pass
        if saved_streams:
            for fd, stream in saved_streams:
                if fd == 1:
                    try:
                        sys.stdout.flush()
                    except Exception:
                        pass
                    sys.stdout = stream
                elif fd == 2:
                    try:
                        sys.stderr.flush()
                    except Exception:
                        pass
                    sys.stderr = stream


class Shell:
    def __init__(self):
        self.state = ShellState()
        self.builtins = BuiltinCommands(self.state)
        self.engine = ScriptEngine(self.state, self)
        self._pt_session = None
        self._cmd_trie = Trie()
        self._path_trie_cache = {}
        self._build_cmd_trie()

    def _get_prompt_tokens(self):
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        try:
            if cwd.startswith(home):
                cwd_display = "~" + cwd[len(home):]
            else:
                cwd_display = cwd
        except Exception:
            cwd_display = cwd

        try:
            user = getpass.getuser()
        except Exception:
            user = "user"

        try:
            host = socket.gethostname()
        except Exception:
            host = "localhost"

        try:
            is_root = os.getuid() == 0
        except AttributeError:
            is_root = False

        suffix = "#" if is_root else "$"

        return ANSI(
            f"\033[1;35mPyBash\033[0m "
            f"\033[1;32m{user}@{host}\033[0m "
            f"\033[1;34m{cwd_display}\033[0m "
            f"{suffix} "
        )

    def run(self):
        print(f"PyBash {platform.system()} - Type 'help' for help")
        if HAS_PT:
            history = FileHistory(self.state.history_file)
            bindings = KeyBindings()
            self._tab_matches = []
            self._tab_pending = False

            @bindings.add(Keys.Tab)
            def _(event):
                self._handle_tab(event)

            self._pt_session = PromptSession(
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                complete_while_typing=False,
                key_bindings=bindings,
            )
            self._run_pt()
        else:
            self._run_basic()

    def _run_pt(self):
        while self.state.running:
            try:
                line = self._pt_session.prompt(
                    self._get_prompt_tokens(),
                )
                if not line.strip():
                    continue
                self.execute_line(line)
            except KeyboardInterrupt:
                print()
            except EOFError:
                print()
                break
            except Exception as e:
                print(f"pybash: {e}", file=sys.stderr)

    def _run_basic(self):
        while self.state.running:
            try:
                prompt = self._get_prompt_tokens()
                sys.stdout.write(prompt)
                sys.stdout.flush()
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.rstrip('\n\r')
                if not line.strip():
                    continue
                self.execute_line(line)
            except KeyboardInterrupt:
                print()
            except EOFError:
                print()
                break
            except Exception as e:
                print(f"pybash: {e}", file=sys.stderr)

    def _handle_tab(self, event):
        buf = event.app.current_buffer
        cursor_pos = buf.cursor_position
        text = buf.text[:cursor_pos]

        word_start = cursor_pos
        while word_start > 0 and text[word_start - 1] not in (' ', '\t', '|', '&', ';', '(', ')', '$', '<', '>'):
            word_start -= 1
        word = text[word_start:cursor_pos]

        if not word and not text.endswith(' '):
            return

        tokens = text.split()
        is_first_word = (len(tokens) <= 1)

        if is_first_word:
            matches = self._cmd_trie.starts_with(word)
        else:
            matches = [name for name, _ in self._complete_path_trie(word)]

        if not matches:
            return

        if len(matches) == 1:
            suffix = matches[0][len(word):]
            buf.insert_text(suffix)
            self._tab_matches = []
            self._tab_pending = False
        else:
            common = os.path.commonprefix(matches)
            if len(common) > len(word):
                buf.insert_text(common[len(word):])
                self._tab_matches = []
                self._tab_pending = False
            elif self._tab_pending and self._tab_matches == matches:
                saved_text = buf.text
                saved_cursor = buf.cursor_position
                buf.reset()
                col_width = max(len(m) for m in matches) + 2
                cols = max(1, 80 // col_width)
                lines = []
                for i in range(0, len(matches), cols):
                    row = matches[i:i + cols]
                    lines.append('  '.join(f'{m:<{col_width}}' for m in row))
                output = '\n'.join(lines) + '\n'
                try:
                    event.app.renderer.write_and_flush(output)
                except Exception:
                    sys.stdout.write(output)
                    sys.stdout.flush()
                buf.text = saved_text
                buf.cursor_position = saved_cursor
                event.app.invalidate()
                self._tab_matches = []
                self._tab_pending = False
            else:
                self._tab_matches = matches
                self._tab_pending = True

    def _build_cmd_trie(self):
        self._cmd_trie.clear()
        for name in self.builtins.cmds.keys():
            self._cmd_trie.insert(name, ('builtin', name))
        seen = set()
        exe_suffixes = ('.exe', '.cmd', '.bat', '.com', '.ps1') if IS_WINDOWS else ()
        for d in self._get_path_dirs():
            try:
                for f in os.listdir(d):
                    if f in seen:
                        continue
                    if IS_WINDOWS:
                        if not any(f.lower().endswith(s) for s in exe_suffixes):
                            continue
                    full = os.path.join(d, f)
                    if os.path.isfile(full):
                        seen.add(f)
                        self._cmd_trie.insert(f, ('path', f))
            except (PermissionError, FileNotFoundError):
                pass
        for name in self.state.functions:
            self._cmd_trie.insert(name, ('function', name))

    def _get_path_trie(self, dir_path):
        dir_path = os.path.expanduser(dir_path)
        if dir_path in self._path_trie_cache:
            return self._path_trie_cache[dir_path]
        trie = Trie()
        try:
            for entry in os.listdir(dir_path):
                full = os.path.join(dir_path, entry)
                is_dir = os.path.isdir(full)
                trie.insert(entry, ('dir' if is_dir else 'file', entry))
        except (PermissionError, FileNotFoundError):
            pass
        self._path_trie_cache[dir_path] = trie
        return trie

    def _invalidate_path_cache(self, dir_path=None):
        if dir_path:
            self._path_trie_cache.pop(dir_path, None)
        else:
            self._path_trie_cache.clear()

    def _complete_path_trie(self, prefix):
        prefix = os.path.expanduser(prefix)
        if '/' in prefix or '\\' in prefix:
            dir_part = os.path.dirname(prefix) or '.'
            base_part = os.path.basename(prefix)
        else:
            dir_part = '.'
            base_part = prefix
        trie = self._get_path_trie(dir_part)
        results = []
        for name in trie.starts_with(base_part):
            kind = trie.search(name)
            if kind:
                kind = kind[0]
            results.append((name, kind))
        return results

    def execute_line(self, line):
        line = line.strip()
        if not line:
            return 0
        if line.startswith('#'):
            return 0
        return self._dispatch(line)

    def _dispatch(self, line):
        stripped = line.strip()
        if re.match(r'^(if|for|while|until|case|function|select)\b', stripped):
            return self.engine.execute_block([stripped])
        if re.match(r'^[A-Za-z_]\w*\s*\(\s*\)\s*\{', stripped):
            return self.engine.execute_block([stripped])
        parts = self._split_semicolons(line)
        if len(parts) > 1:
            for p in parts:
                if re.match(r'^(if|for|while|until|case|function|select)\b', p.strip()):
                    return self.engine.execute_block([stripped])
                if re.match(r'^[A-Za-z_]\w*\s*\(\s*\)\s*\{', p.strip()):
                    return self.engine.execute_block([stripped])
        if '&&' in line or '||' in line:
            return self._handle_logical(line)
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', stripped):
            self.engine._handle_var_assign(stripped)
            return 0
        pipes = Tokenizer.split_pipes(line)
        if len(pipes) > 1:
            return self._handle_pipes(pipes)
        return self._run_single(line)

    def _handle_logical(self, line):
        parts = re.split(r'(\s*&&\s*|\s*\|\|\s*)', line)
        result = 0
        op = None
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part == '&&':
                op = '&&'
                continue
            if part == '||':
                op = '||'
                continue
            if op is None:
                result = self.execute_line(part)
            elif op == '&&':
                if result == 0:
                    result = self.execute_line(part)
            elif op == '||':
                if result != 0:
                    result = self.execute_line(part)
            op = None
        return result

    def _split_semicolons(self, line):
        parts = []
        current = ""
        in_sq = in_dq = False
        for ch in line:
            if ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == ';' and not in_sq and not in_dq:
                parts.append(current)
                current = ""
                continue
            current += ch
        if current:
            parts.append(current)
        return parts

    def _handle_pipes(self, pipes):
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        input_data = None

        for i, cmd in enumerate(pipes):
            cmd = cmd.strip()
            if i > 0:
                sys.stdin = StringIO(input_data)

            buf = StringIO()
            sys.stdout = buf
            sys.stderr = buf

            tokens = Tokenizer.tokenize(cmd, self.state)
            tokens, redirects = RedirectHandler.parse(tokens)

            fds = None
            if redirects:
                fds = RedirectHandler.apply(redirects)

            result = self._exec_tokens(tokens)

            if fds is not None:
                RedirectHandler.restore(fds[0], fds[1])

            sys.stdout = old_stdout
            sys.stderr = old_stderr

            if i == len(pipes) - 1:
                output = buf.getvalue()
                if output:
                    old_stdout.write(output)
                sys.stdin = old_stdin
                return result
            else:
                input_data = buf.getvalue()

    def _run_single(self, line):
        tokens = Tokenizer.tokenize(line, self.state)
        tokens, redirects = RedirectHandler.parse(tokens)
        if not tokens:
            return 0

        fds = None
        if redirects:
            fds = RedirectHandler.apply(redirects)
            if fds is None:
                return 1

        result = self._exec_tokens(tokens)

        if fds is not None:
            RedirectHandler.restore(fds[0], fds[1])

        return result

    def _exec_tokens(self, tokens):
        if not tokens:
            return 0

        cmd = tokens[0]
        args = tokens[1:]

        if cmd in self.builtins.cmds:
            try:
                ret = self.builtins.cmds[cmd](args)
                if ret is None:
                    ret = 0
                self.state.last_return = ret
                return ret
            except SystemExit:
                raise
            except Exception as e:
                print(f"pybash: {cmd}: {e}", file=sys.stderr)
                self.state.last_return = 1
                return 1
        elif cmd in self.state.functions:
            old_vars = dict(self.state.vars)
            self.state.positional = list(args)
            for i, a in enumerate(args):
                self.state.vars[str(i + 1)] = a
            self.state.vars['#'] = str(len(args))
            ret = self.engine.execute_block(self.state.functions[cmd])
            self.state.vars.update(old_vars)
            self.state.last_return = ret
            return ret
        elif cmd in ('if', 'for', 'while', 'until', 'case', 'function', 'select'):
            ret = self.engine.execute_block([tokens[0] + ' ' + ' '.join(tokens[1:])])
            self._build_cmd_trie()
            return ret
        else:
            return self._run_external(tokens)

    def _get_path_dirs(self):
        path = os.environ.get("PATH", "")
        path = os.path.expandvars(path)
        return [d for d in path.split(os.pathsep) if d]

    def _find_in_path(self, cmd):
        if IS_WINDOWS:
            exe_exts = ('.exe', '.com', '.cmd', '.bat', '.ps1')
        else:
            exe_exts = ('',)
        for d in self._get_path_dirs():
            for ext in exe_exts:
                full = os.path.join(d, cmd + ext)
                if os.path.isfile(full):
                    return full
        return None

    def _run_external(self, tokens):
        try:
            cmd = tokens[0]
            cmd_lower = cmd.lower()

            if IS_WINDOWS:
                script_exts = ('.cmd', '.bat', '.ps1')
                exe_exts = ('.exe', '.com')
                is_script = any(cmd_lower.endswith(e) for e in script_exts)
                is_exe = any(cmd_lower.endswith(e) for e in exe_exts)

                if not is_exe:
                    if is_script:
                        tokens = ['cmd', '/c'] + tokens
                    else:
                        for d in self._get_path_dirs():
                            for ext in script_exts:
                                full = os.path.join(d, cmd + ext)
                                if os.path.isfile(full):
                                    tokens = ['cmd', '/c'] + tokens
                                    break
                            else:
                                continue
                            break

            proc = subprocess.Popen(
                tokens,
                stdin=None,
                stdout=None,
                stderr=None,
                cwd=os.getcwd(),
            )
            proc.wait()
            self.state.last_return = proc.returncode
            return proc.returncode
        except FileNotFoundError:
            print(f"pybash: {tokens[0]}: command not found", file=sys.stderr)
            self.state.last_return = 127
            return 127
        except PermissionError:
            print(f"pybash: {tokens[0]}: permission denied", file=sys.stderr)
            self.state.last_return = 126
            return 126
        except Exception as e:
            print(f"pybash: {tokens[0]}: {e}", file=sys.stderr)
            self.state.last_return = 1
            return 1


def main():
    shell = Shell()
    try:
        shell.run()
    except SystemExit:
        pass
    except Exception as e:
        print(f"pybash: fatal error: {e}", file=sys.stderr)
        sys.exit(1)
