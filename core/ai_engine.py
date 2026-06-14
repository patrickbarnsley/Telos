import pdfplumber
import docx
import io

def extract_resume_text(uploaded_file) -> str:
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    if filename.endswith(".pdf"):
        return _extract_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return _extract_from_docx(file_bytes)
    else:
        raise ValueError("Unsupported file type. Please upload a PDF or Word document (.docx).")

def _extract_from_pdf(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def _extract_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    return text.strip()