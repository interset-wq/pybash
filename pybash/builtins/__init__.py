"""
Built-in commands: all core commands implemented in pure Python for cross-platform use.
"""
import os
import sys
import stat
import subprocess
import platform
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

from pybash.builtins.file import FileCommands
from pybash.builtins.text import TextCommands
from pybash.builtins.system import SystemCommands
from pybash.builtins.shell import ShellControlCommands


class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


class BuiltinCommands(FileCommands, TextCommands, SystemCommands, ShellControlCommands):
    def __init__(self, state):
        self.state = state
        self.shell = None
        self._aliases = {
            'dir': 'ls',
            'll': 'ls -l',
            'la': 'ls -a',
            'quit': 'exit',
            '.': 'source',
            '[': 'test',
        }
        self.cmds = {
            'cd': self.cmd_cd,
            'pwd': self.cmd_pwd,
            'echo': self.cmd_echo,
            'printf': self.cmd_printf,
            'cat': self.cmd_cat,
            'ls': self.cmd_ls,
            'dir': self.cmd_ls,
            'll': lambda a: self.cmd_ls(['-l'] + a),
            'la': lambda a: self.cmd_ls(['-a'] + a),
            'mkdir': self.cmd_mkdir,
            'rmdir': self.cmd_rmdir,
            'cp': self.cmd_cp,
            'mv': self.cmd_mv,
            'rm': self.cmd_rm,
            'touch': self.cmd_touch,
            'find': self.cmd_find,
            'grep': self.cmd_grep,
            'wc': self.cmd_wc,
            'head': self.cmd_head,
            'tail': self.cmd_tail,
            'sort': self.cmd_sort,
            'uniq': self.cmd_uniq,
            'cut': self.cmd_cut,
            'tr': self.cmd_tr,
            'sed': self.cmd_sed,
            'awk': self.cmd_awk,
            'diff': self.cmd_diff,
            'xargs': self.cmd_xargs,
            'tee': self.cmd_tee,
            'which': self.cmd_which,
            'file': self.cmd_file,
            'stat': self.cmd_stat,
            'du': self.cmd_du,
            'df': self.cmd_df,
            'chmod': self.cmd_chmod,
            'ln': self.cmd_ln,
            'readlink': self.cmd_readlink,
            'basename': self.cmd_basename,
            'dirname': self.cmd_dirname,
            'realpath': self.cmd_realpath,
            'mktemp': self.cmd_mktemp,
            'seq': self.cmd_seq,
            'sleep': self.cmd_sleep,
            'date': self.cmd_date,
            'uname': self.cmd_uname,
            'hostname': self.cmd_hostname,
            'whoami': self.cmd_whoami,
            'id': self.cmd_id,
            'env': self.cmd_env,
            'printenv': self.cmd_printenv,
            'export': self.cmd_export,
            'unset': self.cmd_unset,
            'set': self.cmd_set,
            'source': self.cmd_source,
            '.': self.cmd_source,
            'type': self.cmd_type,
            'test': self.cmd_test,
            '[': self.cmd_test_bracket,
            'alias': self.cmd_alias,
            'unalias': self.cmd_unalias,
            'history': self.cmd_history,
            'read': self.cmd_read,
            'declare': self.cmd_declare,
            'local': self.cmd_local,
            'return': self.cmd_return,
            'exit': self.cmd_exit,
            'quit': self.cmd_exit,
            'clear': self.cmd_clear,
            'help': self.cmd_help,
            'exec': self.cmd_exec,
            'eval': self.cmd_eval,
            'pushd': self.cmd_pushd,
            'popd': self.cmd_popd,
            'dirs': self.cmd_dirs,
            'wait': self.cmd_wait,
            'kill': self.cmd_kill,
            'command': self.cmd_command,
            'builtin': self.cmd_builtin,
            'md5sum': self.cmd_md5sum,
            'sha256sum': self.cmd_sha256sum,
            'base64': self.cmd_base64,
            'strings': self.cmd_strings,
            'od': self.cmd_od,
            'nl': self.cmd_nl,
            'column': self.cmd_column,
            'paste': self.cmd_paste,
            'split': self.cmd_split,
            'comm': self.cmd_comm,
            'join': self.cmd_join,
            'fold': self.cmd_fold,
            'fmt': self.cmd_fmt,
            'pr': self.cmd_pr,
            'timeout': self.cmd_timeout,
            'true': lambda a: 0,
            'false': lambda a: 1,
            'hash': lambda a: 0,
            'break': self.cmd_break,
            'continue': self.cmd_continue,
        }
        self.alias_map = {}
        self._dir_stack = []
        self._hash_table = {}
        self._jobs = []
        self._load_aliases()

    def _load_aliases(self):
        alias_file = self.state.alias_file
        if os.path.exists(alias_file):
            try:
                with open(alias_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            k, v = line.split('=', 1)
                            self.alias_map[k] = v.strip("'\"")
            except Exception:
                pass

    def _save_aliases(self):
        alias_file = self.state.alias_file
        try:
            with open(alias_file, 'w', encoding='utf-8') as f:
                for k, v in sorted(self.alias_map.items()):
                    f.write(f"{k}='{v}'\n")
        except Exception:
            pass

    def _parse_flags(self, args):
        flags = set()
        positional = []
        for arg in args:
            if arg == '--help':
                return 'HELP', []
            if arg.startswith('-') and len(arg) > 1 and not arg[1:].isdigit():
                flags.update(arg[1:])
            else:
                positional.append(arg)
        return flags, positional

    def _human_size(self, size):
        for unit in ('B', 'K', 'M', 'G', 'T'):
            if abs(size) < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}P"

    def _format_mode(self, mode):
        s = ''
        if stat.S_ISDIR(mode): s += 'd'
        elif stat.S_ISLNK(mode): s += 'l'
        elif stat.S_ISFIFO(mode): s += 'p'
        elif stat.S_ISBLK(mode): s += 'b'
        elif stat.S_ISCHR(mode): s += 'c'
        elif stat.S_ISSOCK(mode): s += 's'
        else: s += '-'
        for who in ('USR', 'GRP', 'OTH'):
            s += 'r' if mode & getattr(stat, f'S_IR{who}') else '-'
            s += 'w' if mode & getattr(stat, f'S_IW{who}') else '-'
            s += 'x' if mode & getattr(stat, f'S_IX{who}') else '-'
        return s

    def cmd_which(self, args):
        for arg in args:
            if arg in self.cmds:
                print(f"{arg}: shell built-in command")
            else:
                path_dirs = os.path.expandvars(os.environ.get("PATH", "")).split(os.pathsep)
                found = False
                for d in path_dirs:
                    if not d:
                        continue
                    exe = os.path.join(d, arg)
                    if os.path.isfile(exe) and os.access(exe, os.X_OK):
                        print(exe); found = True; break
                    if IS_WINDOWS:
                        for ext in ('.exe', '.cmd', '.bat', '.com'):
                            if os.path.isfile(exe + ext):
                                print(exe + ext); found = True; break
                    if found: break
                if not found:
                    print(f"pybash: which: no {arg} in ({os.environ.get('PATH', '')})", file=sys.stderr)
        return 0

    def cmd_file(self, args):
        for filepath in args:
            filepath = os.path.expanduser(filepath)
            if not os.path.exists(filepath):
                print(f"{filepath}: cannot open (No such file or directory)"); continue
            if os.path.islink(filepath): print(f"{filepath}: symbolic link to {os.readlink(filepath)}")
            elif os.path.isdir(filepath): print(f"{filepath}: directory")
            elif os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                if size == 0: print(f"{filepath}: empty")
                else:
                    try:
                        with open(filepath, 'rb') as f: header = f.read(16)
                        if header.startswith(b'\x89PNG'): print(f"{filepath}: PNG image data")
                        elif header.startswith(b'\xff\xd8'): print(f"{filepath}: JPEG image data")
                        elif header.startswith(b'%PDF'): print(f"{filepath}: PDF document")
                        elif header.startswith(b'PK'): print(f"{filepath}: Zip archive data")
                        else:
                            try: header.decode('utf-8'); print(f"{filepath}: ASCII text")
                            except UnicodeDecodeError: print(f"{filepath}: data")
                    except Exception: print(f"{filepath}: cannot determine type")
        return 0

    def _run_external(self, args):
        try:
            creation_flags = 0
            if IS_WINDOWS:
                creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            result = subprocess.run(args, shell=False, cwd=os.getcwd(), creationflags=creation_flags)
            self.state.last_return = result.returncode
            return result.returncode
        except FileNotFoundError:
            print(f"pybash: {args[0]}: command not found", file=sys.stderr)
            self.state.last_return = 127; return 127
        except PermissionError:
            print(f"pybash: {args[0]}: permission denied", file=sys.stderr)
            self.state.last_return = 126; return 126
        except Exception as e:
            print(f"pybash: {args[0]}: {e}", file=sys.stderr)
            self.state.last_return = 1; return 1
