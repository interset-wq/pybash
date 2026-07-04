"""
Bash scripting engine: variables, if/else, for, while, case, functions, arithmetic.
"""
import os
import sys
import re
import fnmatch
from pybash.utils import Tokenizer


class ScriptEngine:
    def __init__(self, state, shell):
        self.state = state
        self.shell = shell

    def execute_file(self, filepath):
        filepath = os.path.expanduser(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            return self.execute_block(lines)
        except FileNotFoundError:
            print(f"pybash: {filepath}: No such file or directory", file=sys.stderr)
            self.state.last_return = 127
            return 127

    def execute_block(self, lines):
        i = 0
        last_ret = 0
        while i < len(lines):
            line = lines[i].rstrip('\n\r')
            stripped = line.strip()
            i += 1

            if not stripped or stripped.startswith('#'):
                continue

            if stripped.startswith('if '):
                i, last_ret = self._handle_if(lines, i - 1)
                continue

            if stripped.startswith('while '):
                i, last_ret = self._handle_while(lines, i - 1)
                continue

            if stripped.startswith('until '):
                i, last_ret = self._handle_until(lines, i - 1)
                continue

            if stripped.startswith('for '):
                i, last_ret = self._handle_for(lines, i - 1)
                continue

            if stripped.startswith('select '):
                i, last_ret = self._handle_select(lines, i - 1)
                continue

            if stripped.startswith('case '):
                i, last_ret = self._handle_case(lines, i - 1)
                continue

            if re.match(r'^function\s+', stripped) or re.match(r'^[A-Za-z_]\w*\s*\(\s*\)\s*\{', stripped):
                i = self._handle_function(lines, i - 1)
                continue

            if stripped in ('then', 'do', 'else', 'elif', 'fi', 'done', 'esac', ';;'):
                continue

            parts = self._split_semicolons(stripped)
            if len(parts) > 1:
                for p in parts:
                    p = p.strip()
                    if not p:
                        continue
                    if re.match(r'^(if|for|while|until|case|function|select)\b', p):
                        last_ret = self.execute_block([p])
                    elif re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', p):
                        self._handle_var_assign(p)
                    elif p.startswith('(('):
                        last_ret = self._handle_arithmetic(p)
                    elif p.startswith('local ') or p.startswith('export ') or p.startswith('declare '):
                        self._handle_var_assign(p)
                    elif self.shell:
                        last_ret = self.shell.execute_line(p)
                    else:
                        self._execute_line_fallback(p)
                continue

            if stripped.startswith('local ') or stripped.startswith('export ') or stripped.startswith('declare '):
                self._handle_var_assign(stripped)
                continue

            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', stripped) and not stripped.startswith(('echo', 'return', 'exit', 'test', '[')):
                self._handle_var_assign(stripped)
                continue

            if stripped.startswith('(('):
                last_ret = self._handle_arithmetic(stripped)
                continue

            if self.shell:
                last_ret = self.shell.execute_line(stripped)
            else:
                self._execute_line_fallback(stripped)

        self.state.last_return = last_ret
        return last_ret

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

    def _split_body_statements(self, body_str):
        if not body_str:
            return []
        parts = self._split_semicolons(body_str)
        result = []
        for p in parts:
            p = p.strip()
            if p:
                result.append(p)
        return result if result else [body_str]

    def _execute_line_fallback(self, line):
        try:
            result = os.popen(line).read()
            if result:
                print(result, end='')
        except Exception:
            pass

    def _clean_body(self, body):
        cleaned = []
        for line in body:
            line = line.strip()
            if not line:
                continue
            if line.endswith(';'):
                line = line[:-1].strip()
            if line:
                cleaned.append(line)
        return cleaned if cleaned else ['']

    def _handle_function(self, lines, start):
        line = lines[start].strip()
        if line.startswith('function '):
            rest = line[9:]
            if '{' in rest:
                name = rest[:rest.index('{')].strip().rstrip('(').rstrip(')')
                body = [rest[rest.index('{') + 1:].strip()]
                if '}' in body[0]:
                    body[0] = body[0][:body[0].index('}')].strip()
                    self.state.functions[name] = self._clean_body(body)
                    return start + 1
                j = start + 1
                while j < len(lines):
                    l = lines[j].strip()
                    if l == '}':
                        break
                    body.append(l)
                    j += 1
                self.state.functions[name] = self._clean_body(body)
                return j + 1
        elif '()' in line:
            name = line[:line.index('(')].strip()
            rest_after_paren = line[line.index(')') + 1:].strip()
            if '{' in rest_after_paren:
                body_start = rest_after_paren[rest_after_paren.index('{') + 1:].strip()
                body = [body_start]
                if '}' in body[0]:
                    body[0] = body[0][:body[0].index('}')].strip()
                    self.state.functions[name] = self._clean_body(body)
                    return start + 1
                j = start + 1
                while j < len(lines):
                    l = lines[j].strip()
                    if l == '}':
                        break
                    body.append(l)
                    j += 1
                self.state.functions[name] = self._clean_body(body)
                return j + 1
            j = start + 1
            while j < len(lines) and lines[j].strip() in ('{', ''):
                j += 1
            body = []
            while j < len(lines):
                l = lines[j].strip()
                if l == '}':
                    break
                body.append(l)
                j += 1
            self.state.functions[name] = body
            return j + 1
        return start + 1

    def _handle_if(self, lines, start):
        line = lines[start].strip()
        condition_line = line[3:].strip()

        if condition_line.endswith('then'):
            condition_line = condition_line[:-4].strip()

        if condition_line.endswith(';'):
            condition_line = condition_line[:-1].strip()

        is_oneliner = len(lines) == 1 and 'then' in line and 'fi' in line

        if is_oneliner:
            full = line
            if 'then' in full:
                parts = re.split(r'\b(then|else|elif|fi)\b', full)
            else:
                parts = re.split(r'\b(else|elif|fi)\b', full)

            result = 0
            depth = 0
            cond = None
            cond_met = False
            i = 0
            while i < len(parts):
                p = parts[i].strip()
                if i == 0:
                    cond = p[3:].strip() if p.startswith('if ') else p
                    if cond.endswith(';'):
                        cond = cond[:-1].strip()
                    i += 1
                    continue
                if p == 'then':
                    i += 1
                    if i < len(parts):
                        body = parts[i].strip()
                        if body.endswith(';'):
                            body = body[:-1].strip()
                        if not cond_met and cond and self._evaluate_condition(cond) == 0:
                            cond_met = True
                            result = self.execute_block([body])
                        cond = None
                    i += 1
                    continue
                if p == 'elif':
                    i += 1
                    if i < len(parts):
                        cond = parts[i].strip()
                    i += 1
                    continue
                if p == 'else':
                    i += 1
                    if i < len(parts):
                        body = parts[i].strip()
                        if body.endswith(';'):
                            body = body[:-1].strip()
                        if not cond_met:
                            result = self.execute_block([body])
                    i += 1
                    continue
                if p == 'fi':
                    break
                i += 1
            return start + 1, result

        j = start + 1
        if line.rstrip().endswith('then'):
            pass
        else:
            while j < len(lines) and lines[j].strip() in ('then', ''):
                j += 1

        then_lines = []
        else_lines = []
        elif_conditions = []
        elif_bodies = []
        in_else = False
        depth = 1

        while j < len(lines):
            l = lines[j].strip()
            if re.match(r'^if\b', l):
                depth += 1
            elif l == 'fi':
                depth -= 1
                if depth == 0:
                    break
            elif l == 'else' and depth == 1:
                in_else = True
                j += 1
                continue
            elif l.startswith('elif ') and depth == 1:
                elif_cond = l[5:].strip()
                if elif_cond.endswith('then'):
                    elif_cond = elif_cond[:-4].strip()
                elif_conditions.append(elif_cond)
                j += 1
                if lines[j - 1].rstrip().endswith('then'):
                    pass
                else:
                    while j < len(lines) and lines[j].strip() == 'then':
                        j += 1
                elif_body = []
                while j < len(lines):
                    l2 = lines[j].strip()
                    if l2 in ('else', 'elif', 'fi') and depth == 1:
                        break
                    elif_body.append(lines[j])
                    j += 1
                elif_bodies.append(elif_body)
                continue

            if in_else:
                else_lines.append(lines[j])
            elif not elif_conditions:
                then_lines.append(lines[j])
            j += 1

        result = 0
        ret = self._evaluate_condition(condition_line)
        if ret == 0:
            result = self.execute_block(then_lines)
        else:
            handled = False
            for idx, ec in enumerate(elif_conditions):
                ret2 = self._evaluate_condition(ec)
                if ret2 == 0:
                    result = self.execute_block(elif_bodies[idx])
                    handled = True
                    break
            if not handled:
                result = self.execute_block(else_lines)

        return j + 1, result

    def _handle_while(self, lines, start):
        line = lines[start].strip()
        condition_line = line[6:].strip()

        if ';' in condition_line:
            parts = condition_line.split(';', 1)
            condition_line = parts[0].strip()
            rest = parts[1].strip()
            if rest and rest != 'do':
                if rest.startswith('do'):
                    rest = rest[2:].strip()
                body_str = rest
                if body_str.endswith('done'):
                    body_str = body_str[:-4].strip()
                if body_str.endswith(';'):
                    body_str = body_str[:-1].strip()
                body_lines = self._split_body_statements(body_str)
                last_ret = 0
                max_iter = 100000
                count = 0
                while count < max_iter:
                    ret = self._evaluate_condition(condition_line)
                    if ret != 0:
                        break
                    last_ret = self.execute_block(body_lines)
                    count += 1
                return start + 1, last_ret

        j = start + 1
        while j < len(lines) and lines[j].strip() in ('do', ''):
            j += 1

        body_lines = []
        while j < len(lines):
            l = lines[j].strip()
            if l == 'done':
                break
            body_lines.append(lines[j])
            j += 1

        last_ret = 0
        max_iter = 100000
        count = 0
        while count < max_iter:
            ret = self._evaluate_condition(condition_line)
            if ret != 0:
                break
            last_ret = self.execute_block(body_lines)
            count += 1

        return j + 1, last_ret

    def _handle_until(self, lines, start):
        condition_line = lines[start].strip()[6:].strip()

        j = start + 1
        while j < len(lines) and lines[j].strip() in ('do', ''):
            j += 1

        body_lines = []
        while j < len(lines):
            l = lines[j].strip()
            if l == 'done':
                break
            body_lines.append(lines[j])
            j += 1

        last_ret = 0
        max_iter = 100000
        count = 0
        while count < max_iter:
            ret = self._evaluate_condition(condition_line)
            if ret == 0:
                break
            last_ret = self.execute_block(body_lines)
            count += 1

        return j + 1, last_ret

    def _handle_for(self, lines, start):
        line = lines[start].strip()

        match = re.match(r'for\s+([A-Za-z_]\w*)\s+in\s+(.+)', line)
        if match:
            var_name = match.group(1)
            items_str = match.group(2).strip()

            if ';' in items_str:
                parts = items_str.split(';', 1)
                items_str = parts[0].strip()
                rest = parts[1].strip()
                if rest and rest != 'do':
                    if rest.startswith('do'):
                        rest = rest[2:].strip()
                    items = self._expand_items(items_str)
                    body_str = rest
                    if body_str.endswith('done'):
                        body_str = body_str[:-4].strip()
                    if body_str.endswith(';'):
                        body_str = body_str[:-1].strip()
                    body_lines = self._split_body_statements(body_str)
                    last_ret = 0
                    for item in items:
                        self.state.vars[var_name] = item
                        last_ret = self.execute_block(body_lines)
                    return start + 1, last_ret

            items = self._expand_items(items_str)

            j = start + 1
            while j < len(lines) and lines[j].strip() in ('do', ''):
                j += 1
            body_lines = []
            while j < len(lines):
                l = lines[j].strip()
                if l == 'done':
                    break
                body_lines.append(lines[j])
                j += 1

            last_ret = 0
            for item in items:
                self.state.vars[var_name] = item
                last_ret = self.execute_block(body_lines)
            return j + 1, last_ret

        match = re.match(r'for\s*\(\s*([^;]+)\s*;\s*([^;]+)\s*;\s*([^)]+)\s*\)', line)
        if match:
            init = match.group(1).strip()
            cond = match.group(2).strip()
            incr = match.group(3).strip()

            self._handle_var_assign(init)

            j = start + 1
            while j < len(lines) and lines[j].strip() in ('do', ''):
                j += 1
            body_lines = []
            while j < len(lines):
                l = lines[j].strip()
                if l == 'done':
                    break
                body_lines.append(lines[j])
                j += 1

            last_ret = 0
            max_iter = 100000
            count = 0
            while count < max_iter:
                ret = self._evaluate_condition(cond)
                if ret != 0:
                    break
                last_ret = self.execute_block(body_lines)
                self._handle_var_assign(incr)
                count += 1
            return j + 1, last_ret

        return start + 1, 0

    def _handle_select(self, lines, start):
        match = re.match(r'select\s+(\w+)\s+in\s+(.+)', lines[start].strip())
        if not match:
            return start + 1, 0

        var_name = match.group(1)
        items = self._expand_items(match.group(2).strip())

        j = start + 1
        while j < len(lines) and lines[j].strip() in ('do', ''):
            j += 1
        body_lines = []
        while j < len(lines):
            if lines[j].strip() == 'done':
                break
            body_lines.append(lines[j])
            j += 1

        last_ret = 0
        while True:
            for idx, item in enumerate(items, 1):
                print(f"{idx}) {item}")
            try:
                choice = input("#? ")
                if not choice:
                    continue
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(items):
                        self.state.vars[var_name] = items[idx]
                        last_ret = self.execute_block(body_lines)
                    else:
                        print("invalid selection")
                except ValueError:
                    print("invalid selection")
            except (EOFError, KeyboardInterrupt):
                break

        return j + 1, last_ret

    def _handle_case(self, lines, start):
        line = lines[start].strip()
        match = re.match(r'case\s+(.+)\s+in', line)
        if not match:
            return start + 1, 0

        value = match.group(1).strip()
        value = Tokenizer.expand_variables(value, self.state).strip('"').strip("'")

        rest = line[line.index(' in') + 3:].strip()
        if rest.endswith('esac'):
            rest = rest[:-4].strip()
        if rest.endswith(';;'):
            rest = rest[:-2].strip()
        if rest:
            entries = re.split(r';;', rest)
            for entry in entries:
                entry = entry.strip()
                if ')==)' in entry:
                    parts = entry.split(')==)')
                    pattern_str = parts[0].strip()
                    body = parts[1].strip() if len(parts) > 1 else ''
                elif ')=' in entry:
                    pidx = entry.index(')')
                    pattern_str = entry[:pidx].strip()
                    body = entry[pidx + 1:].strip()
                elif ')' in entry:
                    pidx = entry.index(')')
                    pattern_str = entry[:pidx].strip()
                    body = entry[pidx + 1:].strip()
                else:
                    continue
                if body.endswith(';'):
                    body = body[:-1].strip()
                patterns = [p.strip().strip('"').strip("'") for p in pattern_str.split('|')]
                matched = False
                for p in patterns:
                    if p == '*' or p == value:
                        matched = True
                        break
                    if fnmatch.fnmatch(value, p):
                        matched = True
                        break
                if matched and body:
                    result = self.execute_block([body])
                    return start + 1, result
            return start + 1, 0

        j = start + 1
        while j < len(lines):
            l = lines[j].strip()
            if l == 'esac':
                return j + 1, 0
            if l.endswith(')'):
                pattern = l[:-1].strip()
                patterns = [p.strip().strip('"').strip("'") for p in pattern.split('|')]
                j += 1
                body_lines = []
                while j < len(lines):
                    l2 = lines[j].strip()
                    if l2 == ';;' or l2 == 'esac':
                        break
                    body_lines.append(lines[j])
                    j += 1
                matched = False
                for p in patterns:
                    if p == '*' or p == value:
                        matched = True
                        break
                    if fnmatch.fnmatch(value, p):
                        matched = True
                        break
                if matched:
                    result = self.execute_block(body_lines)
                    if l2 == ';;':
                        return j + 1, result
                if l2 == ';;':
                    j += 1
                continue
            j += 1

        return start + 1, 0

    def _handle_var_assign(self, line):
        line = line.replace('local ', '').replace('export ', '').replace('declare ', '')
        if '=' in line:
            var, _, value = line.partition('=')
            var = var.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            else:
                value = self._expand_value(value)
            self.state.vars[var] = value

    def _expand_value(self, value):
        if '$((' in value:
            value = self._expand_arithmetic(value)
        if '$(' in value or '`' in value:
            value = self._expand_command_sub(value)
        value = Tokenizer.expand_variables(value, self.state)
        return value

    def _expand_arithmetic(self, value):
        def replace_arith(m):
            expr = m.group(1)
            expr = Tokenizer.expand_variables(expr, self.state)
            def replace_var(m2):
                name = m2.group(0)
                return str(self.state.vars.get(name, '0'))
            expr = re.sub(r'\b([A-Za-z_]\w*)\b', replace_var, expr)
            try:
                result = eval(expr, {"__builtins__": {}}, {})
                return str(int(result) if isinstance(result, (int, float)) else 0)
            except Exception:
                return '0'
        return re.sub(r'\$\(\(([^)]+)\)\)', replace_arith, value)

    def _expand_command_sub(self, value):
        def replace_backtick(m):
            cmd = m.group(1)
            try:
                import subprocess
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.stdout.strip()
            except Exception:
                return ''
        value = re.sub(r'`([^`]+)`', replace_backtick, value)

        def replace_dollar(m):
            cmd = m.group(1)
            try:
                import subprocess
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.stdout.strip()
            except Exception:
                return ''
        value = re.sub(r'\$\(([^)]+)\)', replace_dollar, value)
        return value

    def _expand_items(self, items_str):
        items_str = self._expand_value(items_str)
        items = []
        for part in items_str.split():
            if '*' in part or '?' in part:
                items.extend(Tokenizer.expand_glob(part))
            else:
                items.append(part)
        return items

    def _evaluate_condition(self, condition):
        if not condition:
            return 1

        condition = condition.strip()
        condition = self._expand_value(condition)

        if condition.startswith('[ ') and condition.endswith(' ]'):
            condition = condition[2:-2].strip()
            return self._evaluate_condition(condition)

        if condition.startswith('(') and condition.endswith(')'):
            return self._evaluate_condition(condition[1:-1])

        if condition.startswith('!'):
            return 1 if self._evaluate_condition(condition[1:]) == 0 else 0

        if ' && ' in condition:
            parts = condition.split(' && ', 1)
            return 0 if (self._evaluate_condition(parts[0]) == 0 and
                         self._evaluate_condition(parts[1]) == 0) else 1

        if ' || ' in condition:
            parts = condition.split(' || ', 1)
            return 0 if (self._evaluate_condition(parts[0]) == 0 or
                         self._evaluate_condition(parts[1]) == 0) else 1

        if re.match(r'^-([a-z])\s+(.+)', condition):
            m = re.match(r'^-([a-z])\s+(.+)', condition)
            op, arg = m.group(1), m.group(2).strip()
            arg = os.path.expanduser(arg)
            return self._eval_unary(op, arg)

        for op in ['==', '!=', '-eq', '-ne', '-lt', '-le', '-gt', '-ge', '=',
                    '-contains', '-notcontains', '=~']:
            pattern = rf'(.+?)\s+{re.escape(op)}\s+(.+)'
            m = re.match(pattern, condition)
            if m:
                left = m.group(1).strip().strip('"').strip("'")
                right = m.group(2).strip().strip('"').strip("'")
                left = self._expand_value(left)
                right = self._expand_value(right)
                return self._eval_binary(left, op, right)

        parts = condition.split(None, 1)
        if len(parts) == 1:
            return 0 if parts[0] else 1

        if self.shell:
            return self.shell.execute_line(condition)
        return 1

    def _eval_unary(self, op, arg):
        arg = os.path.expanduser(arg)
        if op == 'f': return 0 if os.path.isfile(arg) else 1
        if op == 'd': return 0 if os.path.isdir(arg) else 1
        if op == 'e': return 0 if os.path.exists(arg) else 1
        if op == 'r': return 0 if os.path.exists(arg) and os.access(arg, os.R_OK) else 1
        if op == 'w': return 0 if os.path.exists(arg) and os.access(arg, os.W_OK) else 1
        if op == 'x': return 0 if os.path.exists(arg) and os.access(arg, os.X_OK) else 1
        if op == 's': return 0 if os.path.exists(arg) and os.path.getsize(arg) > 0 else 1
        if op == 'z': return 0 if len(arg) == 0 else 1
        if op == 'n': return 0 if len(arg) > 0 else 1
        if op == 'L': return 0 if os.path.islink(arg) else 1
        return 1

    def _eval_binary(self, left, op, right):
        if op in ('==', '='):
            return 0 if left == right else 1
        elif op == '!=':
            return 0 if left != right else 1
        elif op == '=~':
            try:
                return 0 if re.search(right, left) else 1
            except re.error:
                return 1
        elif op in ('-eq', '-ne', '-lt', '-le', '-gt', '-ge'):
            try:
                li, ri = int(left), int(right)
            except ValueError:
                try:
                    li, ri = float(left), float(right)
                except ValueError:
                    return 1
            if op == '-eq': return 0 if li == ri else 1
            if op == '-ne': return 0 if li != ri else 1
            if op == '-lt': return 0 if li < ri else 1
            if op == '-le': return 0 if li <= ri else 1
            if op == '-gt': return 0 if li > ri else 1
            if op == '-ge': return 0 if li >= ri else 1
        elif op == '-contains':
            return 0 if left in right else 1
        elif op == '-notcontains':
            return 0 if left not in right else 1
        return 1

    def _handle_arithmetic(self, stripped):
        expr = stripped[2:].rstrip(')').strip()
        expr = Tokenizer.expand_variables(expr, self.state)

        def replace_var(m):
            name = m.group(0)
            return str(self.state.vars.get(name, '0'))
        expr = re.sub(r'\b([A-Za-z_]\w*)\b', replace_var, expr)

        try:
            result = eval(expr, {"__builtins__": {}}, {})
            return int(result) if isinstance(result, (int, float)) else 0
        except Exception:
            return 0
