"""Zip a Lambda folder for upload through the console (Code -> Update -> .zip file).

    python scripts/package_lambda.py              # both functions
    python scripts/package_lambda.py api_handler  # one function

Writes dist/<function>.zip with the source files at the zip root. If the function folder has a
requirements.txt, those packages are pip-installed into the zip as well (pure-Python only;
boto3 is already in the Python 3.12 runtime). dist/ and *.zip are gitignored.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNCTIONS = ("process_resume", "api_handler")
INCLUDE = (".py", ".json")
SKIP_DIRS = {"__pycache__", "bin"}


def _add_tree(zf, src, keep):
    added = []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if keep(fn):
                path = os.path.join(dirpath, fn)
                arc = os.path.relpath(path, src).replace(os.sep, "/")
                zf.write(path, arc)
                added.append(arc)
    return added


def package(name):
    src = os.path.join(ROOT, "lambda", name)
    if not os.path.isdir(src):
        raise SystemExit(f"no such function folder: lambda/{name}")
    if not os.path.exists(os.path.join(src, "lambda_function.py")):
        raise SystemExit(f"lambda/{name} has no lambda_function.py")
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}.zip")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        files = _add_tree(zf, src, lambda fn: fn.endswith(INCLUDE))
        deps = []
        req = os.path.join(src, "requirements.txt")
        if os.path.exists(req):
            build = tempfile.mkdtemp(prefix=f"{name}-deps-")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "--no-compile",
                     "--disable-pip-version-check", "-r", req, "--target", build],
                    check=True,
                )
                deps = _add_tree(zf, build, lambda fn: not fn.endswith(".pyc"))
            finally:
                shutil.rmtree(build, ignore_errors=True)

    extra = f" + {len(deps)} dependency files" if deps else ""
    print(f"{os.path.relpath(out, ROOT)}  ({os.path.getsize(out) // 1024} KB): {', '.join(files)}{extra}")


if __name__ == "__main__":
    for fn in sys.argv[1:] or FUNCTIONS:
        package(fn)
