# Materials / OCR test fixtures

| File | Size | Git | Use |
|---|---|---|---|
| `esl_textbook_sample_pages_9_to_11.pdf` | ~3.9 MB | tracked | Quick OCR / upload tests |
| `esl_textbook_sample.pdf` | ~16.8 MB | **gitignored** (local-only) | Full-book / longer OCR runs |
| `mistral_ocr_pages_9_10_min.json` | ~3 KB | tracked | Offline packaging spike (no API) |

Restore the full sample from the local OCR lab if missing:

`C:\Users\matth\ocr_testing\tmp1.pdf` → `esl_textbook_sample.pdf`

Offline packaging test (no Mistral call):

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_materials_ocr_packaging.py -q
```

Live Mistral OCR (needs `MISTRAL_API_KEY` in `backend/.env`):

```powershell
cd backend
$env:RUN_LIVE_MISTRAL_OCR="1"
.\.venv\Scripts\python -m pytest tests\test_materials_ocr_live.py -q
```

See `implementation_plans/v1.2_class_materials_epic.md` § Test assets.
