"""File operation commands: cd, pwd, ls, mkdir, rm, cp, mv, touch, find, chmod, ln, etc."""
import os
import sys
import re
import stat
import shutil
import fnmatch
from datetime import datetime

IS_WINDOWS = __import__('platform').system() == "Windows"


class FileCommands:
    """Mixin providing file-related builtins. Requires self.state, self._parse_flags, self._human_size, self._format_mode."""

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
