# AGENTS.md

## Project

PyBash — a cross-platform bash shell implemented in pure Python. Zero external dependencies; stdlib only.

## Requirements

- Python 3.14+ (see `.python-version` and `pyproject.toml`)
- Package manager: `uv`

## Setup

```bash
uv venv
uv pip install -e .
```

## Run

```bash
python -m pybash
```

## Structure

```
pybash/
  __init__.py         # Package entry, re-exports main()
  __main__.py         # python -m pybash entrypoint
  shell/              # REPL, parsing, execution
    __init__.py       # Shell class, ShellState, main(), REPL loop, _dispatch
    redirect.py       # RedirectHandler (>, >>, <, 2>)
    completion.py     # Tab completion (readline on Linux, Console API on Windows)
  builtins/           # 60+ built-in commands
    __init__.py       # BuiltinCommands class, command registry, shared helpers, _aliases dict
    file.py           # File ops: cd, ls, mkdir, cp, mv, rm, find, chmod, ln, etc.
    text.py           # Text processing: cat, grep, sort, head, tail, sed, awk, etc.
    system.py         # System info: date, uname, whoami, env, export, base64, etc.
    shell.py          # Shell control: echo, printf, type, alias, test, help, etc.
  script.py           # Scripting engine (if/for/while/case/function)
  utils.py            # Tokenizer, Trie, variable/glob expansion
tests/
  test_builtins.py    # 38 tests for built-in commands
  test_shell.py       # 22 tests for pipes, redirects, variables, conditionals, loops, functions
  test_utils.py       # 33 tests for Trie, Tokenizer
```

## Key architecture notes

- `shell/__init__.py` owns the REPL loop. On Windows it uses Console API via ctypes for raw input and tab completion; on Linux/macOS it uses `readline`.
- `_dispatch` handles semicolons by executing preceding parts before control keywords (if/for/while/etc), and splits remaining parts into `execute_block` calls.
- Function definitions with `{...}` on the same line are handled by splitting at the closing `}` — the function is defined first, then remaining code is executed.
- `builtins/` is a package with mixin classes: `FileCommands`, `TextCommands`, `SystemCommands`, `ShellControlCommands`. All registered in `__init__.py` dict.
- `_aliases` dict in `BuiltinCommands` tracks `dir`, `ll`, `la`, `quit`, `.`, `[` for `type` command reporting.
- `script.py` handles multi-line constructs (if/for/while/case/function). It calls back into `shell.execute_line()` for individual command execution.
- `utils.py` provides `Tokenizer` (static methods for parsing/expanding) and `Trie` (used for tab completion).
- Positional parameters (`$1`, `$2`, etc.) are expanded from `state.positional` in `expand_variables`.

## Testing / Linting

```bash
python -m unittest discover -s tests -v
```

93 tests across 3 test files. No linter or type checker configured. If you add tooling, update `pyproject.toml` accordingly.

## Gotchas

- Windows tab completion uses `ctypes` and raw Console API — not readline. Don't break `_run_win()` when editing completion logic.
- History is stored at `~/.pybash_history`, aliases at `~/.pybash_aliases`.
- No formal code style is enforced. Follow existing patterns in each file.
- Backslashes are literal on Windows (tokenizer skips escape processing when `IS_WINDOWS`).
- Arithmetic expansion uses `eval()` with restricted builtins — variables inside `$((...))` are expanded before evaluation.
