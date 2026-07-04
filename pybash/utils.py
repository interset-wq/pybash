"""
Shared utilities: tokenizer, variable expansion, glob expansion, trie.
"""
import os
import re
import glob
import platform

IS_WINDOWS = platform.system() == "Windows"

SPECIAL_VARS = {'?', '$', '!', '#', '@', '*', '0'}


class TrieNode:
    __slots__ = ('children', 'is_end', 'value')

    def __init__(self):
        self.children = {}
        self.is_end = False
        self.value = None


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, key, value=None):
        node = self.root
        for ch in key:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True
        node.value = value if value is not None else key

    def search(self, key):
        node = self.root
        for ch in key:
            if ch not in node.children:
                return None
            node = node.children[ch]
        if node.is_end:
            return node.value
        return None

    def starts_with(self, prefix):
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]
        results = []
        path = list(prefix)
        self._collect(node, path, results)
        return results

    def _collect(self, node, path, results):
        if node.is_end:
            results.append(''.join(path))
        for ch, child in sorted(node.children.items()):
            path.append(ch)
            self._collect(child, path, results)
            path.pop()

    def delete(self, key):
        self._delete(self.root, key, 0)

    def _delete(self, node, key, depth):
        if depth == len(key):
            node.is_end = False
            node.value = None
            return len(node.children) == 0
        ch = key[depth]
        if ch not in node.children:
            return False
        should_delete = self._delete(node.children[ch], key, depth + 1)
        if should_delete:
            del node.children[ch]
            return not node.is_end and len(node.children) == 0
        return False

    def clear(self):
        self.root = TrieNode()

    def __len__(self):
        return self._count(self.root)

    def _count(self, node):
        count = 1 if node.is_end else 0
        for child in node.children.values():
            count += self._count(child)
        return count


class Tokenizer:
    @staticmethod
    def expand_variables(text, state):
        def replacer(m):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if name in SPECIAL_VARS:
                if name == '?': return str(state.last_return)
                elif name == '$': return str(os.getpid())
                elif name == '!': return ''
                elif name == '#': return str(len(state.positional))
                elif name == '@': return ' '.join(state.positional)
                elif name == '*': return ' '.join(state.positional)
                elif name == '0': return 'pybash'
            if name.isdigit() and int(name) > 0:
                idx = int(name) - 1
                if idx < len(state.positional):
                    return state.positional[idx]
                return ''
            if name in state.vars:
                return state.vars[name]
            return os.environ.get(name, '')
        return re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)|\$(\d+)|\$([?$#!@*])', replacer, text)

    @staticmethod
    def expand_arithmetic(text, state):
        def replace_arith(m):
            expr = m.group(1)
            expr = Tokenizer.expand_variables(expr, state)
            def replace_var(m2):
                name = m2.group(0)
                return str(state.vars.get(name, '0'))
            expr = re.sub(r'\b([A-Za-z_]\w*)\b', replace_var, expr)
            try:
                result = eval(expr, {"__builtins__": {}}, {})
                return str(int(result) if isinstance(result, (int, float)) else 0)
            except Exception:
                return '0'
        return re.sub(r'\$\(\(([^)]+)\)\)', replace_arith, text)

    @staticmethod
    def expand_command_sub(text, state):
        def replace_cmd(m):
            cmd = m.group(1)
            cmd = Tokenizer.expand_variables(cmd, state)
            cmd = Tokenizer.expand_arithmetic(cmd, state)
            try:
                import subprocess
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.stdout.strip()
            except Exception:
                return ''
        return re.sub(r'\$\(([^)]+)\)', replace_cmd, text)

    @staticmethod
    def expand_tilde(text):
        home = os.path.expanduser("~")
        if text.startswith("~/"):
            return os.path.join(home, text[2:])
        elif text == "~":
            return home
        return text

    @staticmethod
    def expand_glob(text):
        if not any(c in text for c in ('*', '?', '[')):
            return [text]
        text = Tokenizer.expand_tilde(text)
        matches = glob.glob(text)
        return matches if matches else [text]

    @staticmethod
    def tokenize(line, state):
        line = Tokenizer.expand_variables(line, state)
        line = Tokenizer.expand_arithmetic(line, state)
        line = Tokenizer.expand_command_sub(line, state)
        tokens = []
        i = 0
        current = ""
        in_sq = False
        in_dq = False
        escape = False

        while i < len(line):
            ch = line[i]
            if escape:
                current += ch
                escape = False
                i += 1
                continue
            if ch == '\\' and not in_sq and not IS_WINDOWS:
                escape = True
                i += 1
                continue
            if ch == "'" and not in_dq:
                in_sq = not in_sq
                i += 1
                continue
            if ch == '"' and not in_sq:
                in_dq = not in_dq
                i += 1
                continue
            if in_sq or in_dq:
                current += ch
                i += 1
                continue
            if ch in (' ', '\t'):
                if current:
                    tokens.append(current)
                    current = ""
                i += 1
                continue
            current += ch
            i += 1

        if current:
            tokens.append(current)
        return Tokenizer._split_redirects(tokens)

    @staticmethod
    def _split_redirects(tokens):
        import re
        result = []
        for tok in tokens:
            m = re.match(r'^(\d+)(>>?)', tok)
            if m:
                result.append(m.group(1) + m.group(2))
                rest = tok[len(m.group(0)):]
                if rest:
                    result.append(rest)
                continue
            m = re.match(r'^(>>?)', tok)
            if m:
                result.append(m.group(1))
                rest = tok[len(m.group(0)):]
                if rest:
                    result.append(rest)
                continue
            result.append(tok)
        return result

    @staticmethod
    def split_pipes(line):
        parts = []
        current = ""
        in_sq = False
        in_dq = False
        escape = False

        for ch in line:
            if escape:
                current += ch
                escape = False
                continue
            if ch == '\\' and not in_sq and not IS_WINDOWS:
                escape = True
                continue
            if ch == "'" and not in_dq:
                in_sq = not in_sq
                current += ch
                continue
            if ch == '"' and not in_sq:
                in_dq = not in_dq
                current += ch
                continue
            if not in_sq and not in_dq and ch == '|':
                parts.append(current)
                current = ""
                continue
            current += ch

        if current:
            parts.append(current)
        return parts
