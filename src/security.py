from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from src.config import settings

security_scheme = HTTPBearer()

try:
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
except Exception:
    analyzer = None
    anonymizer = None

PII_ENTITIES = ("EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "CREDIT_CARD", "IP_ADDRESS")

def redact_pii(text: str) -> str:
    """Sanitizes PII tokens (emails, phones, credit cards) before LLM ingestion."""
    if not analyzer or not anonymizer:
        return text
    try:
        results = analyzer.analyze(text=text, language='en', entities=list(PII_ENTITIES))
        redacted = anonymizer.anonymize(text=text, analyzer_results=results)
        return redacted.text
    except Exception:
        return text

def verify_jwt(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> dict:
    """Enforces Role-Based Access Control via Bearer JWT."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        role = payload.get("role")
        if role not in ["admin", "analyst", "viewer"]:
            raise HTTPException(status_code=403, detail="Role unauthorized for gateway execution.")
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer authentication token."
        )
