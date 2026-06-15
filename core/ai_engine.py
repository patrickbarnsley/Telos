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
  "recommended_certs": ["<specific certification that would strengthen this application, with brief reason why>", "..."],
  "recommended_actions": ["<specific action to improve this match — not cert-related, those go above>", "..."]
}}

For recommended_certs: always include at least 1-3 relevant certifications if there are any gaps or if certs would strengthen the application. If the candidate already has all relevant certs, return an empty list. Be specific — name the exact certification."""

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

def check_company_legitimacy(company_name: str, job_description: str) -> dict:
    client = _get_client()

    prompt = f"""Research the company "{company_name}" and evaluate whether this job posting appears legitimate or fraudulent.

JOB DESCRIPTION:
{job_description[:2000]}

Search for this company online. Look for:
- Official website and LinkedIn presence
- Glassdoor or Indeed reviews and ratings
- Any scam reports or fake job posting complaints
- Whether the job details match the company's actual business
- Red flags like requests for personal info, unrealistic pay, vague descriptions

Return ONLY a JSON object. No preamble, no markdown:
{{
  "verdict": "<legitimate|suspicious|likely_scam>",
  "confidence": "<high|medium|low>",
  "summary": "<2-3 sentence plain English summary of what you found>",
  "green_flags": ["<positive indicator>", "..."],
  "red_flags": ["<warning sign>", "..."]
}}

If you cannot find information about the company, set verdict to "suspicious" and note this in the summary."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, 'type') and block.type == "text":
            response_text += block.text

    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()

    return json.loads(response_text)

def generate_critical_path(profile: dict, match_history: list) -> dict:
    client = _get_client()

    match_summary = ""
    if match_history:
        for m in match_history[:5]:
            match_summary += f"- {m['company']} — {m['role']}: {m['overall_score']}% match\n"
            missing = json.loads(m['missing_reqs']) if m['missing_reqs'] else []
            certs = json.loads(m['recommended_certs']) if m['recommended_certs'] else []
            if missing:
                match_summary += f"  Gaps: {', '.join(missing[:3])}\n"
            if certs:
                match_summary += f"  Recommended certs: {', '.join(certs[:3])}\n"

    prompt = f"""You are a direct, no-nonsense career advisor. Build a specific, actionable critical path for this candidate to reach their target role.

CANDIDATE PROFILE:
Target Role: {profile['target_role']}
Career Goals: {profile.get('goals', 'Not specified')}

RESUME SUMMARY:
{profile['resume_text'][:3000]}

RECENT JOB MATCH ANALYSIS:
{match_summary if match_summary else 'No match history yet.'}

Build a critical path from their current state to their target role. Be specific — name exact skills, certifications, and actions. No generic advice.

Return ONLY a JSON object. No preamble, no markdown:
{{
  "current_state": "<1-2 sentence honest assessment of where they are now>",
  "target_state": "<1-2 sentence description of the target role and what success looks like>",
  "gap_summary": "<2-3 sentence summary of the key gaps between current and target state>",
  "milestones": [
    {{
      "order": 1,
      "title": "<milestone title>",
      "description": "<what to do and why>",
      "timeline": "<e.g. 30 days, 60 days, 3 months>",
      "actions": ["<specific action>", "..."],
      "success_criteria": "<how you know this milestone is complete>"
    }}
  ],
  "critical_certs": ["<cert name — reason it matters for target role>", "..."],
  "estimated_timeline": "<total estimated time to reach target role>",
  "biggest_risk": "<the single biggest thing that could derail this path>"
}}

Include 4-6 milestones ordered by priority. Be honest about timeline — don't sugarcoat it."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()
    return json.loads(response_text)


def chat_with_advisor(profile: dict, critical_path: dict, conversation_history: list, user_message: str) -> str:
    client = _get_client()

    system = f"""You are a direct, no-nonsense career advisor. You have the candidate's profile and their generated critical path. Give specific, actionable advice. No generic resume tips. No cheerleading. Be honest.

CANDIDATE TARGET ROLE: {profile['target_role']}
CAREER GOALS: {profile.get('goals', 'Not specified')}

CRITICAL PATH SUMMARY:
Current State: {critical_path.get('current_state', '')}
Target State: {critical_path.get('target_state', '')}
Estimated Timeline: {critical_path.get('estimated_timeline', '')}
Biggest Risk: {critical_path.get('biggest_risk', '')}"""

    history = conversation_history + [{"role": "user", "content": user_message}]

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=system,
        messages=history
    )

    return message.content[0].text