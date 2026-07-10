---
name: mine-convert
description: "Convert binary documents (PDF, DOCX, PPTX, XLSX, images, audio) to readable markdown using markitdown. Use when encountering a file that can't be read directly."
user-invocable: true
---

# Convert to Markdown

Convert binary or non-text files to readable markdown in-session using `uvx markitdown`.

## Arguments

$ARGUMENTS — a file path or URL:
- `/mine-convert report.pdf`
- `/mine-convert slides.pptx`
- `/mine-convert screenshot.png`
- Empty: ask the user what to convert

## Supported formats

- **Documents**: PDF, DOCX, PPTX, XLSX, XLS
- **Web**: HTML
- **Images**: PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP (OCR via markitdown)
- **Audio**: MP3, WAV (transcription via markitdown)

## Usage

```bash
uvx markitdown <file>
```

Output goes to stdout as markdown. For large files, pipe to a temp file:

```bash
uvx markitdown report.pdf -o /tmp/report.md
```

Then read the output file.

## When to reach for this

When you encounter a binary file you need to read — a PDF spec, a DOCX contract, a screenshot with text, an Excel dataset. Don't ask the user to convert it manually; just run markitdown.
