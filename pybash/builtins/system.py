"""System info commands: date, uname, whoami, env, export, sleep, seq, etc."""
import os
import sys
import time
import platform
import subprocess
import hashlib
from datetime import datetime

IS_WINDOWS = platform.system() == "Windows"


class SystemCommands:
    """Mixin providing system-related builtins."""

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

    def cmd_command(self, args):
        if not args: return 0
        if args[0] == '-v': return self.cmd_type(args[1:])
        return self._run_external(args)

    def cmd_builtin(self, args):
        if args and args[0] in self.cmds: return self.cmds[args[0]](args[1:])
        return 1

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
