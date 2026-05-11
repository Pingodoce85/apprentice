import pymupdf
import re

def extract_toc(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    toc = doc.get_toc()
    if toc:
        return [(item[1], item[2]) for item in toc]
    headings = []
    heading_patterns = [
        r"^\s*SECTION\s+[\d\s]+[-–]\s*.+",
        r"^\s*\d{2}\s+\d{2}\s+\d{2}\s+.+",
        r"^\s*[A-Z][A-Z\s]{4,}$",
        r"^\s*\d+\.\d+\s+[A-Z].+",
        r"^\s*PART\s+\d+",
    ]
    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("blocks")
        for block in blocks:
            text = block[4].strip()
            for pattern in heading_patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    headings.append((text[:80], page_num))
                    break
    return headings

def extract_section_text(pdf_bytes, start_page, end_page):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    end_page = min(end_page, len(doc))
    for page_num in range(start_page - 1, end_page):
        page = doc[page_num]
        text += f"
[Page {page_num + 1}]
"
        text += page.get_text()
        tables = page.find_tables()
        if tables.tables:
            import pandas as pd
            for table in tables.tables:
                try:
                    df = table.to_pandas()
                    text += "
[TABLE]
"
                    text += df.to_html(index=False)
                    text += "
[/TABLE]
"
                except:
                    pass
    return text
