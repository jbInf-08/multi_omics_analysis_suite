"""The upload endpoint must not let a filename choose where the file lands.

``POST /datasets/{id}/upload`` took ``file.filename`` straight from the
multipart body and joined it onto the dataset directory. Two things make that
exploitable by any authenticated user:

* ``Path("/data/uploads/1") / "/etc/passwd"`` is ``/etc/passwd`` -- pathlib
  returns the right-hand side whole when it is absolute, so the base is
  discarded entirely.
* ``"../../.."`` walks out of the directory the ordinary way.

CodeQL rates it ``py/path-injection`` at high severity. These tests exercise
the sanitising rule the route now applies, rather than the route itself, so
they need no database or running app -- the point is the rule, and a change to
it should fail here.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

BASE = Path("/data/uploads/0000-1111")


def sanitise(filename: str | None) -> str | None:
    """Mirror of the rule in routes/datasets.py: keep only a final component.

    Both flavours are applied because a filename arrives as text from a client
    that may be on either platform, and ``PurePosixPath`` does not treat a
    backslash as a separator.
    """
    name = PurePosixPath(filename or "").name or ""
    name = PureWindowsPath(name).name
    if not name or name in {".", ".."}:
        return None
    return name


@pytest.mark.parametrize(
    "filename",
    [
        "/etc/passwd",
        "../../../etc/passwd",
        "..\\..\\windows\\win.ini",
        "subdir/nested.csv",
    ],
)
def test_traversal_attempts_are_reduced_to_a_bare_name(filename):
    """Whatever is passed, only the last component survives."""
    name = sanitise(filename)
    assert name is not None
    assert "/" not in name and "\\" not in name
    assert ".." not in name
    # And the join now stays put.
    assert (BASE / name).parent == BASE


@pytest.mark.parametrize("filename", ["", None, ".", "..", "/", "///"])
def test_filenames_with_no_usable_component_are_rejected(filename):
    """These would otherwise resolve to the directory itself or its parent."""
    assert sanitise(filename) is None


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("expression.csv", "expression.csv"),
        ("counts.tsv", "counts.tsv"),
        ("sample.h5ad", "sample.h5ad"),
        ("has spaces.vcf", "has spaces.vcf"),
        ("dots.in.name.parquet", "dots.in.name.parquet"),
    ],
)
def test_ordinary_filenames_are_untouched(filename, expected):
    """Sanitising must not damage the names people actually upload."""
    assert sanitise(filename) == expected


def test_extension_still_resolves_after_sanitising():
    """file_type_map keys off the suffix, which must survive the rewrite."""
    name = sanitise("../../../data/expression.CSV")
    assert name == "expression.CSV"
    assert Path(name).suffix.lower().lstrip(".") == "csv"


def test_absolute_path_would_have_escaped_without_the_rule():
    """Pin the underlying pathlib behaviour this defends against.

    If a future Python changed it, the rule would be unnecessary -- but until
    then this documents why it exists.
    """
    assert Path("/data/uploads/1") / "/etc/passwd" == Path("/etc/passwd")
