"""
Extract and run code examples from README.md
"""

import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from richtablebuilder import example


def extract_python_code_blocks(markdown_file: str | Path) -> str:
    """Extract Python code blocks from a markdown file."""
    with open(markdown_file, "r") as f:
        content = f.read()

    # Find all Python code blocks (```python ... ```)
    pattern = r"```python\n(.*?)```"
    code_blocks = re.findall(pattern, content, re.DOTALL)
    if code_blocks:
        return "\n\n".join(code_blocks)
    else:
        raise ValueError("No code blocks found in README.md")


def execfile(
    filepath: str, globals: dict[str, object] | None = None, locals: dict[str, object] | None = None
):
    if globals is None:
        globals = {}
    globals["__file__"] = filepath
    globals["__name__"] = "__main__"
    with open(filepath, "rb") as file:
        exec(compile(file.read(), filepath, "exec"), globals, locals)


def test_readme_examples():
    readme_path = Path(__file__).parent.parent / "README.md"
    code_block = extract_python_code_blocks(readme_path)

    with NamedTemporaryFile("w+") as f:
        _ = f.write(code_block)
        f.flush()
        execfile(f.name)


def test_module_example():
    example()
