"""
Core shell: REPL loop, command parsing, pipeline, redirection, variable expansion.
Tab completion via Trie. On Windows uses Console API via ctypes, on Linux uses readline.
"""
import os
import sys
import re
import platform
import struct
import subprocess
import getpass
import socket
import atexit
from pathlib import Path
from io import StringIO

from pybash.utils import Tokenizer, Trie

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    os.system("")
    import ctypes
    import ctypes.wintypes

    _kernel32 = ctypes.windll.kernel32
    _user32 = ctypes.windll.user32
    _STD_INPUT_HANDLE = -10
    _STD_OUTPUT_HANDLE = -11
    _ENABLE_PROCESSED_INPUT = 0x0001
    _ENABLE_LINE_INPUT = 0x0002
    _ENABLE_ECHO_INPUT = 0x0004

    _hStdin = _kernel32.GetStdHandle(_STD_INPUT_HANDLE)
    _hStdout = _kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)

    _INPUT_RECORD_SIZE = 20
    _KEY_EVENT = 0x0001

_ctrl_c_flag = [False]

if IS_WINDOWS:
    @ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.DWORD)
    def _console_ctrl_handler(ctrl_type):
        if ctrl_type == 0:
            _ctrl_c_flag[0] = True
            return True
        return False
    _kernel32.SetConsoleCtrlHandler(_console_ctrl_handler, True)
else:
    import readline
    msvcrt = None


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
        self._cmd_trie = Trie()
        self._path_trie_cache = {}
        self._build_cmd_trie()
        self._rl_saved_completer = None

    def _get_prompt_str(self):
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

        return (
            f"\033[1;35mPyBash\033[0m "
            f"\033[1;32m{user}@{host}\033[0m "
            f"\033[1;34m{cwd_display}\033[0m "
            f"{suffix} "
        )

    def run(self):
        print(f"PyBash {platform.system()} - Type 'help' for help")
        if IS_WINDOWS:
            self._run_win()
        else:
            self._setup_readline()
            self._run_readline()

    def _setup_readline(self):
        hist_file = self.state.history_file
        try:
            readline.read_history_file(hist_file)
        except FileNotFoundError:
            pass
        readline.set_history_length(10000)
        atexit.register(readline.write_history_file, hist_file)

        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set completion-ignore-case on")
        readline.set_completer(self._readline_completer)
        readline.set_completer_delims(' \t\n|&;<>()$')

    def _readline_completer(self, text, state):
        if state == 0:
            self._invalidate_path_cache(self.state.cwd)
            self._rl_matches = self._get_completions(text)
        try:
            return self._rl_matches[state]
        except (IndexError, AttributeError):
            return None

    def _get_completions(self, text):
        line = readline.get_line_buffer()
        before = line[:len(line) - len(text)]

        tokens = before.split()
        is_first_word = len(tokens) == 0

        if is_first_word:
            return self._cmd_trie.starts_with(text)
        else:
            if '/' in text or '\\' in text:
                dir_part = os.path.dirname(text) or '.'
                base_part = os.path.basename(text)
            else:
                dir_part = '.'
                base_part = text
            trie = self._get_path_trie(dir_part)
            return trie.starts_with(base_part)

    def _read_console_key(self):
        buf = (ctypes.c_char * 20)()
        nread = ctypes.wintypes.DWORD()
        _kernel32.ReadConsoleInputW(_hStdin, buf, 1, ctypes.byref(nread))
        for i in range(nread.value):
            off = i * _INPUT_RECORD_SIZE
            evt_type = struct.unpack_from('<H', buf, off)[0]
            if evt_type != _KEY_EVENT:
                continue
            bKeyDown = struct.unpack_from('<I', buf, off + 4)[0]
            if not bKeyDown:
                continue
            vk = struct.unpack_from('<H', buf, off + 10)[0]
            uc = struct.unpack_from('<H', buf, off + 14)[0]
            if 32 <= uc < 127 or uc in (9, 10, 13):
                return chr(uc), vk
            if uc:
                return None, vk
            return None, vk
        return None, 0

    def _set_raw_mode(self, raw=True):
        mode = ctypes.wintypes.DWORD()
        _kernel32.GetConsoleMode(_hStdin, ctypes.byref(mode))
        if raw:
            mode.value &= ~(_ENABLE_PROCESSED_INPUT | _ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT)
        else:
            mode.value |= _ENABLE_PROCESSED_INPUT | _ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT
        _kernel32.SetConsoleMode(_hStdin, mode)

    def _read_console_key_nonblocking(self):
        result = _kernel32.WaitForSingleObject(_hStdin, 16)
        if result != 0:
            return None, 0
        return self._read_console_key()

    def _run_win(self):
        _kernel32.FlushConsoleInputBuffer(_hStdin)
        self._set_raw_mode(True)
        buf = ""
        prompt = self._get_prompt_str()
        sys.stdout.write(prompt)
        sys.stdout.flush()
        _VK_CONTROL = 0x11
        _VK_CTRL_C = 0x43
        _VK_CTRL_D = 0x44
        _VK_CTRL_L = 0x4C
        _ctrl_c_held = False
        _ctrl_d_held = False
        _ctrl_l_held = False
        try:
            while self.state.running:
                try:
                    self._set_raw_mode(True)
                    if _ctrl_c_flag[0]:
                        _ctrl_c_flag[0] = False
                        sys.stdout.write('^C\n')
                        sys.stdout.flush()
                        _kernel32.FlushConsoleInputBuffer(_hStdin)
                        buf = ""
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                        continue
                    ctrl_down = bool(_user32.GetAsyncKeyState(_VK_CONTROL) & 0x8000)
                    ctrl_c_now = ctrl_down and bool(_user32.GetAsyncKeyState(_VK_CTRL_C) & 0x8000)
                    ctrl_d_now = ctrl_down and bool(_user32.GetAsyncKeyState(_VK_CTRL_D) & 0x8000)
                    ctrl_l_now = ctrl_down and bool(_user32.GetAsyncKeyState(_VK_CTRL_L) & 0x8000)
                    if ctrl_c_now and not _ctrl_c_held:
                        _ctrl_c_held = True
                        sys.stdout.write('^C\n')
                        sys.stdout.flush()
                        _kernel32.FlushConsoleInputBuffer(_hStdin)
                        buf = ""
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                        continue
                    _ctrl_c_held = ctrl_c_now
                    if ctrl_d_now and not _ctrl_d_held:
                        _ctrl_d_held = True
                        if not buf:
                            print()
                            break
                        buf = ""
                        sys.stdout.write('\n' + self._get_prompt_str())
                        sys.stdout.flush()
                        continue
                    _ctrl_d_held = ctrl_d_now
                    if ctrl_l_now and not _ctrl_l_held:
                        _ctrl_l_held = True
                        sys.stdout.write('\033[2J\033[H')
                        sys.stdout.flush()
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                        continue
                    _ctrl_l_held = ctrl_l_now
                    ch, vk = self._read_console_key_nonblocking()
                    if vk == 0:
                        import time
                        time.sleep(0.01)
                        continue
                    if vk == 0x0D:
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        clean = ''.join(c for c in buf if c.isprintable() or c in '\t')
                        if clean.strip():
                            self.execute_line(clean)
                        _kernel32.FlushConsoleInputBuffer(_hStdin)
                        buf = ""
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                    elif vk == 0x03:
                        sys.stdout.write('^C\n')
                        sys.stdout.flush()
                        _kernel32.FlushConsoleInputBuffer(_hStdin)
                        buf = ""
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                    elif vk == 0x04:
                        if not buf:
                            print()
                            break
                        buf = ""
                        sys.stdout.write('\n')
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                    elif vk == 0x0C:
                        sys.stdout.write('\033[2J\033[H')
                        sys.stdout.flush()
                        prompt = self._get_prompt_str()
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                    elif vk == 0x08:
                        if buf:
                            buf = buf[:-1]
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                    elif vk == 0x09:
                        buf = self._tab_complete_win(buf)
                    elif vk == 0x12:
                        self._list_matches(buf)
                        sys.stdout.write(prompt + buf)
                        sys.stdout.flush()
                    elif vk == 0x1B:
                        raise EOFError
                    elif ch and ch.isprintable():
                        buf += ch
                        sys.stdout.write(ch)
                        sys.stdout.flush()
                except KeyboardInterrupt:
                    print()
                    _kernel32.FlushConsoleInputBuffer(_hStdin)
                    buf = ""
                    prompt = self._get_prompt_str()
                    sys.stdout.write(prompt)
                    sys.stdout.flush()
                except EOFError:
                    print()
                    break
                except Exception as e:
                    print(f"pybash: {e}", file=sys.stderr)
                    buf = ""
                    prompt = self._get_prompt_str()
                    sys.stdout.write(prompt)
                    sys.stdout.flush()
        finally:
            self._set_raw_mode(False)

    def _tab_complete_win(self, buf):
        self._invalidate_path_cache(self.state.cwd)
        tokens = buf.split()
        is_first_word = not ' ' in buf.rstrip()

        if not buf or buf.endswith(' '):
            word = ""
        else:
            word = tokens[-1] if tokens else ""

        if is_first_word:
            matches = self._cmd_trie.starts_with(word) if word else []
        else:
            if '/' in word or '\\' in word:
                dir_part = os.path.dirname(word) or '.'
                base_part = os.path.basename(word)
            else:
                dir_part = '.'
                base_part = word
            trie = self._get_path_trie(dir_part)
            matches = trie.starts_with(base_part) if base_part else []

        if not matches:
            return buf

        common = os.path.commonprefix(matches)
        if len(common) > len(word):
            suffix = common[len(word):]
            sys.stdout.write(suffix)
            sys.stdout.flush()
            return buf + suffix

        if len(matches) == 1:
            suffix = matches[0][len(word):]
            sys.stdout.write(suffix)
            sys.stdout.flush()
            return buf + suffix

        if is_first_word:
            sorted_matches = self._sort_cmds(matches)
            first = sorted_matches[0]
            suffix = first[len(word):]
            sys.stdout.write(suffix)
            sys.stdout.flush()
            return buf + suffix

        return buf

    def _sort_cmds(self, matches):
        builtins = []
        externals = []
        for m in matches:
            val = self._cmd_trie.search(m)
            if val and val[0] == 'builtin':
                builtins.append(m)
            else:
                externals.append(m)
        return sorted(builtins) + sorted(externals)

    def _list_matches(self, buf):
        self._invalidate_path_cache(self.state.cwd)
        tokens = buf.split()
        is_first_word = not ' ' in buf.rstrip()

        if not buf or buf.endswith(' '):
            word = ""
        else:
            word = tokens[-1] if tokens else ""

        if is_first_word:
            matches = self._cmd_trie.starts_with(word) if word else []
        else:
            if '/' in word or '\\' in word:
                dir_part = os.path.dirname(word) or '.'
                base_part = os.path.basename(word)
            else:
                dir_part = '.'
                base_part = word
            trie = self._get_path_trie(dir_part)
            matches = trie.starts_with(base_part) if base_part else []

        if not matches:
            sys.stdout.write('\a')
            sys.stdout.flush()
            return

        sorted_matches = self._sort_cmds(matches) if is_first_word else sorted(matches)

        sys.stdout.write('\n')
        for m in sorted_matches:
            sys.stdout.write(f"  {m}\n")
        sys.stdout.flush()

    def _run_readline(self):
        while self.state.running:
            try:
                prompt = self._get_prompt_str()
                line = input(prompt)
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
        trie = Trie()
        try:
            for entry in os.listdir(dir_path):
                full = os.path.join(dir_path, entry)
                is_dir = os.path.isdir(full)
                trie.insert(entry, ('dir' if is_dir else 'file', entry))
        except (PermissionError, FileNotFoundError):
            pass
        return trie

    def _invalidate_path_cache(self, dir_path=None):
        self._path_trie_cache.clear()

    def _complete_path_trie(self, prefix):
        prefix = os.path.expanduser(prefix)
        if '/' in prefix or '\\' in prefix:
            dir_part = os.path.dirname(prefix) or '.'
            base_part = os.path.basename(prefix)
        else:
            dir_path = '.'
            base_part = prefix
        trie = self._get_path_trie(dir_part if '/' in prefix or '\\' in prefix else '.')
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
