"""Text processing commands: cat, grep, sort, head, tail, wc, sed, awk, etc."""
import os
import sys
import re
import subprocess

IS_WINDOWS = __import__('platform').system() == "Windows"


class TextCommands:
    """Mixin providing text-processing builtins."""

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
        n = 10
        filtered = []
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                n = int(args[i + 1]); i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n = int(args[i][1:]); i += 1
            else:
                filtered.append(args[i]); i += 1
        files = filtered
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
        n = 10
        follow = False
        filtered = []
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                n = int(args[i + 1]); i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n = int(args[i][1:]); i += 1
            elif args[i] == '-f':
                follow = True; i += 1
            else:
                filtered.append(args[i]); i += 1
        files = filtered
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
