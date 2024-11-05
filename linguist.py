import shutil
import subprocess
import tempfile
from os import PathLike
from pathlib import Path

# Check exist for github-linguist
if not shutil.which("github-linguist"):
    raise FileNotFoundError(
        "github-linguist is not installed.\n"
        "Please refer to https://github.com/github-linguist/linguist for installation."
    )


def detect_language(
    file: PathLike = None,
    src: bytes = None,
    suffix: str = None,
):
    """
    example output:
            extension_install_prompt.h: 476 lines (387 sloc)
            type:      Text
            mime type: text/plain
            language:  C++
    """
    if file:
        file = Path(file)
        src = file.open("rb").read()
        suffix = file.suffix
    elif src and suffix:
        pass
    else:
        raise ValueError("Either file or src and suffix must be provided.")

    with tempfile.NamedTemporaryFile("wb", suffix=suffix) as tmp_f:
        # create temporary file to allow linguistic to escape .gitignore
        tmp_f.write(src)
        tmp_f.flush()
        output = subprocess.check_output(
            f"github-linguist {tmp_f.name}",
            shell=True,
            text=True,
            stderr=subprocess.STDOUT,
        )
        language = output.splitlines()[3].strip()
        language = language.split(":")[1].strip()
        # return value: ['C++', 'C', 'Objective-c']
        return language
