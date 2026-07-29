# Third-party notices

Senpai's Pdf Workshop is licensed under Apache-2.0 (see `LICENSE`). It uses the
following third-party software. This file lists what's bundled/imported
directly; each project's own license file is the authoritative text.

## Core (always installed — `pip install senpais-pdf-workshop`)

| Project | License | Used for |
|---|---|---|
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | Page structure, reading/writing PDFs |
| [pikepdf](https://github.com/pikepdf/pikepdf) (QPDF) | MPL-2.0 | Encryption, repair, low-level PDF objects |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | BSD-3-Clause / Apache-2.0 | PDF rendering and rasterisation |
| [Pillow](https://github.com/python-pillow/Pillow) | HPND (permissive) | Image decode/encode for stamps and image ops |
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 / BSD-3-Clause | AES support for pypdf's reader |
| [PySide6](https://www.qt.io/qt-for-python) (Qt for Python) | LGPL-3.0 | Desktop GUI toolkit, linked dynamically |

## Optional — `extras` group (`pip install "senpais-pdf-workshop[extras]"`)

| Project | License | Used for |
|---|---|---|
| [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) | MPL-2.0 | Adds a searchable text layer (drives Tesseract) |
| [camelot-py](https://github.com/camelot-dev/camelot) | MIT | Table detection for PDF → Excel |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | MIT | Writes the .xlsx workbook |
| [pandas](https://github.com/pandas-dev/pandas) | BSD-3-Clause | camelot-py's own table-data dependency |
| [numpy](https://github.com/numpy/numpy) | BSD-3-Clause (+ 0BSD/MIT/Zlib/CC0-1.0 bundled components) | camelot-py's own table-data dependency |
| [opencv-python-headless](https://github.com/opencv/opencv-python) | Apache-2.0 | camelot-py's own image-processing dependency |
| [playa-pdf](https://github.com/dhdaines/playa) | MIT | camelot-py's own PDF-parsing dependency |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | MIT | Positioned text extraction for PDF → Word |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | MIT | pdfplumber's own PDF-parsing dependency |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT | Writes the .docx document |
| [python-pptx](https://github.com/scanny/python-pptx) | MIT | Writes the .pptx presentation |
| [XlsxWriter](https://github.com/jmcnamara/XlsxWriter) | BSD-2-Clause | python-pptx's own dependency |
| [lxml](https://github.com/lxml/lxml) | BSD-3-Clause | python-docx/python-pptx's own XML dependency |

## External programs, invoked as separate processes (never bundled/imported)

These are full third-party programs the user installs separately (or that the
Windows installer offers to install alongside the app) and are only ever
invoked as subprocesses — never linked into or imported by this project's
code. Their copyleft licenses are why they're kept at arm's length; see the
README's Licensing section for the reasoning.

| Program | License | Used for |
|---|---|---|
| [Ghostscript](https://www.ghostscript.com/) | AGPL-3.0 | `compress`, `pdf_to_pdfa` |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | Apache-2.0 | `ocr` (text recognition) |
| [LibreOffice](https://www.libreoffice.org/) | MPL-2.0 | `office_to_pdf` |

## Development / build tooling (not shipped in the application)

| Project | License | Used for |
|---|---|---|
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Test suite |
| [ruff](https://github.com/astral-sh/ruff) | MIT | Linting |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | GPL-2.0-with-exception | Freezes the app into an executable (its bootloader exception permits distributing the frozen app under this project's own license) |
| [reportlab](https://www.reportlab.com/) | BSD-3-Clause | Dev-only PDF generation used while prototyping |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Custom (free for any use, including commercial) | Builds the Windows installer |
