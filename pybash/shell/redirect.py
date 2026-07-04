"""Redirect handler for file descriptor redirections (>, >>, <, 2>, etc.)."""
import os
import sys
import re
import platform

IS_WINDOWS = platform.system() == "Windows"


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
            if IS_WINDOWS and filename in ('/dev/null', 'NUL', 'nul'):
                filename = 'NUL'
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
