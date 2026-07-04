"""Shell control commands: echo, printf, type, alias, history, source, test, etc."""
import os
import sys
import signal
import subprocess

IS_WINDOWS = __import__('platform').system() == "Windows"


class ShellControlCommands:
    """Mixin providing shell-control builtins."""

    def cmd_echo(self, args):
        if not args:
            print()
            return 0
        line = ' '.join(args)
        output = self._echo_expand(line)
        end = '\n'
        if line.endswith('-n'):
            end = ''
            output = output[:-2].rstrip()
        elif line.endswith('-e'):
            output = output[:-2]
        elif line.endswith('-ne') or line.endswith('-en'):
            output = output[:-3]
            end = ''
        print(output, end=end)
        return 0

    def _echo_expand(self, s):
        result = ''
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                nc = s[i + 1]
                if nc == 'n': result += '\n'; i += 2
                elif nc == 't': result += '\t'; i += 2
                elif nc == 'r': result += '\r'; i += 2
                elif nc == 'a': result += '\a'; i += 2
                elif nc == 'b': result += '\b'; i += 2
                elif nc == 'f': result += '\f'; i += 2
                elif nc == 'v': result += '\v'; i += 2
                elif nc == '\\': result += '\\'; i += 2
                elif nc == '"': result += '"'; i += 2
                elif nc == '0':
                    j = i + 2
                    octal = ''
                    while j < len(s) and s[j] in '01234567' and len(octal) < 3:
                        octal += s[j]; j += 1
                    result += chr(int(octal, 8)) if octal else '\0'
                    i = j
                elif nc == 'x':
                    if i + 3 < len(s):
                        hexstr = s[i + 2:i + 4]
                        try:
                            result += chr(int(hexstr, 16))
                            i += 4
                        except ValueError:
                            result += '\\x'; i += 2
                    else:
                        result += '\\x'; i += 2
                else:
                    result += nc; i += 2
            else:
                result += s[i]; i += 1
        return result

    def cmd_printf(self, args):
        if not args:
            return 0
        fmt = args[0]
        vals = args[1:]
        vi = 0
        result = ''
        i = 0
        while i < len(fmt):
            if fmt[i] == '%' and i + 1 < len(fmt):
                spec = fmt[i + 1]
                if spec == '%':
                    result += '%'; i += 2; continue
                if spec in ('s', 'd', 'i', 'f', 'c', 'x', 'o', 'u'):
                    val = vals[vi] if vi < len(vals) else ''
                    vi += 1
                    if spec == 's': result += val
                    elif spec in ('d', 'i'):
                        try: result += str(int(val))
                        except ValueError: result += val
                    elif spec == 'f':
                        try: result += str(float(val))
                        except ValueError: result += val
                    elif spec == 'c': result += val[0] if val else ''
                    elif spec == 'x': result += format(int(val), 'x') if val.isdigit() else val
                    elif spec == 'o': result += format(int(val), 'o') if val.isdigit() else val
                    elif spec == 'u': result += str(abs(int(val))) if val.isdigit() else val
                    i += 2; continue
            result += fmt[i]; i += 1
        print(result, end='')
        return 0

    def cmd_source(self, args):
        if not args: print("pybash: source: filename required", file=sys.stderr); return 1
        from pybash.script import ScriptEngine
        engine = ScriptEngine(self.state, self.shell)
        engine.execute_file(args[0])
        return self.state.last_return

    def cmd_type(self, args):
        for arg in args:
            if arg in self._aliases:
                print(f"{arg} is aliased to `{self._aliases[arg]}'")
            elif arg in self.cmds: print(f"{arg} is a shell builtin")
            elif arg in self.state.functions: print(f"{arg} is a function")
            else:
                path_dirs = os.environ.get("PATH", "").split(os.pathsep)
                found = False
                for d in path_dirs:
                    exe = os.path.join(d, arg)
                    if os.path.isfile(exe) and os.access(exe, os.X_OK):
                        print(f"{arg} is {exe}"); found = True; break
                    if IS_WINDOWS:
                        for ext in ('.exe', '.cmd', '.bat'):
                            if os.path.isfile(exe + ext):
                                print(f"{arg} is {exe}{ext}"); found = True; break
                    if found: break
                if not found: print(f"pybash: type: {arg}: not found", file=sys.stderr)
        return 0

    def cmd_test(self, args):
        return self._eval_test(args)

    def cmd_test_bracket(self, args):
        if args and args[-1] == ']': args = args[:-1]
        return self._eval_test(args)

    def _eval_test(self, args):
        if not args: return 1
        if args[0] == '(' and args[-1] == ')': return self._eval_test(args[1:-1])
        if args[0] == '!': return 1 if self._eval_test(args[1:]) == 0 else 0
        if '-a' in args:
            idx = args.index('-a')
            return 0 if (self._eval_test(args[:idx]) == 0 and self._eval_test(args[idx + 1:]) == 0) else 1
        if '-o' in args:
            idx = args.index('-o')
            return 0 if (self._eval_test(args[:idx]) == 0 or self._eval_test(args[idx + 1:]) == 0) else 1
        for op in ['==', '!=', '-eq', '-ne', '-lt', '-le', '-gt', '-ge', '=']:
            if op in args:
                idx = args.index(op)
                left = os.path.expanduser(args[idx - 1]) if idx > 0 else ''
                right = os.path.expanduser(args[idx + 1]) if idx + 1 < len(args) else ''
                if op in ('==', '='): return 0 if left == right else 1
                elif op == '!=': return 0 if left != right else 1
                elif op == '-eq':
                    try: return 0 if int(left) == int(right) else 1
                    except ValueError: return 1
                elif op == '-ne':
                    try: return 0 if int(left) != int(right) else 1
                    except ValueError: return 1
                elif op == '-lt':
                    try: return 0 if int(left) < int(right) else 1
                    except ValueError: return 1
                elif op == '-le':
                    try: return 0 if int(left) <= int(right) else 1
                    except ValueError: return 1
                elif op == '-gt':
                    try: return 0 if int(left) > int(right) else 1
                    except ValueError: return 1
                elif op == '-ge':
                    try: return 0 if int(left) >= int(right) else 1
                    except ValueError: return 1
        if len(args) == 2:
            op, arg = args
            arg = os.path.expanduser(arg)
            if op == '-f': return 0 if os.path.isfile(arg) else 1
            if op == '-d': return 0 if os.path.isdir(arg) else 1
            if op == '-e': return 0 if os.path.exists(arg) else 1
            if op == '-r': return 0 if os.path.exists(arg) and os.access(arg, os.R_OK) else 1
            if op == '-w': return 0 if os.path.exists(arg) and os.access(arg, os.W_OK) else 1
            if op == '-x': return 0 if os.path.exists(arg) and os.access(arg, os.X_OK) else 1
            if op == '-s': return 0 if os.path.exists(arg) and os.path.getsize(arg) > 0 else 1
            if op == '-z': return 0 if len(arg) == 0 else 1
            if op == '-n': return 0 if len(arg) > 0 else 1
            if op == '-L': return 0 if os.path.islink(arg) else 1
        if len(args) == 1: return 0 if args[0] else 1
        return 1

    def cmd_alias(self, args):
        if not args:
            for k, v in sorted(self.alias_map.items()): print(f"alias {k}='{v}'")
            return 0
        for arg in args:
            if '=' in arg:
                k, v = arg.split('=', 1)
                self.alias_map[k] = v.strip("'\"")
            else:
                if arg in self.alias_map: print(f"alias {arg}='{self.alias_map[arg]}'")
                else: print(f"pybash: alias: {arg}: not found", file=sys.stderr)
        self._save_aliases()
        return 0

    def cmd_unalias(self, args):
        ret = 0
        for arg in args:
            if arg in self.alias_map:
                del self.alias_map[arg]
            else:
                ret = 1
        self._save_aliases()
        return ret

    def cmd_history(self, args):
        try:
            if os.path.exists(self.state.history_file):
                with open(self.state.history_file, 'r', encoding='utf-8', errors='replace') as f:
                    for i, line in enumerate(f.readlines(), 1): print(f"  {i:>5}  {line.rstrip()}")
        except Exception as e: print(f"pybash: history: {e}", file=sys.stderr)
        return 0

    def cmd_read(self, args):
        prompt_str = ''; var = 'REPLY'; i = 0
        while i < len(args):
            if args[i] == '-p' and i + 1 < len(args): prompt_str = args[i + 1]; i += 2
            elif not args[i].startswith('-'): var = args[i]; i += 1
            else: i += 1
        try:
            if prompt_str: sys.stdout.write(prompt_str); sys.stdout.flush()
            self.state.vars[var] = input()
        except (EOFError, KeyboardInterrupt): self.state.vars[var] = ''
        return 0

    def cmd_declare(self, args):
        for arg in args:
            if '=' in arg:
                var, _, val = arg.partition('=')
                self.state[var.lstrip('-')] = val
        return 0

    def cmd_local(self, args):
        for arg in args:
            if '=' in arg:
                var, _, val = arg.partition('=')
                self.state.vars[var] = val
        return 0

    def cmd_return(self, args):
        code = int(args[0]) if args else 0
        self.state.last_return = code; return code

    def cmd_exit(self, args):
        code = int(args[0]) if args else 0
        self.state.running = False; sys.exit(code)

    def cmd_clear(self, args):
        os.system('cls' if IS_WINDOWS else 'clear'); return 0

    def cmd_help(self, args):
        if args:
            cmd = args[0]
            if cmd in self.cmds:
                handler = self.cmds[cmd]
                if hasattr(handler, '__self__'):
                    method_name = handler.__func__.__name__
                    method = getattr(self, method_name)
                    if method.__doc__:
                        print(method.__doc__)
                    else:
                        print(f"No detailed help for '{cmd}'. Try: {cmd} --help")
                else:
                    print(f"No detailed help for '{cmd}'. Try: {cmd} --help")
            else:
                print(f"Unknown command: {cmd}")
            return 0

        print("PyBash - Cross-platform Python Shell")
        print()
        print("Usage: <command> [arguments]")
        print()
        print("FILE OPERATIONS:")
        print("  ls [-laAhFrRtS]    List directory contents")
        print("  cat [-nEs]         Print file contents")
        print("  cp [-rfp]          Copy files and directories")
        print("  mv [-fv]           Move/rename files")
        print("  rm [-rfv]          Remove files and directories")
        print("  mkdir [-pv]        Create directories")
        print("  touch              Create files or update timestamps")
        print("  find [path] [opts] Search for files")
        print("  chmod              Change file permissions")
        print("  ln [-s]            Create links")
        print()
        print("TEXT PROCESSING:")
        print("  grep [-ivnwc]      Search text patterns")
        print("  sort [-rnuf]       Sort lines")
        print("  uniq [-cd]         Filter duplicates")
        print("  wc [-lwc]          Count lines/words/chars")
        print("  head [-n N]        First N lines")
        print("  tail [-n N] [-f]   Last N lines")
        print("  cut [-d -f]        Extract columns")
        print("  tr [-ds]           Translate characters")
        print("  sed                Stream editor")
        print("  awk                Pattern scanning")
        print()
        print("SYSTEM:")
        print("  date               Display date/time")
        print("  uname [-a]         System information")
        print("  whoami             Current user")
        print("  env / printenv     Environment variables")
        print("  export             Set environment variable")
        print("  which              Locate a command")
        print()
        print("SHELL CONTROL:")
        print("  cd [dir]           Change directory")
        print("  pwd                Print working directory")
        print("  echo [-ne]         Print arguments")
        print("  alias              Create aliases")
        print("  source/.           Execute script")
        print("  history            Command history")
        print("  exit               Exit shell")
        print()
        print("SCRIPTING:")
        print("  if/then/elif/else/fi   Conditional execution")
        print("  for/in/do/done        Iteration over list")
        print("  while/do/done         Conditional loop")
        print("  case/esac             Pattern matching")
        print("  name() { ... }        Function definition")
        print("  $(( expr ))           Arithmetic expansion")
        print("  $(cmd)                Command substitution")
        print()
        print("FEATURES:")
        print("  Pipes:        cmd1 | cmd2 | cmd3")
        print("  Redirects:    > file, >> file, < file, 2> file")
        print("  Logical:      cmd1 && cmd2, cmd1 || cmd2")
        print("  Variables:    VAR=value, $VAR, ${VAR}")
        print("  Tab completion: Bash-style (single/double Tab)")
        print()
        print("Run 'command --help' for detailed usage of any command.")
        return 0

    def cmd_exec(self, args):
        if not args: return 0
        return self._run_external(args)

    def cmd_eval(self, args):
        line = ' '.join(args)
        from pybash.shell import Shell
        shell = Shell.__new__(Shell)
        shell.state = self.state; shell.builtins = self
        from pybash.script import ScriptEngine
        shell.engine = ScriptEngine(self.state, shell)
        return shell.execute_line(line)

    def cmd_pushd(self, args):
        if args:
            ret = self.cmd_cd(args)
            if ret != 0: return ret
        self._dir_stack.append(os.getcwd()); print(os.getcwd()); return 0

    def cmd_popd(self, args):
        if self._dir_stack:
            target = self._dir_stack.pop()
            os.chdir(target); self.state.cwd = target
        else:
            print("pybash: popd: directory stack empty", file=sys.stderr); return 1
        return 0

    def cmd_dirs(self, args):
        for d in reversed(self._dir_stack): print(d)
        print(os.getcwd()); return 0

    def cmd_wait(self, args): return 0

    def cmd_kill(self, args):
        if not args: print("pybash: kill: usage: kill pid", file=sys.stderr); return 1
        for arg in args:
            if arg.startswith('-'): continue
            try: os.kill(int(arg), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, ValueError) as e:
                print(f"pybash: kill: ({arg}): {e}", file=sys.stderr)
        return 0

    def cmd_timeout(self, args):
        if len(args) < 2: print("pybash: timeout: missing operand", file=sys.stderr); return 1
        try:
            result = subprocess.run(args[1:], shell=IS_WINDOWS, timeout=float(args[0]))
            return result.returncode
        except subprocess.TimeoutExpired:
            print(f"pybash: timeout: '{' '.join(args[1:])}' still running"); return 124
        except Exception as e:
            print(f"pybash: timeout: {e}", file=sys.stderr); return 1

    def cmd_break(self, args):
        from pybash.builtins import BreakException
        raise BreakException()

    def cmd_continue(self, args):
        from pybash.builtins import ContinueException
        raise ContinueException()
