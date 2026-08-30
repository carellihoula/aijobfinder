FROM python:3.12-slim

WORKDIR /app

# WeasyPrint's text/font rendering (Pango/HarfBuzz) - shared libs only, no compiler
# needed since pip installs weasyprint from a prebuilt wheel.
# tesseract-ocr is the actual OCR engine pytesseract shells out to (fra+eng -
# CVs in this app are French or English) - needed for scanned/image-only PDFs,
# see pipeline/nodes/pdf_parser.py.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libharfbuzz-subset0 \
    tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
