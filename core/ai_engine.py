import pdfplumber
import docx
import io
import base64
import anthropic
import json
import os
from dotenv import load_dotenv
from PIL import Image

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

def extract_jd_from_image(uploaded_file) -> str:
    """Extract job-description text from an uploaded screenshot/image via Claude vision.
    Returns the transcribed text for the user to review before saving."""
    client = _get_client()
    raw = uploaded_file.read()

    # Normalize any uploaded image to PNG so we accept whatever format the user has.
    try:
        img = Image.open(io.BytesIO(raw))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
    except Exception:
        image_bytes = raw  # fall back to the original bytes

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Extract the job posting text from this image as accurately as possible. "
        "Return only the text of the posting itself — role, responsibilities, requirements, "
        "qualifications, and any salary or company details shown. Preserve the wording. "
        "Do not add commentary, invented headings, or a summary. If part of the image is cut "
        "off or unreadable, transcribe what is visible and do not guess at the rest."
    )

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return message.content[0].text.strip()

def score_match(resume_text: str, job_description: str, target_role: str) -> dict:
    client = _get_client()

    prompt = f"""You are a strict ATS (Applicant Tracking System) engine. Your job is to score resumes the way enterprise ATS software actually does — not the way a generous human recruiter would.

IMPORTANT SCORING CALIBRATION:
- 90-100: Resume could be submitted as-is. Near-perfect keyword and requirement match.
- 75-89: Strong match with minor gaps. Likely passes ATS screening.
- 60-74: Moderate match. Real ATS systems would likely filter this out before a human sees it.
- Below 60: Poor match. Would be automatically rejected by most ATS systems.

Be strict. Most ATS systems reject 70-75% of resumes. Do not score generously. A missing required skill, certification, or experience area should meaningfully lower the score. Do not give credit for skills that are implied but not explicitly stated in the resume.

CANDIDATE'S TARGET ROLE: {target_role}

CANDIDATE'S RESUME:
{resume_text[:10000]}

JOB DESCRIPTION:
{job_description}

Analyze strictly. Only count requirements as met if they are explicitly and clearly demonstrated in the resume. Implied experience does not count. Missing required qualifications must lower the score significantly.

Return ONLY a JSON object. No preamble, no explanation, no markdown formatting. Just the raw JSON:
{{
  "overall_score": <integer 0-100>,
  "match_summary": "<2-3 sentence plain-English summary of the match — be direct about gaps>",
  "matched_requirements": ["<requirement explicitly met in resume>", "..."],
  "missing_requirements": ["<requirement missing or only implied, not explicit>", "..."],
  "recommended_certs": ["<specific certification that would strengthen this application, with brief reason why>", "..."],
  "recommended_actions": ["<specific action to improve this match — not cert-related, those go above>", "..."]
}}

For recommended_certs: only recommend certifications from real, verifiable professional organizations you are certain exist. Include the full certification name and the issuing organization. If you are not certain a certification body is real and established, omit it entirely. Never recommend certifications sourced from forums, Reddit, or community discussions. It is better to return fewer recommendations or an empty list than to recommend something that cannot be verified."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
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
{job_description[:10000]}

Search for this company online. Look for official website, LinkedIn presence, Glassdoor reviews, any scam reports, whether job details match the company's actual business.

Note: Job postings hosted on Workday, Greenhouse, Lever, iCIMS, BambooHR, ADP, or similar enterprise ATS platforms are strong green flags — these are paid enterprise systems that scammers do not use. A job description that appears cut off is NOT a red flag — it may simply be a display limit in our system. Focus on whether the company itself is real and legitimate, not on formatting of the posting.

After your research, return ONLY a JSON object — no other text:
{{
  "verdict": "<legitimate|suspicious|likely_scam>",
  "confidence": "<high|medium|low>",
  "summary": "<2-3 sentence plain English summary of what you found>",
  "green_flags": ["<positive indicator>", "..."],
  "red_flags": ["<warning sign>", "..."]
}}"""

    try:
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

        if not response_text.strip():
            raise ValueError("Empty response from web search")

    except Exception:
        fallback_prompt = f"""Evaluate whether this job posting appears legitimate or potentially fraudulent based on the information provided.

COMPANY NAME: {company_name}

JOB DESCRIPTION:
{job_description[:10000]}

Look for red flags like vague company details, unrealistic salary, requests for personal info, poor grammar, or too-good-to-be-true promises. Also note any green flags like specific role details, realistic requirements, and professional tone.

Return ONLY a JSON object:
{{
  "verdict": "<legitimate|suspicious|likely_scam>",
  "confidence": "<high|medium|low>",
  "summary": "<2-3 sentence plain English summary>",
  "green_flags": ["<positive indicator>", "..."],
  "red_flags": ["<warning sign>", "..."]
}}"""

        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": fallback_prompt}]
        )
        response_text = message.content[0].text.strip()

    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    if "{" in response_text:
        response_text = response_text[response_text.rfind("{"):response_text.rfind("}")+1]

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
{profile['resume_text'][:10000]}

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
  "critical_certs": ["<cert name from verified professional organization — issuing body and reason it matters>", "..."],
  "estimated_timeline": "<total estimated time to reach target role>",
  "biggest_risk": "<the single biggest thing that could derail this path>"
}}

Include 4-6 milestones ordered by priority. Be honest about timeline — don't sugarcoat it.

For critical_certs: only recommend certifications from established, verifiable professional organizations. Include the issuing organization name alongside the cert name. If you cannot confirm a certification body is real and established, omit it. Never fabricate certification bodies, acronyms, or programs sourced from forums or community discussions. Return an empty list rather than recommend something unverifiable."""

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

    system = f"""You are a direct, no-nonsense career advisor. You have full access to the candidate's profile, resume, and career paths. Give specific, actionable advice based on what you know about them. No generic tips. No cheerleading. Be honest.

CANDIDATE TARGET ROLE: {profile['target_role']}
CAREER GOALS: {profile.get('goals', 'Not specified')}

CANDIDATE RESUME:
{profile.get('resume_text', 'Not provided')[:5000]}

ALL CAREER PATHS:
{json.dumps(profile.get('all_paths', []))}

CURRENT PATH: {profile.get('current_path_name', 'Master Roadmap')}

CRITICAL PATH SUMMARY:
Current State: {critical_path.get('current_state', '')}
Target State: {critical_path.get('target_state', '')}
Gap Summary: {critical_path.get('gap_summary', '')}
Estimated Timeline: {critical_path.get('estimated_timeline', '')}
Biggest Risk: {critical_path.get('biggest_risk', '')}

You know this person's background from their resume. Never say you don't have their profile — you do. Reference specific details from their resume when giving advice."""

    history = conversation_history + [{"role": "user", "content": user_message}]

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=system,
        messages=history
    )

    return message.content[0].text