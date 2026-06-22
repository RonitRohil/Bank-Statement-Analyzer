# Sprint-06 Prompt 06 — TD-023: Magic-Byte Upload Validation

## Task: Add file content validation beyond extension whitelist (P1 — do only if capacity allows)

**Context:** The upload handler currently validates file extension but not file content. A `.exe` renamed to `.pdf` passes the whitelist check. This adds a second line of defense: verify the first few bytes match the expected format's magic bytes.

**Files to read first:**

- `backend/app/routers/analyze.py` — read the upload handler and validation logic
- `backend/tests/test_analyze.py` — read existing upload tests to understand the fixture pattern

---

## Change: Add `validate_magic_bytes()` to `analyze.py`

**Add this helper function** near the top of `backend/app/routers/analyze.py` (after imports, before the router):

```python
MAGIC_BYTES = {
    ".pdf": [b"%PDF"],
    ".xlsx": [b"PK\x03\x04"],   # ZIP-based format (Office Open XML)
    ".xls": [b"\xd0\xcf\x11\xe0"],  # Compound Document (old Excel binary)
    # .csv: plain text, no magic bytes — skip validation
}

def validate_magic_bytes(file_path: Path, extension: str) -> bool:
    """
    Returns True if the file's leading bytes match the expected magic for its extension.
    Returns True unconditionally for .csv (no magic bytes for plain text).
    Returns False if the file can't be read or bytes don't match.
    """
    signatures = MAGIC_BYTES.get(extension)
    if signatures is None:
        return True  # .csv — no magic byte check
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
        return any(header.startswith(sig) for sig in signatures)
    except OSError:
        return False
```

**Call the validator** in the upload handler, after the file is saved to disk and before passing it to `BankStatementAnalyzer`. If validation fails, delete the file and return 400:

```python
if not validate_magic_bytes(file_path, file_extension):
    file_path.unlink(missing_ok=True)
    raise HTTPException(
        status_code=400,
        detail=f"File content does not match extension '{file_extension}'. Upload a real {file_extension.upper()} file."
    )
```

**Constraints:**

- Read the existing upload handler carefully before making changes. Place the validation call in the right position (after save, before parse, inside the try block).
- The `finally` block that deletes the uploaded file must still run on all code paths — don't move it.
- `.csv` files skip the check. Add a comment: `# CSV is plain text — no magic byte signature to check`.
- Do not add any new pip dependencies. Use the stdlib `open()` in binary mode.

---

## Tests: Add 2 tests to `backend/tests/test_analyze.py`

Add to the existing `TestAnalyzeEndpoint` class (or equivalent):

| Test                               | What it checks                                                                               |
| ---------------------------------- | -------------------------------------------------------------------------------------------- |
| `test_pdf_magic_byte_mismatch_400` | Upload a `.pdf` file whose content is actually plain text → 400 with descriptive error       |
| `test_csv_no_magic_check`          | Upload a valid `.csv` that happens to start with `%PDF` (edge case) → still parsed correctly |

For the first test, create the fixture file with `b"this is not a pdf"` as content but name it `fake.pdf`.

---

## Verification

```bash
cd backend && pytest tests/test_analyze.py -v
pytest --tb=short -q
```

Manual: rename any text file to `statement.pdf`, upload → 400 error. Upload a real PDF → proceeds normally.

## Changelog entry required

Add to `docs/changelog.md`.
