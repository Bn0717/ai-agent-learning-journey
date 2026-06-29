"""Extract raw text from a PDF resume using pdfplumber."""
import argparse
import json
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print(json.dumps({"error": "pdfplumber not installed. Run: pip install pdfplumber"}))
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Extract text from a PDF resume")
    parser.add_argument("--file", required=True, help="Path to the PDF resume file")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {args.file}"}))
        sys.exit(1)
    if path.suffix.lower() != ".pdf":
        print(json.dumps({"error": f"Only PDF files are supported. Got: {path.suffix}"}))
        sys.exit(1)

    pages_text = []
    with pdfplumber.open(str(path)) as pdf:
        num_pages = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

    full_text = "\n\n".join(pages_text)

    if not full_text.strip():
        print(json.dumps({"error": "No text could be extracted. The PDF may be image-based."}))
        sys.exit(1)

    print(json.dumps({
        "text": full_text,
        "pages": num_pages,
        "char_count": len(full_text),
        "file": str(path.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
