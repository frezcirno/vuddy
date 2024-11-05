# Python Wrapper of VUDDY - Vulnerability Detection Tool

## Requirements:

Linux tools:

- Git
- github-linguist
- Python 3.8+

Python packages:

- tree-sitter
- tree-sitter-c
- tree-sitter-cpp
- tree-sitter-java
- requests
- timeout_decorator
- fire
- joblib
- loguru

## Usage:

```
$ python3 vuddy.py run_vuddy your_label /path/to/your/repository git_revision
```

`./vuddy-exploded/<your_label>_<git_revision>/` contains the breakdown results of the repository.

`./vuddy-result/<your_label>_<git_revision>.jsonl` contains the vuddy detection results.
