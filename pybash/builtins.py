"""
Built-in commands: all core commands implemented in pure Python for cross-platform use.
"""
import os
import sys
import re
import glob
import shutil
import stat
import time
import platform
import fnmatch
import hashlib
from pathlib import Path
from datetime import datetime

IS_WINDOWS = platform.system() == "Windows"


class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


class BuiltinCommands:
    def __init__(self, state):
        self.state = state
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

    def cmd_break(self, args):
        raise BreakException()

    def cmd_continue(self, args):
        raise ContinueException()

    def cmd_cd(self, args):
        if '--help' in args:
            print("Usage: cd [DIR]")
            print("Change the current directory to DIR.")
            print("  cd       Go to home directory")
            print("  cd -     Go to previous directory")
            print("  cd ..    Go to parent directory")
            return 0
        if not args or args[0] == '~':
            target = os.path.expanduser('~')
        elif args[0] == '-':
            target = self._dir_stack[-1] if self._dir_stack else os.getcwd()
            print(target)
        elif args[0] == '.':
            target = os.getcwd()
        elif args[0] == '..':
            target = os.path.dirname(os.getcwd())
        else:
            target = os.path.expanduser(args[0])
            target = os.path.expandvars(target)
        try:
            self._dir_stack.append(os.getcwd())
            os.chdir(target)
            self.state.cwd = os.getcwd()
            return 0
        except FileNotFoundError:
            print(f"pybash: cd: {target}: No such file or directory", file=sys.stderr)
            return 1
        except NotADirectoryError:
            print(f"pybash: cd: {target}: Not a directory", file=sys.stderr)
            return 1
        except PermissionError:
            print(f"pybash: cd: {target}: Permission denied", file=sys.stderr)
            return 1

    def cmd_pwd(self, args):
        print(os.getcwd())
        return 0

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

    def cmd_cat(self, args):
        flags, files = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: cat [-nEETs] [FILE...]")
            print("Concatenate files and print on the standard output.")
            print("  -n     Number output lines")
            print("  -E     Display $ at end of each line")
            print("  -T     Display TAB as ^I")
            print("  -s     Squeeze multiple blank lines")
            return 0
        show_line_numbers = 'n' in flags
        show_ends = 'E' in flags
        show_tabs = 'T' in flags
        show_nonblank = 'b' in flags
        squeeze = 's' in flags

        if not files:
            try:
                for line in sys.stdin:
                    out = line.rstrip('\n\r')
                    if show_tabs: out = out.replace('\t', '^I')
                    if show_ends: out += '$'
                    print(out)
            except (EOFError, KeyboardInterrupt):
                pass
            return 0

        line_num = 1
        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    prev_blank = False
                    for line in f:
                        is_blank = line.strip() == ''
                        if squeeze and is_blank and prev_blank:
                            continue
                        prev_blank = is_blank
                        out = line.rstrip('\n\r')
                        if show_tabs: out = out.replace('\t', '^I')
                        if show_ends: out += '$'
                        if show_line_numbers or (show_nonblank and not is_blank):
                            out = f"{line_num:>6}\t{out}"
                            line_num += 1
                        elif show_nonblank and is_blank:
                            out = f"\t{out}"
                        print(out)
            except FileNotFoundError:
                print(f"pybash: cat: {filepath}: No such file or directory", file=sys.stderr)
                return 1
            except IsADirectoryError:
                print(f"pybash: cat: {filepath}: Is a directory", file=sys.stderr)
                return 1
        return 0

    def cmd_ls(self, args):
        if '--help' in args:
            print("Usage: ls [-laAhFrRtSr] [--help] [FILE...]")
            print("List directory contents.")
            print()
            print("  -l         Long listing format")
            print("  -a         Show hidden files (starting with .)")
            print("  -A         Show hidden files (except . and ..)")
            print("  -h         Human-readable sizes")
            print("  -F         Classify entries (append / * @)")
            print("  -r         Reverse sort order")
            print("  -R         List subdirectories recursively")
            print("  -t         Sort by modification time")
            print("  -S         Sort by file size")
            print("  --color    Colorize output")
            return 0
        flags, paths = self._parse_flags(args)
        long_fmt = 'l' in flags
        show_all = 'a' in flags or 'A' in flags
        classify = 'F' in flags
        human = 'h' in flags
        recursive = 'R' in flags
        color = 'color' in flags or 'c' in flags
        reverse = 'r' in flags
        sort_time = 't' in flags
        sort_size = 'S' in flags

        if not paths:
            paths = ['.']

        all_entries = []
        for path in paths:
            if not os.path.exists(path):
                print(f"pybash: ls: cannot access '{path}': No such file or directory", file=sys.stderr)
                continue
            if os.path.isfile(path) and not os.path.isdir(path):
                all_entries.append(('', [os.path.basename(path)]))
                continue
            entries = []
            try:
                for entry in os.listdir(path):
                    if not show_all and entry.startswith('.'):
                        continue
                    entries.append(entry)
            except PermissionError:
                print(f"pybash: ls: cannot access '{path}': Permission denied", file=sys.stderr)
                continue

            if sort_time:
                entries.sort(key=lambda e: os.path.getmtime(os.path.join(path, e)), reverse=True)
            elif sort_size:
                entries.sort(key=lambda e: os.path.getsize(os.path.join(path, e)), reverse=True)
            else:
                entries.sort()
            if reverse:
                entries.reverse()

            if len(paths) > 1:
                print(f"\n{path}:")
            all_entries.append((path, entries))

            if recursive:
                for entry in entries:
                    full = os.path.join(path, entry)
                    if os.path.isdir(full) and not os.path.islink(full):
                        sub_entries = []
                        try:
                            for se in os.listdir(full):
                                if not show_all and se.startswith('.'):
                                    continue
                                sub_entries.append(se)
                        except PermissionError:
                            pass
                        all_entries.append((full, sub_entries))

        use_color = color or sys.stdout.isatty()
        for path, entries in all_entries:
            if not entries:
                continue
            if long_fmt:
                for entry in entries:
                    full = os.path.join(path, entry) if path else entry
                    try:
                        st = os.lstat(full)
                        mode_str = self._format_mode(st.st_mode)
                        nlink = st.st_nlink
                        size = self._human_size(st.st_size) if human else st.st_size
                        mtime = datetime.fromtimestamp(st.st_mtime).strftime('%b %d %H:%M')
                        name = entry
                        if classify:
                            if os.path.isdir(full) and not os.path.islink(full): name += '/'
                            elif os.access(full, os.X_OK): name += '*'
                            elif os.path.islink(full): name += '@'
                        if use_color:
                            if os.path.isdir(full) and not os.path.islink(full):
                                name = f"\033[1;34m{name}\033[0m"
                            elif os.access(full, os.X_OK):
                                name = f"\033[1;32m{name}\033[0m"
                            elif os.path.islink(full):
                                name = f"\033[1;36m{name}\033[0m"
                        print(f"{mode_str} {nlink:>3} {size:>6} {mtime} {name}")
                    except (OSError, FileNotFoundError) as e:
                        print(f"pybash: ls: {e}", file=sys.stderr)
            else:
                names = []
                for entry in entries:
                    full = os.path.join(path, entry) if path else entry
                    name = entry
                    if classify:
                        if os.path.isdir(full) and not os.path.islink(full): name += '/'
                        elif os.access(full, os.X_OK): name += '*'
                        elif os.path.islink(full): name += '@'
                    if use_color:
                        if os.path.isdir(full) and not os.path.islink(full):
                            name = f"\033[1;34m{name}\033[0m"
                        elif os.access(full, os.X_OK):
                            name = f"\033[1;32m{name}\033[0m"
                        elif os.path.islink(full):
                            name = f"\033[1;36m{name}\033[0m"
                    names.append(name)
                print('  '.join(names))
        return 0

    def cmd_mkdir(self, args):
        flags, dirs = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: mkdir [-pv] DIR...")
            print("Create directories.")
            print("  -p     Create parent directories as needed")
            print("  -v     Verbose output")
            return 0
        make_parents = 'p' in flags
        make_verbose = 'v' in flags
        for d in dirs:
            if d.startswith('-m') and len(d) > 2:
                continue
            try:
                if make_parents:
                    os.makedirs(d, exist_ok=True)
                else:
                    os.mkdir(d)
                if make_verbose:
                    print(f"mkdir: created directory '{d}'")
            except FileExistsError:
                print(f"pybash: mkdir: cannot create directory '{d}': File exists", file=sys.stderr)
                return 1
            except PermissionError:
                print(f"pybash: mkdir: cannot create directory '{d}': Permission denied", file=sys.stderr)
                return 1
        return 0

    def cmd_rmdir(self, args):
        for d in args:
            try:
                os.rmdir(d)
            except FileNotFoundError:
                print(f"pybash: rmdir: failed to remove '{d}': No such file or directory", file=sys.stderr)
                return 1
            except OSError as e:
                print(f"pybash: rmdir: failed to remove '{d}': {e}", file=sys.stderr)
                return 1
        return 0

    def cmd_cp(self, args):
        flags, paths = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: cp [-rfp] SOURCE DEST")
            print("Copy files and directories.")
            print("  -r     Copy directories recursively")
            print("  -f     Force overwrite")
            print("  -p     Preserve permissions")
            return 0
        recursive = 'r' in flags or 'R' in flags
        force = 'f' in flags
        preserve = 'p' in flags
        verbose = 'v' in flags
        if len(paths) < 2:
            print("pybash: cp: missing destination operand", file=sys.stderr)
            return 1
        dest = paths[-1]
        sources = paths[:-1]
        for src in sources:
            src = os.path.expanduser(src)
            if not os.path.exists(src):
                print(f"pybash: cp: cannot stat '{src}': No such file or directory", file=sys.stderr)
                return 1
            if os.path.isdir(src) and not recursive:
                print(f"pybash: cp: -r not specified; omitting directory '{src}'", file=sys.stderr)
                return 1
            try:
                if os.path.isdir(src):
                    dest_dir = os.path.join(dest, os.path.basename(src)) if os.path.isdir(dest) else dest
                    os.makedirs(dest_dir, exist_ok=True)
                    for item in os.listdir(src):
                        s = os.path.join(src, item)
                        d = os.path.join(dest_dir, item)
                        if os.path.isfile(s):
                            shutil.copy2(s, d) if preserve else shutil.copy(s, d)
                            if verbose: print(f"'{s}' -> '{d}'")
                        elif os.path.isdir(s):
                            self.cmd_cp(['-rv', s, d])
                else:
                    if os.path.isdir(dest):
                        d = os.path.join(dest, os.path.basename(src))
                    else:
                        d = dest
                    shutil.copy2(src, d) if preserve else shutil.copy(src, d)
                    if verbose: print(f"'{src}' -> '{d}'")
            except Exception as e:
                print(f"pybash: cp: {e}", file=sys.stderr)
                return 1
        return 0

    def cmd_mv(self, args):
        flags, paths = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: mv [-fv] SOURCE DEST")
            print("Move (rename) files.")
            print("  -f     Force overwrite")
            print("  -v     Verbose output")
            return 0
        force = 'f' in flags
        verbose = 'v' in flags
        if len(paths) < 2:
            print("pybash: mv: missing destination operand", file=sys.stderr)
            return 1
        dest = paths[-1]
        sources = paths[:-1]
        for src in sources:
            src = os.path.expanduser(src)
            if not os.path.exists(src):
                print(f"pybash: mv: cannot stat '{src}': No such file or directory", file=sys.stderr)
                return 1
            try:
                if os.path.isdir(dest):
                    d = os.path.join(dest, os.path.basename(src))
                else:
                    d = dest
                shutil.move(src, d)
                if verbose: print(f"'{src}' -> '{d}'")
            except Exception as e:
                print(f"pybash: mv: {e}", file=sys.stderr)
                return 1
        return 0

    def cmd_rm(self, args):
        flags, paths = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: rm [-rfv] FILE...")
            print("Remove files or directories.")
            print("  -r     Remove directories recursively")
            print("  -f     Force removal without prompt")
            print("  -v     Verbose output")
            return 0
        recursive = 'r' in flags or 'R' in flags
        force = 'f' in flags
        verbose = 'v' in flags
        if not paths:
            if not force:
                print("pybash: rm: missing operand", file=sys.stderr)
            return 1 if not force else 0
        for path in paths:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                if not force:
                    print(f"pybash: rm: cannot remove '{path}': No such file or directory", file=sys.stderr)
                    return 1
                continue
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                    if verbose: print(f"removed '{path}'")
                elif os.path.isdir(path):
                    if not recursive:
                        print(f"pybash: rm: cannot remove '{path}': Is a directory", file=sys.stderr)
                        return 1
                    shutil.rmtree(path)
                    if verbose: print(f"removed directory '{path}'")
            except PermissionError:
                print(f"pybash: rm: cannot remove '{path}': Permission denied", file=sys.stderr)
                return 1
        return 0

    def cmd_touch(self, args):
        flags, files = self._parse_flags(args)
        no_create = 'c' in flags
        for filepath in files:
            try:
                if os.path.exists(filepath):
                    os.utime(filepath)
                elif not no_create:
                    with open(filepath, 'w') as f:
                        pass
            except Exception as e:
                print(f"pybash: touch: {filepath}: {e}", file=sys.stderr)
                return 1
        return 0

    def cmd_find(self, args):
        if '--help' in args:
            print("Usage: find [PATH...] [-name PATTERN] [-type f|d] [-exec CMD {}]")
            print("Search for files in a directory hierarchy.")
            print("  -name PATTERN   Match filename pattern")
            print("  -type f|d       Filter by type (file or directory)")
            print("  -maxdepth N     Maximum search depth")
            print("  -empty          Find empty files")
            print("  -exec CMD {}    Execute command on found files")
            print("  -print0         Null-separated output")
            return 0
        name = None
        type_filter = None
        max_depth = None
        min_depth = 0
        exec_cmd = None
        print0 = False
        follow = False
        inames = None
        regex = None
        newer_file = None
        empty = False
        paths = []
        i = 0
        while i < len(args):
            if args[i] == '-name' and i + 1 < len(args):
                name = args[i + 1]; i += 2
            elif args[i] == '-iname' and i + 1 < len(args):
                inames = args[i + 1]; i += 2
            elif args[i] == '-type' and i + 1 < len(args):
                type_filter = args[i + 1]; i += 2
            elif args[i] == '-maxdepth' and i + 1 < len(args):
                max_depth = int(args[i + 1]); i += 2
            elif args[i] == '-mindepth' and i + 1 < len(args):
                min_depth = int(args[i + 1]); i += 2
            elif args[i] == '-exec' and i + 1 < len(args):
                j = i + 1
                exec_parts = []
                while j < len(args) and args[j] != ';':
                    exec_parts.append(args[j]); j += 1
                exec_cmd = exec_parts; i = j + 1
            elif args[i] == '-print0':
                print0 = True; i += 1
            elif args[i] == '-L':
                follow = True; i += 1
            elif args[i] == '-regex' and i + 1 < len(args):
                regex = args[i + 1]; i += 2
            elif args[i] == '-newer' and i + 1 < len(args):
                newer_file = args[i + 1]; i += 2
            elif args[i] == '-empty':
                empty = True; i += 1
            elif not args[i].startswith('-'):
                paths.append(args[i]); i += 1
            else:
                i += 1
        if not paths:
            paths = ['.']
        results = []
        sep = '\0' if print0 else '\n'
        for search_path in paths:
            try:
                for root, dirs, files in os.walk(search_path, followlinks=follow):
                    depth = root.replace(search_path, '').count(os.sep)
                    if max_depth is not None and depth > max_depth:
                        dirs.clear(); continue
                    if depth < min_depth:
                        continue
                    entries = files + dirs
                    for entry in entries:
                        full = os.path.join(root, entry)
                        if name and not fnmatch.fnmatch(entry, name): continue
                        if inames and not fnmatch.fnmatch(entry.lower(), inames.lower()): continue
                        if regex and not re.search(regex, full): continue
                        if type_filter:
                            if type_filter == 'f' and not os.path.isfile(full): continue
                            if type_filter == 'd' and not os.path.isdir(full): continue
                            if type_filter == 'l' and not os.path.islink(full): continue
                        if empty:
                            if os.path.isfile(full) and os.path.getsize(full) == 0: pass
                            elif os.path.isdir(full) and not os.listdir(full): pass
                            else: continue
                        if exec_cmd:
                            cmd = [a.replace('{}', full) for a in exec_cmd]
                            try: subprocess.run(cmd)
                            except Exception: pass
                        else:
                            results.append(full)
            except PermissionError:
                print(f"pybash: find: '{search_path}': Permission denied", file=sys.stderr)
        for r in results:
            print(r, end=sep)
        if print0:
            print()
        return 0

    def cmd_grep(self, args):
        flags, paths = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: grep [-ivnwlcsE] PATTERN [FILE...]")
            print("Search for PATTERN in each FILE.")
            print("  -i     Ignore case")
            print("  -v     Invert match (select non-matching lines)")
            print("  -n     Prefix each line with line number")
            print("  -w     Match whole words only")
            print("  -l     Print only filenames of matching files")
            print("  -c     Print only match count")
            print("  -s     Suppress error messages")
            return 0
        ignore_case = 'i' in flags
        invert = 'v' in flags
        count_only = 'c' in flags
        line_numbers = 'n' in flags
        whole_line = 'w' in flags
        show_files = 'l' in flags
        color = 'color' in flags
        pattern = None
        for arg in args:
            if not arg.startswith('-'):
                pattern = arg
                break
        if pattern is None:
            print("pybash: grep: missing pattern", file=sys.stderr)
            return 1
        flags_re = re.IGNORECASE if ignore_case else 0
        try:
            compiled = re.compile(pattern, flags_re)
        except re.error as e:
            print(f"pybash: grep: {e}", file=sys.stderr)
            return 1
        file_patterns = [a for a in args if not a.startswith('-') and a != pattern]
        if not file_patterns:
            file_patterns = ['-']
        use_color = color or sys.stdout.isatty()
        match_count = 0
        def do_grep(filepath, lines):
            nonlocal match_count
            count = 0
            for i, line in enumerate(lines, 1):
                stripped = line.rstrip('\n\r')
                if whole_line:
                    m = compiled.fullmatch(stripped)
                else:
                    m = compiled.search(stripped)
                if invert:
                    m = not m
                if m:
                    count += 1
                    if show_files:
                        print(filepath)
                        break
                    prefix = ''
                    if len(file_patterns) > 1 or (len(file_patterns) == 1 and file_patterns[0] == '-'):
                        prefix = f"{filepath}:"
                    if line_numbers:
                        prefix += f"{i}:"
                    out = stripped
                    if use_color and not invert:
                        out = compiled.sub(lambda m: f"\033[1;31m{m.group()}\033[0m", stripped)
                    print(f"{prefix}{out}")
            if count_only:
                print(f"{filepath}:{count}" if len(file_patterns) > 1 else str(count))
            if count > 0:
                match_count += count
        for fp in file_patterns:
            if fp == '-':
                do_grep('(standard input)', sys.stdin.readlines())
            else:
                fp = os.path.expanduser(fp)
                try:
                    if os.path.isdir(fp): continue
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        do_grep(fp, f.readlines())
                except FileNotFoundError:
                    print(f"pybash: grep: {fp}: No such file or directory", file=sys.stderr)
                    return 1
                except PermissionError:
                    print(f"pybash: grep: {fp}: Permission denied", file=sys.stderr)
                    return 1
        return 0 if match_count > 0 else 1

    def cmd_wc(self, args):
        flags, files = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: wc [-lwc] [FILE...]")
            print("Print line, word, and byte counts for each file.")
            print("  -l     Print line count")
            print("  -w     Print word count")
            print("  -c     Print byte count")
            return 0
        show_lines = 'l' in flags
        show_words = 'w' in flags
        show_chars = 'c' in flags or 'm' in flags
        if not (show_lines or show_words or show_chars):
            show_lines = show_words = show_chars = True
        def count_file(filepath, f):
            lines = words = chars = 0
            for line in f:
                lines += 1; words += len(line.split()); chars += len(line)
            return lines, words, chars
        if not files:
            l, w, c = count_file('-', sys.stdin)
            print(f"{l:>8}{w:>8}{c:>8}")
            return 0
        total_l = total_w = total_c = 0
        for filepath in files:
            filepath = os.path.expanduser(filepath)
            try:
                if os.path.isdir(filepath):
                    print(f"pybash: wc: {filepath}: Is a directory", file=sys.stderr)
                    continue
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    l, w, c = count_file(filepath, f)
                parts = []
                if show_lines: parts.append(f"{l:>8}")
                if show_words: parts.append(f"{w:>8}")
                if show_chars: parts.append(f"{c:>8}")
                print(f"{''.join(parts)} {filepath}")
                total_l += l; total_w += w; total_c += c
            except FileNotFoundError:
                print(f"pybash: wc: {filepath}: No such file or directory", file=sys.stderr)
                return 1
        if len(files) > 1:
            parts = []
            if show_lines: parts.append(f"{total_l:>8}")
            if show_words: parts.append(f"{total_w:>8}")
            if show_chars: parts.append(f"{total_c:>8}")
            print(f"{''.join(parts)} total")
        return 0

    def cmd_head(self, args):
        if '--help' in args:
            print("Usage: head [-n N] [FILE...]")
            print("Output the first N lines of each file (default 10).")
            print("  -n N   Print first N lines")
            return 0
        flags, files = self._parse_flags(args)
        n = 10
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                n = int(args[i + 1]); i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n = int(args[i][1:]); i += 1
            else:
                i += 1
        if not files:
            count = 0
            for line in sys.stdin:
                if count >= n: break
                print(line.rstrip('\n\r')); count += 1
            return 0
        for filepath in files:
            filepath = os.path.expanduser(filepath)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    for i, line in enumerate(f):
                        if i >= n: break
                        print(line.rstrip('\n\r'))
            except FileNotFoundError:
                print(f"pybash: head: {filepath}: No such file or directory", file=sys.stderr)
                return 1
        return 0

    def cmd_tail(self, args):
        if '--help' in args:
            print("Usage: tail [-n N] [-f] [FILE...]")
            print("Output the last N lines of each file (default 10).")
            print("  -n N   Print last N lines")
            print("  -f     Follow file growth")
            return 0
        flags, files = self._parse_flags(args)
        n = 10
        follow = False
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                n = int(args[i + 1]); i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n = int(args[i][1:]); i += 1
            elif args[i] == '-f':
                follow = True; i += 1
            else:
                i += 1
        if not files:
            lines = sys.stdin.readlines()
            for line in lines[-n:]: print(line.rstrip('\n\r'))
            return 0
        for filepath in files:
            filepath = os.path.expanduser(filepath)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                    for line in lines[-n:]: print(line.rstrip('\n\r'))
                    if follow:
                        while True:
                            line = f.readline()
                            if line: print(line.rstrip('\n\r'))
                            else: time.sleep(0.1)
            except KeyboardInterrupt:
                break
            except FileNotFoundError:
                print(f"pybash: tail: {filepath}: No such file or directory", file=sys.stderr)
                return 1
        return 0

    def cmd_sort(self, args):
        flags, files = self._parse_flags(args)
        if flags == 'HELP':
            print("Usage: sort [-rnuf] [FILE...]")
            print("Sort lines of text files.")
            print("  -r     Reverse sort order")
            print("  -n     Sort numerically")
            print("  -u     Remove duplicates")
            print("  -f     Fold lowercase to uppercase")
            return 0
        reverse = 'r' in flags
        numeric = 'n' in flags
        unique = 'u' in flags
        ignore_case = 'f' in flags or 'i' in flags
        lines = []
        if not files:
            lines = sys.stdin.readlines()
        else:
            for fp in files:
                fp = os.path.expanduser(fp)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        lines.extend(f.readlines())
                except FileNotFoundError:
                    print(f"pybash: sort: {fp}: No such file or directory", file=sys.stderr)
                    return 1
        def sort_key(line):
            l = line.rstrip('\n\r')
            if numeric:
                try: return (0, float(l))
                except ValueError: return (1, l)
            return (0, l.lower() if ignore_case else l)
        lines.sort(key=sort_key, reverse=reverse)
        if unique:
            seen = set()
            filtered = []
            for line in lines:
                k = line.rstrip('\n\r')
                if k not in seen: seen.add(k); filtered.append(line)
            lines = filtered
        for line in lines: print(line.rstrip('\n\r'))
        return 0

    def cmd_uniq(self, args):
        flags, files = self._parse_flags(args)
        count = 'c' in flags
        ignore_case = 'i' in flags
        lines = []
        if not files:
            lines = sys.stdin.readlines()
        else:
            for fp in files:
                fp = os.path.expanduser(fp)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        lines.extend(f.readlines())
                except FileNotFoundError:
                    print(f"pybash: uniq: {fp}: No such file or directory", file=sys.stderr)
                    return 1
        prev = None; cnt = 0
        for line in lines:
            l = line.rstrip('\n\r')
            cmp = l.lower() if ignore_case else l
            if cmp == prev:
                cnt += 1
            else:
                if prev is not None:
                    if count: print(f"{cnt:>7} {prev}")
                    else: print(prev)
                prev = cmp; cnt = 1
        if prev is not None:
            if count: print(f"{cnt:>7} {prev}")
            else: print(prev)
        return 0

    def cmd_cut(self, args):
        flags, files = self._parse_flags(args)
        delimiter = '\t'; fields = None; characters = None
        i = 0
        while i < len(args):
            if args[i] == '-d' and i + 1 < len(args):
                delimiter = args[i + 1].replace('\\t', '\t').replace('\\n', '\n'); i += 2
            elif args[i] == '-f' and i + 1 < len(args):
                fields = self._parse_range(args[i + 1]); i += 2
            elif args[i] == '-c' and i + 1 < len(args):
                characters = self._parse_range(args[i + 1]); i += 2
            else: i += 1
        lines = []
        if not files:
            lines = sys.stdin.readlines()
        else:
            for fp in files:
                fp = os.path.expanduser(fp)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        lines.extend(f.readlines())
                except FileNotFoundError:
                    print(f"pybash: cut: {fp}: No such file or directory", file=sys.stderr)
                    return 1
        for line in lines:
            l = line.rstrip('\n\r')
            if fields is not None:
                parts = l.split(delimiter)
                selected = [parts[f - 1] for f in fields if 1 <= f <= len(parts)]
                print(delimiter.join(selected))
            elif characters is not None:
                print(''.join(l[c - 1] for c in characters if 1 <= c <= len(l)))
            else:
                print(l)
        return 0

    def _parse_range(self, s):
        result = set()
        for part in s.split(','):
            if '-' in part:
                start, end = part.split('-', 1)
                start = int(start) if start else 1
                end = int(end) if end else 99999
                result.update(range(start, end + 1))
            else:
                result.add(int(part))
        return sorted(result)

    def cmd_tr(self, args):
        if len(args) < 2:
            print("pybash: tr: missing operand", file=sys.stderr)
            return 1
        delete = 'd' in args
        args = [a for a in args if a != '-d']
        if delete:
            data = sys.stdin.read()
            for ch in args[0]: data = data.replace(ch, '')
            print(data, end=''); return 0
        if len(args) < 2:
            print("pybash: tr: missing second operand", file=sys.stderr)
            return 1
        table = str.maketrans(args[0], args[1])
        print(sys.stdin.read().translate(table), end=''); return 0

    def cmd_sed(self, args):
        if not args: print("pybash: sed: no expression", file=sys.stderr); return 1
        expression = args[0]; files = args[1:]; lines = []
        if not files:
            lines = sys.stdin.readlines()
        else:
            for fp in files:
                fp = os.path.expanduser(fp)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        lines.extend(f.readlines())
                except FileNotFoundError:
                    print(f"pybash: sed: {fp}: No such file or directory", file=sys.stderr)
                    return 1
        if expression.startswith('s/'):
            parts = expression[2:].split('/')
            if len(parts) >= 2:
                pattern, replacement = parts[0], parts[1]
                flags = parts[2] if len(parts) > 2 else ''
                global_replace = 'g' in flags
                for line in lines:
                    try:
                        print(re.sub(pattern, replacement, line.rstrip('\n\r'),
                                     count=0 if global_replace else 1))
                    except re.error:
                        print(line.rstrip('\n\r'))
        elif expression.startswith('d'):
            pass
        elif expression.startswith('p'):
            for line in lines: print(line.rstrip('\n\r'))
        else:
            for line in lines: print(line.rstrip('\n\r'))
        return 0

    def cmd_awk(self, args):
        if not args: print("pybash: awk: missing pattern", file=sys.stderr); return 1
        pattern = args[0]; files = args[1:]; lines = []
        if not files:
            lines = sys.stdin.readlines()
        else:
            for fp in files:
                fp = os.path.expanduser(fp)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        lines.extend(f.readlines())
                except FileNotFoundError:
                    print(f"pybash: awk: {fp}: No such file or directory", file=sys.stderr)
                    return 1
        for line in lines:
            fields = line.rstrip('\n\r').split()
            if not fields: continue
            try:
                if pattern == '{print $0}': print(line.rstrip('\n\r'))
                elif pattern.startswith('{print $') and pattern.endswith('}'):
                    idx = int(pattern[8:-1])
                    if idx <= len(fields): print(fields[idx - 1])
                elif pattern == '{print NF}': print(len(fields))
                elif pattern == '{print NR}': print(lines.index(line) + 1)
                elif pattern == '{print $1}': print(fields[0])
                else: print(line.rstrip('\n\r'))
            except (IndexError, ValueError): pass
        return 0

    def cmd_diff(self, args):
        flags, files = self._parse_flags(args)
        if len(files) < 2: print("pybash: diff: missing operand", file=sys.stderr); return 1
        try:
            with open(files[0], 'r', encoding='utf-8', errors='replace') as f: lines1 = f.readlines()
            with open(files[1], 'r', encoding='utf-8', errors='replace') as f: lines2 = f.readlines()
        except FileNotFoundError as e:
            print(f"pybash: diff: {e}", file=sys.stderr); return 1
        import difflib
        diff = list(difflib.unified_diff(lines1, lines2, fromfile=files[0], tofile=files[1], lineterm=''))
        for line in diff: print(line.rstrip('\n\r'))
        return 1 if diff else 0

    def cmd_xargs(self, args):
        cmd = args if args else ['echo']
        items = sys.stdin.read().split()
        if not items: return 0
        try:
            result = subprocess.run(cmd + items, shell=IS_WINDOWS)
            return result.returncode
        except Exception as e:
            print(f"pybash: xargs: {e}", file=sys.stderr); return 1

    def cmd_tee(self, args):
        flags, files = self._parse_flags(args)
        append = 'a' in flags
        lines = sys.stdin.readlines()
        for line in lines: print(line.rstrip('\n\r'))
        for fp in files:
            fp = os.path.expanduser(fp)
            try:
                with open(fp, 'a' if append else 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            except Exception as e:
                print(f"pybash: tee: {fp}: {e}", file=sys.stderr); return 1
        return 0

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

    def cmd_stat(self, args):
        targets = [a for a in args if not a.startswith('-')]
        if not targets: print("pybash: stat: missing operand", file=sys.stderr); return 1
        for filepath in targets:
            filepath = os.path.expanduser(filepath)
            try:
                st = os.stat(filepath)
                print(f"  File: {filepath}")
                print(f"  Size: {st.st_size}")
                print(f"Access: ({oct(stat.S_IMODE(st.st_mode))})")
                print(f"Access: {datetime.fromtimestamp(st.st_atime).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Modify: {datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Change: {datetime.fromtimestamp(st.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}")
            except FileNotFoundError:
                print(f"pybash: stat: cannot stat '{filepath}': No such file or directory", file=sys.stderr)
                return 1
        return 0

    def cmd_du(self, args):
        flags, paths = self._parse_flags(args)
        human = 'h' in flags
        summarize = 's' in flags
        if not paths: paths = ['.']
        total = 0
        for path in paths:
            path = os.path.expanduser(path)
            try:
                for root, dirs, files in os.walk(path):
                    size = sum(os.path.getsize(os.path.join(root, f)) for f in files)
                    total += size
                    if not summarize:
                        h = self._human_size(size) if human else size
                        print(f"{h}\t{root}")
            except (PermissionError, FileNotFoundError):
                print(f"pybash: du: cannot access '{path}': Permission denied", file=sys.stderr)
        if summarize:
            h = self._human_size(total) if human else total
            print(f"{h}\t{path}")
        return 0

    def cmd_df(self, args):
        flags, _ = self._parse_flags(args)
        human = 'h' in flags
        print(f"{'Filesystem':>20} {'Size':>10} {'Used':>10} {'Avail':>10} {'Use%':>8} {'Mounted on'}")
        try:
            usage = shutil.disk_usage('/')
            size, used, free = usage.total, usage.used, usage.free
            pct = int(used / size * 100) if size > 0 else 0
            s = self._human_size(size) if human else str(size)
            u = self._human_size(used) if human else str(used)
            f = self._human_size(free) if human else str(free)
            print(f"{'/':>20} {s:>10} {u:>10} {f:>10} {pct:>7}% /")
        except Exception: pass
        return 0

    def cmd_chmod(self, args):
        if len(args) < 2: print("pybash: chmod: missing operand", file=sys.stderr); return 1
        try: mode = int(args[0], 8)
        except ValueError: print(f"pybash: chmod: invalid mode: {args[0]}", file=sys.stderr); return 1
        for fp in args[1:]:
            fp = os.path.expanduser(fp)
            try: os.chmod(fp, mode)
            except FileNotFoundError:
                print(f"pybash: chmod: cannot access '{fp}': No such file or directory", file=sys.stderr); return 1
            except PermissionError:
                print(f"pybash: chmod: changing permissions of '{fp}': Permission denied", file=sys.stderr); return 1
        return 0

    def cmd_ln(self, args):
        flags, paths = self._parse_flags(args)
        symbolic = 's' in flags; force = 'f' in flags
        if len(paths) < 2: print("pybash: ln: missing target", file=sys.stderr); return 1
        target, link_name = paths[0], paths[1]
        try:
            if os.path.isdir(link_name): link_name = os.path.join(link_name, os.path.basename(target))
            if os.path.exists(link_name) and not force:
                print("pybash: ln: failed to create symbolic link: File exists", file=sys.stderr); return 1
            if os.path.exists(link_name): os.remove(link_name)
            if symbolic: os.symlink(target, link_name)
            else: os.link(target, link_name)
        except OSError as e:
            print(f"pybash: ln: {e}", file=sys.stderr); return 1
        return 0

    def cmd_readlink(self, args):
        flags, files = self._parse_flags(args)
        for fp in files:
            fp = os.path.expanduser(fp)
            try:
                if 'f' in flags: print(os.path.realpath(fp))
                else: print(os.readlink(fp))
            except OSError:
                print(f"pybash: readlink: {fp}: Not a symbolic link", file=sys.stderr); return 1
        return 0

    def cmd_basename(self, args):
        if not args: print("pybash: basename: missing operand", file=sys.stderr); return 1
        name = os.path.basename(args[0])
        if len(args) > 1 and name.endswith(args[1]): name = name[:-len(args[1])]
        print(name); return 0

    def cmd_dirname(self, args):
        if not args: print("pybash: dirname: missing operand", file=sys.stderr); return 1
        print(os.path.dirname(args[0]) or '.'); return 0

    def cmd_realpath(self, args):
        for fp in args: print(os.path.realpath(os.path.expanduser(fp)))
        return 0

    def cmd_mktemp(self, args):
        import tempfile
        try:
            fd, path = tempfile.mkstemp(); os.close(fd); print(path)
        except Exception as e:
            print(f"pybash: mktemp: {e}", file=sys.stderr); return 1
        return 0

    def cmd_seq(self, args):
        if not args: print("pybash: seq: missing operand", file=sys.stderr); return 1
        if len(args) == 1: start, end, step = 1, int(args[0]), 1
        elif len(args) == 2: start, end, step = int(args[0]), int(args[1]), 1
        else: start, step, end = int(args[0]), int(args[1]), int(args[2])
        if step == 0: print("pybash: seq: zero step", file=sys.stderr); return 1
        if step > 0:
            while start <= end: print(start); start += step
        else:
            while start >= end: print(start); start += step
        return 0

    def cmd_sleep(self, args):
        if not args: return 0
        try: time.sleep(float(args[0]))
        except ValueError: print(f"pybash: sleep: invalid time interval '{args[0]}'", file=sys.stderr); return 1
        return 0

    def cmd_date(self, args):
        fmt = '+%Y-%m-%d %H:%M:%S'
        if args and args[0].startswith('+'): fmt = args[0][1:]
        print(datetime.now().strftime(fmt)); return 0

    def cmd_uname(self, args):
        flags, _ = self._parse_flags(args)
        system = platform.system()
        if not flags or 'a' in flags:
            print(f"{system} hostname 1.0.0 #1 SMP {system} {platform.machine()}")
        else:
            results = []
            if 's' in flags: results.append(system)
            if 'n' in flags: results.append(platform.node())
            if 'r' in flags: results.append(platform.release())
            if 'v' in flags: results.append(platform.version())
            if 'm' in flags: results.append(platform.machine())
            print(' '.join(results) if results else system)
        return 0

    def cmd_hostname(self, args): print(platform.node()); return 0

    def cmd_whoami(self, args):
        if IS_WINDOWS: print(os.environ.get('USERNAME', os.environ.get('USER', 'user')))
        else:
            import pwd
            try: print(pwd.getpwuid(os.getuid()).pw_name)
            except KeyError: print(os.environ.get('USER', 'user'))
        return 0

    def cmd_id(self, args):
        if IS_WINDOWS:
            user = os.environ.get('USERNAME', os.environ.get('USER', 'user'))
            print(f"uid=1000({user}) gid=1000({user}) groups=1000({user})")
        else:
            import pwd
            try:
                pw = pwd.getpwuid(os.getuid())
                print(f"uid={pw.pw_uid}({pw.pw_name}) gid={pw.pw_gid}")
            except KeyError: print(f"uid={os.getuid()} gid={os.getgid()}")
        return 0

    def cmd_env(self, args):
        if not args:
            for k, v in sorted(os.environ.items()): print(f"{k}={v}")
            return 0
        return self._run_external(args)

    def cmd_printenv(self, args):
        if not args:
            for k, v in sorted(os.environ.items()): print(f"{k}={v}")
        else:
            for arg in args:
                val = os.environ.get(arg)
                if val is not None: print(val)
        return 0

    def cmd_export(self, args):
        if not args:
            for k, v in sorted(os.environ.items()): print(f"declare -x {k}=\"{v}\"")
            return 0
        for arg in args:
            if '=' in arg:
                var, _, val = arg.partition('=')
                os.environ[var] = val; self.state.vars[var] = val
            else:
                val = self.state.vars.get(arg, os.environ.get(arg, ''))
                os.environ[arg] = val
        return 0

    def cmd_unset(self, args):
        for arg in args:
            self.state.vars.pop(arg, None); os.environ.pop(arg, None)
        return 0

    def cmd_set(self, args):
        if not args:
            for k, v in sorted(self.state.vars.items()): print(f"{k}={v}")
            return 0
        return 0

    def cmd_source(self, args):
        if not args: print("pybash: source: filename required", file=sys.stderr); return 1
        from pybash.script import ScriptEngine
        engine = ScriptEngine(self.state, None)
        engine.execute_file(args[0])
        return self.state.last_return

    def cmd_type(self, args):
        for arg in args:
            if arg in self.cmds: print(f"{arg} is a shell builtin")
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
        for arg in args:
            if arg in self.alias_map: del self.alias_map[arg]
            else: print(f"pybash: unalias: {arg}: not found", file=sys.stderr)
        self._save_aliases()
        return 0

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

    def cmd_command(self, args):
        if not args: return 0
        if args[0] == '-v': return self.cmd_type(args[1:])
        return self._run_external(args)

    def cmd_builtin(self, args):
        if args and args[0] in self.cmds: return self.cmds[args[0]](args[1:])
        return 1

    def cmd_strings(self, args):
        min_len = 4; i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args): min_len = int(args[i + 1]); i += 2
            else: i += 1
        if i < len(args):
            try:
                with open(args[i], 'rb') as f: data = f.read()
            except FileNotFoundError:
                print(f"pybash: strings: {args[i]}: No such file or directory", file=sys.stderr); return 1
        else: data = sys.stdin.buffer.read()
        current = ''
        for b in data:
            if 32 <= b < 127: current += chr(b)
            else:
                if len(current) >= min_len: print(current)
                current = ''
        if len(current) >= min_len: print(current)
        return 0

    def cmd_od(self, args):
        if not args: data = sys.stdin.buffer.read()
        else:
            try:
                with open(args[0], 'rb') as f: data = f.read()
            except FileNotFoundError:
                print(f"pybash: od: {args[0]}: No such file or directory", file=sys.stderr); return 1
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"{i:07o}  {hex_str:<48}  {ascii_str}")
        return 0

    def cmd_nl(self, args):
        start = 1
        for line in sys.stdin: print(f"{start:>6}\t{line.rstrip()}"); start += 1
        return 0

    def cmd_column(self, args):
        lines = sys.stdin.readlines()
        if not lines: return 0
        cols = max(len(l.split()) for l in lines)
        widths = [0] * cols; rows = []
        for line in lines:
            parts = line.rstrip('\n\r').split(); rows.append(parts)
            for i, p in enumerate(parts):
                if i < cols: widths[i] = max(widths[i], len(p))
        for row in rows:
            cells = [row[i].ljust(widths[i]) if i < len(row) else ' ' * widths[i] for i in range(cols)]
            print('  '.join(cells))
        return 0

    def cmd_paste(self, args):
        if len(args) < 2:
            for line in sys.stdin: print(line.rstrip('\n\r'))
            return 0
        files = []
        for fp in args:
            try:
                with open(fp, 'r') as f: files.append(f.readlines())
            except FileNotFoundError: files.append([])
        for row in zip(*files):
            print('\t'.join(l.rstrip('\n\r') for l in row))
        return 0

    def cmd_split(self, args):
        prefix = 'x'; lines_per_file = 1000; i = 0
        while i < len(args):
            if args[i] == '-l' and i + 1 < len(args): lines_per_file = int(args[i + 1]); i += 2
            elif not args[i].startswith('-'): prefix = args[i]; i += 1
            else: i += 1
        lines = sys.stdin.readlines(); idx = 0; chunk_num = 0
        while idx < len(lines):
            with open(f"{prefix}{chunk_num:02d}", 'w') as f:
                f.writelines(lines[idx:idx + lines_per_file])
            idx += lines_per_file; chunk_num += 1
        return 0

    def cmd_comm(self, args):
        if len(args) < 2: print("pybash: comm: missing operand", file=sys.stderr); return 1
        try:
            with open(args[0], 'r') as f1: lines1 = set(l.strip() for l in f1)
            with open(args[1], 'r') as f2: lines2 = set(l.strip() for l in f2)
            for line in sorted(lines1 | lines2):
                in1 = line in lines1; in2 = line in lines2
                if in1 and not in2: print(line)
                elif not in1 and in2: print(f"\t{line}")
                else: print(f"\t\t{line}")
        except FileNotFoundError as e:
            print(f"pybash: comm: {e}", file=sys.stderr); return 1
        return 0

    def cmd_join(self, args):
        if len(args) < 2: print("pybash: join: missing operand", file=sys.stderr); return 1
        try:
            with open(args[0], 'r') as f1, open(args[1], 'r') as f2:
                for l1, l2 in zip(f1, f2): print(f"{l1.rstrip()} {l2.rstrip()}")
        except FileNotFoundError as e:
            print(f"pybash: join: {e}", file=sys.stderr); return 1
        return 0

    def cmd_fold(self, args):
        width = 80; i = 0
        while i < len(args):
            if args[i] == '-w' and i + 1 < len(args): width = int(args[i + 1]); i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit(): width = int(args[i][1:]); i += 1
            else: i += 1
        for line in sys.stdin:
            l = line.rstrip('\n\r')
            while len(l) > width: print(l[:width]); l = l[width:]
            print(l)
        return 0

    def cmd_fmt(self, args):
        for line in sys.stdin: print(line.rstrip('\n\r')[:75])
        return 0

    def cmd_pr(self, args):
        for line in sys.stdin: print(line.rstrip('\n\r').center(72))
        return 0

    def cmd_base64(self, args):
        import base64
        decode = '-d' in args or '--decode' in args
        files = [a for a in args if not a.startswith('-')]
        if not files: data = sys.stdin.buffer.read()
        else:
            try:
                with open(files[0], 'rb') as f: data = f.read()
            except FileNotFoundError:
                print(f"pybash: base64: {files[0]}: No such file or directory", file=sys.stderr); return 1
        if decode: sys.stdout.buffer.write(base64.b64decode(data))
        else:
            result = base64.b64encode(data).decode('ascii')
            print('\n'.join(result[i:i+76] for i in range(0, len(result), 76)))
        return 0

    def cmd_md5sum(self, args):
        for fp in args:
            try:
                h = hashlib.md5()
                with open(fp, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''): h.update(chunk)
                print(f"{h.hexdigest()}  {fp}")
            except Exception as e:
                print(f"pybash: md5sum: {fp}: {e}", file=sys.stderr)
        return 0

    def cmd_sha256sum(self, args):
        for fp in args:
            try:
                h = hashlib.sha256()
                with open(fp, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''): h.update(chunk)
                print(f"{h.hexdigest()}  {fp}")
            except Exception as e:
                print(f"pybash: sha256sum: {fp}: {e}", file=sys.stderr)
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
