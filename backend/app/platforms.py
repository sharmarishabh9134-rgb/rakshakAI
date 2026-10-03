"""Platform directory and conservative verification endpoints.

Registry lookups deliberately return unavailable until an authoritative live
provider is configured. Directory examples are not endorsements or proof of
current registration.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.url_safety import analyze_url, URLRejected

router = APIRouter(prefix="/api/platforms", tags=["platforms"])
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "official_platforms.json"
SEBI_REGISTRY = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes"
DISCLAIM="RakshakAI does not recommend or endorse investment platforms. This check is informational and does not establish that a service or website is safe or fraudulent."

def platforms():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

class VerifyInput(BaseModel):
    platform_name: str = Field(default="", max_length=160)
    url: str = Field(default="", max_length=2000)
    registration_number: str = Field(default="", max_length=120)
    app_name: str = Field(default="", max_length=160)
    developer: str = Field(default="", max_length=160)

class SEBIRegistryAdapter:
    """Safe adapter shell: no scraping or fabricated registry results."""
    def searchByName(self, name: str): return self._unavailable(name)
    def searchByRegistrationNumber(self, number: str): return self._unavailable(number)
    def searchByIntermediaryType(self, intermediary_type: str): return self._unavailable(intermediary_type)
    def verifyRegistration(self, value: str): return self._unavailable(value)
    @staticmethod
    def _unavailable(query: str):
        return {"status":"UNAVAILABLE","query":query,"source":SEBI_REGISTRY,"message":"Live official verification is currently unavailable. Please verify directly through the official SEBI website."}

class RegistryVerificationService:
    def __init__(self): self.sebi = SEBIRegistryAdapter()
    def verify(self, data: VerifyInput):
        matched = None
        if data.url:
            try:
                observation = analyze_url(data.url)
            except (ValueError, URLRejected) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            host = (urlsplit(observation["url"]).hostname or "").lower()
            for item in platforms():
                official = (urlsplit(item["officialWebsite"]).hostname or "").lower()
                if host == official or host.endswith("." + official):
                    matched = item
                    break
        else:
            observation = None
        reg = self.sebi.verifyRegistration(data.registration_number or data.platform_name)
        indicators = []
        if data.url and not matched:
            indicators.append("The submitted domain did not match a directory example’s listed official domain.")
        if data.app_name or data.developer:
            indicators.append("App publisher details are not independently checked by a configured authoritative source.")
        checks = ["URL syntax and domain structure", "HTTPS scheme", "Directory official-domain comparison"]
        if data.registration_number: checks.append("SEBI registration lookup requested; live source unavailable")
        if observation and observation["indicators"]:
            indicators.extend(x["label"] + ": " + x["evidence"] for x in observation["indicators"])
        status = "INCONSISTENT" if data.url and not matched else "INCOMPLETE"
        return {"platform_name": data.platform_name or (matched["name"] if matched else ""),
          "official_website": matched["officialWebsite"] if matched else "",
          "verification_status": status, "registration_status":"UNAVAILABLE",
          "official_source":SEBI_REGISTRY,"checks_performed":checks,
          "risk_indicators":indicators,"evidence":(["Submitted domain matches the directory domain for " + matched["name"] + "."] if matched else []),
          "uncertainties":["Live official verification is currently unavailable.","Directory domain comparison does not verify ownership, registration, app publisher, or current site content."],
          "verification_steps":["Please verify directly through the official SEBI website.","Open the organization website by typing its address yourself.","Never share OTPs, PINs, passwords, or remote-access codes."],
          "domain_observations":observation,
          "disclaimer":DISCLAIM}

service = RegistryVerificationService()

@router.get("")
def list_platforms(): return platforms()

@router.get("/categories")
def list_categories(): return sorted({x["category"] for x in platforms()})

@router.get("/official-resources")
def official_resources():
    return [
      {"authority":"SEBI","purpose":"Securities market regulator information","url":"https://www.sebi.gov.in/"},
      {"authority":"SEBI Investor","purpose":"Investor education and support","url":"https://investor.sebi.gov.in/"},
      {"authority":"SEBI Recognised Intermediaries","purpose":"Search official intermediary records","url":SEBI_REGISTRY},
      {"authority":"SEBI SCORES","purpose":"Investor grievance redressal","url":"https://scores.sebi.gov.in/"},
      {"authority":"National Cyber Crime Reporting Portal","purpose":"Report cybercrime","url":"https://www.cybercrime.gov.in/"},
      {"authority":"Cyber Crime Suspect Reporting","purpose":"Report suspect identifiers","url":"https://cybercrime.gov.in/webform/cyber_suspect.aspx"},
      {"authority":"National Emergency","purpose":"Emergency assistance","phone":"112"},
      {"authority":"Cyber Financial Fraud Helpline","purpose":"Report financial cyber fraud promptly","phone":"1930"}]

@router.get("/{platform_id}")
def get_platform(platform_id: str):
    item = next((x for x in platforms() if x["id"] == platform_id), None)
    if not item: raise HTTPException(status_code=404, detail="Platform entry not found.")
    return item

@router.post("/verify")
def verify_platform(data: VerifyInput): return service.verify(data)

@router.post("/verify-url")
def verify_url(data: VerifyInput):
    if not data.url: raise HTTPException(status_code=422, detail="Enter a URL to verify.")
    return service.verify(data)

@router.post("/verify-registration")
def verify_registration(data: VerifyInput):
    return service.verify(data)
