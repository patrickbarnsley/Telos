import pdfplumber
import docx
import io
import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv()

def _get_client():
    try:
        import streamlit as st
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=api_key)

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

def score_match(resume_text: str, job_description: str, target_role: str) -> dict:
    client = _get_client()

    prompt = f"""You are a reverse ATS (Applicant Tracking System) engine. Score how well this candidate's resume matches the job description — the way a real ATS and hiring manager would evaluate it.

CANDIDATE'S TARGET ROLE: {target_role}

CANDIDATE'S RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Analyze the match carefully. Consider required skills, years of experience, education, certifications, industry background, and soft skills.

Return ONLY a JSON object. No preamble, no explanation, no markdown formatting. Just the raw JSON:
{{
  "overall_score": <integer 0-100>,
  "match_summary": "<2-3 sentence plain-English summary of the match>",
  "matched_requirements": ["<requirement met>", "..."],
  "missing_requirements": ["<requirement not met or unclear>", "..."],
  "recommended_actions": ["<specific action to improve this match>", "..."]
}}"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()
    return json.loads(response_text)