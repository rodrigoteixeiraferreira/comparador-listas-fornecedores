# Transcribe a supplier price list from a photo

You are reading a photo of a printed price list that a supplier sent to a small supermarket in Argentina.
Transcribe it exactly. Your transcription is compared with an independent second transcription; only the lines
where both agree are used, so a guess is worse than a doubt.

Rules:

- One entry per product line, in the order printed.
- `code`: the item code at the left of the line, exactly as printed.
- `description`: the product text exactly as printed: same words, spelling, capitalization and abbreviations.
  Do not correct, expand, translate or normalize anything.
- `price`: the price exactly as printed, without the `$` sign (Argentine format: dot for thousands, comma for
  decimals, e.g. `4.739,11`).
- `section`: the section heading the line is under (for example `ALMACEN`), or `""` if there is none.
- `doubt`: `true` if any character of the line is hard to read or you are not sure of it; otherwise `false`.
  Never guess silently: write your best reading and set `doubt` to `true`.
- `header`: the title and note lines above the first section, verbatim, one string per printed line.

Answer with only this JSON object, no commentary:

```json
{"header": ["..."], "lines": [{"code": "...", "description": "...", "price": "...", "section": "...", "doubt": false}]}
```
