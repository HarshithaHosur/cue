
# ============================================================
#  RESUME PARSER & CLAIM EXTRACTOR
#  Extracts structured claims, skills, projects, and experience
#  from PDF, DOCX, and TXT resumes.
#  Tracks coverage state against live interview transcript.
# ============================================================

import os
import re
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResumeClaim:
    """A specific skill, technology, or project claim extracted from a resume."""
    claim_id: str
    category: str              # "skill", "technology", "project", "experience", "certification"
    text: str
    keywords: List[str] = field(default_factory=list)
    status: str = "UNEXPLORED"  # UNEXPLORED, MENTIONED, DISCUSSED, VALIDATED
    evidence_snippet: str = ""
    evidence_timestamp: Optional[float] = None


class ResumeParser:
    """Parses resumes and extracts key claims for interview co-piloting."""

    TECH_PATTERNS = [
        "Python", "JavaScript", "TypeScript", "C++", "Java", "Go", "Rust",
        "React", "Vue", "Angular", "Node.js", "Django", "FastAPI", "Flask",
        "Kubernetes", "Docker", "AWS", "GCP", "Azure", "Kafka", "RabbitMQ",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "GraphQL",
        "REST", "gRPC", "Microservices", "CI/CD", "Git", "Linux", "Terraform",
        "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-Learn", "SQL"
    ]

    @classmethod
    def parse_file(cls, file_path: str) -> Dict[str, Any]:
        """Parses a resume file and extracts text and claims."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        ext = os.path.splitext(file_path)[1].lower()
        raw_text = ""

        try:
            if ext == ".txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()
            elif ext == ".pdf":
                raw_text = cls._extract_pdf_text(file_path)
            elif ext in (".docx", ".doc"):
                raw_text = cls._extract_docx_text(file_path)
            else:
                # Try raw text read
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()

            if not raw_text.strip():
                return {"success": False, "error": "No readable text extracted from document."}

            return cls.analyze_text(raw_text, filename=os.path.basename(file_path))

        except Exception as e:
            logger.exception(f"[ResumeParser] Failed to parse {file_path}: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _extract_pdf_text(cls, file_path: str) -> str:
        """Extract text from PDF using pypdf / pdfplumber or fallback string extraction."""
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except ImportError:
            pass

        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                if text.strip():
                    return text
        except ImportError:
            pass

        # Fallback binary text scrape
        with open(file_path, "rb") as f:
            content = f.read()
        # Simple ASCII text extraction from PDF stream
        strings = re.findall(b"[\x20-\x7E]{4,}", content)
        return "\n".join(s.decode("latin1", errors="ignore") for s in strings)

    @classmethod
    def _extract_docx_text(cls, file_path: str) -> str:
        """Extract text from DOCX using python-docx or fallback."""
        try:
            import docx
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            pass

        # Fallback zip read for docx
        import zipfile
        import xml.etree.ElementTree as ET
        try:
            with zipfile.ZipFile(file_path) as z:
                xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            texts = [node.text for node in tree.iter() if node.text]
            return " ".join(texts)
        except Exception:
            return ""

    @classmethod
    def analyze_text(cls, text: str, filename: str = "") -> Dict[str, Any]:
        """Analyzes parsed resume text to extract candidate details and claims."""
        # 1. Contact / Name heuristics
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        candidate_name = lines[0] if lines else "Candidate"
        if len(candidate_name) > 40 or any(char in candidate_name for char in "@/:;"):
            candidate_name = "Candidate"

        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        email = email_match.group(0) if email_match else ""

        # 2. Extract Technologies & Skills
        found_skills = []
        for tech in cls.TECH_PATTERNS:
            pattern = r"\b" + re.escape(tech) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                found_skills.append(tech)

        # 3. Extract Claims & Projects
        claims: List[ResumeClaim] = []
        for i, skill in enumerate(found_skills):
            claim = ResumeClaim(
                claim_id=f"claim_{i+1}",
                category="technology",
                text=f"{skill} experience",
                keywords=[skill.lower()]
            )
            claims.append(claim)

        # Look for bullet points with action verbs
        bullet_matches = re.findall(r"(?:•|\-|\*|\d+\.)\s*([A-Z][^\n\.\?!]{20,150}[\.\?!])", text)
        for j, b in enumerate(bullet_matches[:8]):
            # Extract keywords
            b_words = [w.lower() for w in re.findall(r"\b\w{4,}\b", b)]
            claim = ResumeClaim(
                claim_id=f"proj_claim_{j+1}",
                category="project",
                text=b.strip(),
                keywords=b_words[:6]
            )
            claims.append(claim)

        return {
            "success": True,
            "filename": filename,
            "candidate_name": candidate_name,
            "candidate_email": email,
            "skills": found_skills,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "category": c.category,
                    "text": c.text,
                    "keywords": c.keywords,
                    "status": c.status
                }
                for c in claims
            ],
            "raw_text": text[:2000]
        }


class ResumeClaimTracker:
    """Tracks resume claims during a live interview against spoken transcript."""

    def __init__(self, claims_data: Optional[List[Dict[str, Any]]] = None):
        self.claims: List[ResumeClaim] = []
        if claims_data:
            for item in claims_data:
                self.claims.append(ResumeClaim(
                    claim_id=item.get("claim_id", f"c_{len(self.claims)}"),
                    category=item.get("category", "skill"),
                    text=item.get("text", ""),
                    keywords=item.get("keywords", []),
                    status=item.get("status", "UNEXPLORED"),
                    evidence_snippet=item.get("evidence_snippet", ""),
                    evidence_timestamp=item.get("evidence_timestamp")
                ))

    def evaluate_transcript_segment(self, speaker: str, text: str, timestamp: float) -> List[ResumeClaim]:
        """Checks if speech covers any unexplored resume claims. Returns newly updated claims."""
        updated = []
        text_lower = text.lower()

        for claim in self.claims:
            if claim.status in ("DISCUSSED", "VALIDATED"):
                continue

            # Check keyword match
            matches = sum(1 for kw in claim.keywords if kw in text_lower)
            if matches > 0:
                claim.status = "DISCUSSED" if speaker == "candidate" else "MENTIONED"
                claim.evidence_snippet = text[:120]
                claim.evidence_timestamp = timestamp
                updated.append(claim)
                logger.info(f"[ResumeTracker] Claim '{claim.text}' marked as {claim.status} at {timestamp}")

        return updated

    def get_summary(self) -> Dict[str, Any]:
        """Returns coverage statistics and claim lists."""
        total = len(self.claims)
        discussed = sum(1 for c in self.claims if c.status in ("DISCUSSED", "VALIDATED"))
        mentioned = sum(1 for c in self.claims if c.status == "MENTIONED")
        unexplored = sum(1 for c in self.claims if c.status == "UNEXPLORED")

        return {
            "total_claims": total,
            "discussed_count": discussed,
            "mentioned_count": mentioned,
            "unexplored_count": unexplored,
            "coverage_pct": (discussed / total * 100.0) if total > 0 else 0.0,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "category": c.category,
                    "text": c.text,
                    "status": c.status,
                    "evidence_snippet": c.evidence_snippet,
                    "evidence_timestamp": c.evidence_timestamp
                }
                for c in self.claims
            ]
        }
