# PyBash

A cross-platform bash shell implemented entirely in Python. Works on Windows, macOS, and Linux without depending on system commands.

## Features

- **60+ built-in commands** — `ls`, `cat`, `grep`, `find`, `sort`, `wc`, `head`, `tail`, `cp`, `mv`, `rm`, `mkdir`, `echo`, `printf`, `cd`, `pwd`, and more
- **Shell scripting** — `if/then/else/fi`, `for/do/done`, `while/do/done`, `case/esac`, functions
- **Pipeline & redirects** — pipes (`|`), output redirect (`>`, `>>`), input redirect (`<`), stderr redirect (`2>`)
- **Variable expansion** — `$VAR`, `${VAR}`, `$?`, `$#`, `$@`, `$1`..`$9`
- **Arithmetic** — `$(( expression ))` with full Python math
- **Command substitution** — `$(command)` and backticks
- **Tab completion** — bash-style: commands complete to first match (builtins priority), paths do lazy common prefix completion; Alt lists all matches
- **Keyboard shortcuts** — Ctrl+C (cancel), Ctrl+D (exit), Ctrl+L (clear screen)
- **History** — persistent command history with search
- **Pure Python** — no dependency on `cmd.exe`, `bash`, or other system shells; zero external dependencies

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd pybash

# Create virtual environment and install
uv venv
uv pip install -e .

# Run
python -m pybash
```

## Quick Start

```bash
# Basic commands
ls -la
cat file.txt
echo "hello world"

# Variables
name="PyBash"
echo "Welcome to $name"

# Conditionals
x=10
if [ $x -gt 5 ]; then echo "big"; else echo "small"; fi

# Loops
for i in 1 2 3; do echo $i; done

i=0
while [ $i -lt 5 ]; do echo $i; i=$((i+1)); done

# Functions
greet() { echo "Hello, $1!"; }
greet "World"

# Pipes & redirects
ls | grep ".py"
echo "data" > output.txt
cat input.txt | sort | uniq > output.txt
```

## Built-in Commands

### File Operations

| Command   | Description                                              |
| --------- | -------------------------------------------------------- |
| `ls`    | List directory contents (`-l`, `-a`, `-h`, `-R`) |
| `cat`   | Concatenate and print files (`-n`, `-s`)             |
| `cp`    | Copy files and directories (`-r`, `-f`)              |
| `mv`    | Move/rename files (`-f`, `-v`)                       |
| `rm`    | Remove files and directories (`-r`, `-f`)            |
| `mkdir` | Create directories (`-p`)                              |
| `touch` | Create empty files or update timestamps                  |
| `find`  | Search for files (`-name`, `-type`, `-exec`)       |
| `chmod` | Change file permissions                                  |
| `ln`    | Create links (`-s` for symbolic)                       |
| `stat`  | Display file status                                      |
| `du`    | Estimate file space usage (`-h`)                       |
| `df`    | Report disk space usage                                  |

### Text Processing

| Command  | Description                                             |
| -------- | ------------------------------------------------------- |
| `grep` | Search text patterns (`-i`, `-v`, `-n`, `-w`)   |
| `sort` | Sort lines (`-r`, `-n`, `-u`)                     |
| `uniq` | Filter duplicate lines (`-c`, `-d`)                 |
| `wc`   | Count lines, words, characters (`-l`, `-w`, `-c`) |
| `head` | Output first lines (`-n N`)                           |
| `tail` | Output last lines (`-n N`, `-f`)                    |
| `cut`  | Extract columns (`-d`, `-f`)                        |
| `tr`   | Translate characters (`-d`, `-s`)                   |
| `sed`  | Stream editor (`s/pattern/replacement/`)              |
| `awk`  | Pattern scanning (`{print $1}`)                       |
| `diff` | Compare files                                           |
| `tee`  | Read from stdin and write to file                       |

### System

| Command      | Description                 |
| ------------ | --------------------------- |
| `date`     | Display/set date and time   |
| `uname`    | System information (`-a`) |
| `whoami`   | Current username            |
| `hostname` | System hostname             |
| `env`      | Environment variables       |
| `export`   | Set environment variables   |
| `which`    | Locate a command            |
| `type`     | Display command type        |
| `sleep`    | Delay for N seconds         |
| `seq`      | Print number sequences      |

### Shell Control

| Command            | Description                      |
| ------------------ | -------------------------------- |
| `cd`             | Change directory                 |
| `pwd`            | Print working directory          |
| `echo`           | Print arguments (`-n`, `-e`) |
| `printf`         | Formatted output                 |
| `source` / `.` | Execute script in current shell  |
| `alias`          | Create command aliases           |
| `history`        | Command history                  |
| `help`           | Display help                     |
| `exit`           | Exit the shell                   |

## Shell Scripting

### Variables

```bash
# Assignment (no spaces around =)
name="hello"
count=42

# Expansion
echo $name
echo ${name}
echo $((count + 1))    # Arithmetic
echo $(date)           # Command substitution

# Special variables
echo $?    # Last return code
echo $$    # Process ID
echo $#    # Number of arguments
echo $@    # All arguments
echo $1    # First argument
```

### Conditionals

```bash
# Simple if
if [ -f "file.txt" ]; then
    echo "File exists"
fi

# if/elif/else
x=10
if [ $x -lt 5 ]; then
    echo "small"
elif [ $x -lt 20 ]; then
    echo "medium"
else
    echo "big"
fi

# Test operators
[ -f file ]    # File exists
[ -d dir ]     # Directory exists
[ -r file ]    # File is readable
[ -w file ]    # File is writable
[ -s file ]    # File is not empty
[ "$a" = "$b" ]  # Strings equal
[ $a -lt $b ]    # Numbers: less than
```

### Loops

```bash
# for loop
for file in *.txt; do
    echo $file
done

# C-style for
for ((i=0; i<10; i++)); do
    echo $i
done

# while loop
i=0
while [ $i -lt 5 ]; do
    echo $i
    i=$((i+1))
done

# until loop
until [ -f "ready.txt" ]; do
    sleep 1
done
```

### Case Statements

```bash
case $1 in
    start)  echo "Starting...";;
    stop)   echo "Stopping...";;
    *)      echo "Unknown command";;
esac
```

### Functions

```bash
# Function definition
add() {
    echo $(($1 + $2))
}

# Call with arguments
result=$(add 3 4)
echo $result    # 7
```

### Pipes & Redirects

```bash
# Pipe
cat file.txt | grep "error" | wc -l

# Output redirect
echo "hello" > file.txt        # Overwrite
echo "world" >> file.txt       # Append

# Input redirect
sort < unsorted.txt > sorted.txt

# Stderr redirect
command 2> errors.txt
command 2>&1                    # Merge stderr to stdout
```

### One-liners

```bash
# These all work on a single line
i=0; while [ $i -lt 3 ]; do echo $i; i=$((i+1)); done
for x in a b c; do echo $x; done
if [ 1 -eq 1 ]; then echo yes; else echo no; fi
greet() { echo hello; }; greet
```

## Tab Completion

- **Commands**: Auto-completes to first matching command (builtins have highest priority)
- **Paths/files**: Lazy common prefix completion — inserts longest common prefix among matches
- **Alt key**: Lists all matching commands (builtins sorted first, then externals)

## Architecture

```
pybash/
  __init__.py     # Package entry point
  __main__.py     # python -m pybash
  shell.py        # REPL, parser, pipeline, redirects, tab completion
  builtins.py     # 60+ commands in pure Python
  script.py       # Bash scripting engine (if/for/while/case/functions)
  utils.py        # Tokenizer, Trie, variable expansion, glob
```

## Dependencies

- Python 3.14+
- Zero external dependencies — everything is pure Python using only the standard library

## License

MIT

