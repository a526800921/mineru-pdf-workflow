# pdf-auto JSON Mode Test Notes

## Test Results Summary

Tests executed on 2026-06-28 for `PDF_AUTO_JSON=1` feature in `scripts/pdf-auto`.

### Passed Tests

| Test | Status | Details |
|------|--------|---------|
| Error: nonexistent PDF | PASS | Valid JSON with `status: error`, `exit_code: 1`, all null/empty |
| Error: nonexistent segments dir | PASS | Same valid error JSON |
| stderr in JSON mode | PASS | Chinese error messages visible on stderr |
| Syntax check (`bash -n`) | PASS | No syntax errors |

### Environment-Dependent Tests

These require real MinerU-processed data and cannot be run in isolation:

- **all_passed path**: Requires a PDF + segments where all coverage >= threshold
- **merged_with_issues path**: Requires segments that fail even after rerun

See `.superpowers/sdd/task-4-report.md` for full expected commands and outputs.

## How to Run Environment-Dependent Tests

```bash
# Test all_passed path (with data that passes validation)
PDF_AUTO_JSON=1 PDF_VALIDATE_THRESHOLD=0.5 scripts/pdf-auto sample.pdf sample-segments > /tmp/test_output.json 2>/dev/null
python3 -m json.tool /tmp/test_output.json

# Test merged_with_issues path (with data that has issues)
PDF_AUTO_JSON=1 PDF_VALIDATE_THRESHOLD=0.99 scripts/pdf-auto sample.pdf sample-segments > /tmp/test_output.json 2>/dev/null
python3 -m json.tool /tmp/test_output.json
```
