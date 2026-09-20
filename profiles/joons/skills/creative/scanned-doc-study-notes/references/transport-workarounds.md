# Tool-call transport: Korean path segment truncation

## Symptom
A tool call that types a long absolute path containing a Korean segment (e.g. `중학과학`) intermittently fails:
- `No such file or directory` (path visibly cut before the Korean segment)
- `write_file: Permission denied` / `mkdir: cannot create directory '/home/joins'`
- `read_file: File not found` for a file `find` lists as existing
- `execute_code: SyntaxError: unterminated string literal` when the path is inside a Python string literal

ASCII-only paths on the same call succeed. Failure correlates with the length of the non-ASCII run.

## Workarounds (order of reliability)
1. `execute_code` piece-built path:
   ```python
   import os, glob
   home = os.path.expanduser("~")
   pat = os.path.join(home, ".hermes","services","*","work","venv","bin","python3")
   vp  = glob.glob(pat)[0]
   out = os.path.join(home,".hermes","services","scrp_pdf","output","중학과학")
   ```
2. `terminal` relative path from a known `workdir`. Avoid the Korean segment as an inline positional arg.
3. ASCII staging: `write_file` content to `/tmp`, render with `terminal`, then `cp`/`shutil.copy2` into the Korean dir.

## Rules
- After one failed Korean-path call, ROTATE to the next workaround; do not loop the same call.
- Do not conclude a file/dir is missing from a single truncated-path error — `find` confirms.
- This is a transport-layer truncation to work around, NOT a permanent "tool X can't handle Korean paths" rule.
