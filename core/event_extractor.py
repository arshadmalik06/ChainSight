"""
Multimodal Event Extractor for ChainSight Agent using Google GenAI SDK.
Supports both structured text extraction and direct image advisory interpretation.
Falls back safely to structured rule extraction if GEMINI_API_KEY is not set or offline mode is enabled.
"""
import os
import json
import uuid
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path
from pydantic import ValidationError

from schemas import DisruptionEvent, DisruptionType, SeverityLevel, SourceType

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """
You are ChainSight's Disruption Event Extraction Engine.
Analyze the provided supply chain disruption report or advisory (text or image).
You must output ONLY valid JSON matching this schema:
{
  "event_id": "string (e.g. EVT-xxxx)",
  "event_type": "cyclone" | "port_congestion" | "supplier_shutdown" | "inland_flooding" | "shipment_delay" | "geopolitical" | "labor_strike" | "other",
  "description": "concise factual summary of the incident",
  "location": "specific port, city, or geographical hub (e.g. Shanghai, China / Los Angeles, CA, USA / Kaohsiung, Taiwan / Detroit, MI, USA)",
  "severity": "low" | "medium" | "high" | "critical",
  "start_time": "ISO timestamp or null if unknown",
  "expected_duration_hours": float,
  "affected_entity_types": ["port", "supplier", "plant", "distribution_centre", "customer"],
  "extraction_confidence": float between 0.0 and 1.0,
  "assumptions": ["list of assumptions made for uncertain parameters"],
  "requires_confirmation": boolean (true if key details like location or duration were ambiguous or unstated)
}
CRITICAL RULES:
1. Do not invent exact timestamps or certainty if absent from the document.
2. Mark requires_confirmation=true if the location or severity is ambiguous.
3. Return pure JSON without markdown backticks.
"""


def extract_event_rule_heuristic(text: str, source_type: SourceType = SourceType.TEXT) -> DisruptionEvent:
    """
    Deterministic rule-based extractor used when offline or without API key.
    Ensures end-to-end functionality even in isolated test environments.
    """
    text_lower = text.lower()
    event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"

    # Determine event type
    if "cyclone" in text_lower or "typhoon" in text_lower or "hurricane" in text_lower:
        etype = DisruptionType.CYCLONE
        dur = 48.0
        sev = SeverityLevel.HIGH
    elif "congestion" in text_lower or "berth" in text_lower or "anchor" in text_lower:
        etype = DisruptionType.PORT_CONGESTION
        dur = 72.0
        sev = SeverityLevel.HIGH
    elif "flood" in text_lower or "inland" in text_lower or "rain" in text_lower or "derailment" in text_lower or "rail" in text_lower or "washout" in text_lower:
        etype = DisruptionType.INLAND_FLOODING
        dur = 36.0
        sev = SeverityLevel.HIGH
    elif "shutdown" in text_lower or "factory" in text_lower or "fire" in text_lower:
        etype = DisruptionType.SUPPLIER_SHUTDOWN
        dur = 96.0
        sev = SeverityLevel.CRITICAL
    elif "strike" in text_lower or "labor" in text_lower or "walkout" in text_lower:
        etype = DisruptionType.LABOR_STRIKE
        dur = 48.0
        sev = SeverityLevel.HIGH
    else:
        etype = DisruptionType.SHIPMENT_DELAY
        dur = 24.0
        sev = SeverityLevel.LOW

    # Detect severity keywords
    if "critical" in text_lower or "emergency" in text_lower or "force majeure" in text_lower:
        sev = SeverityLevel.CRITICAL
    elif "moderate" in text_lower:
        sev = SeverityLevel.MEDIUM
    elif "minor" in text_lower:
        sev = SeverityLevel.LOW

    # Detect location
    loc = "Unknown Location"
    locations_map = {
        "shanghai": "Shanghai, China",
        "kaohsiung": "Kaohsiung, Taiwan",
        "los angeles": "Los Angeles, CA, USA",
        "long beach": "Long Beach, CA, USA",
        "busan": "Busan, South Korea",
        "detroit": "Detroit, MI, USA",
        "austin": "Austin, TX, USA",
        "chicago": "Chicago, IL, USA",
        "dallas": "Dallas, TX, USA",
        "rayong": "Rayong, Thailand",
        "yokohama": "Yokohama, Japan",
    }
    for k, v in locations_map.items():
        if k in text_lower:
            loc = v
            break

    req_confirm = loc == "Unknown Location"
    assumptions = []
    if req_confirm:
        assumptions.append("Location was not recognized in known supply chain hubs; requires human confirmation.")
    if "duration" not in text_lower and "hours" not in text_lower and "days" not in text_lower:
        assumptions.append(f"Estimated duration defaulted to {dur}h based on standard {etype.value} baseline.")

    return DisruptionEvent(
        event_id=event_id,
        event_type=etype,
        description=text.strip(),
        location=loc,
        severity=sev,
        expected_duration_hours=dur,
        affected_entity_types=["port"] if any(w in text_lower or w in loc.lower() for w in ["port", "terminal", "harbor", "berth"]) or etype == DisruptionType.PORT_CONGESTION else ["supplier"],
        source_type=source_type,
        extraction_confidence=0.88 if not req_confirm else 0.50,
        assumptions=assumptions,
        requires_confirmation=req_confirm,
    )


def extract_event_from_text(text: str) -> DisruptionEvent:
    """Extract disruption event from text, using Gemini GenAI SDK if key is configured, else fallback."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    offline = os.getenv("CHAINSIGHT_OFFLINE_MODE", "false").lower() == "true"
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    if not api_key or offline:
        logger.info("[EventExtractor] Using deterministic offline parser (No GEMINI_API_KEY or offline mode set).")
        return extract_event_rule_heuristic(text, SourceType.TEXT)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nUser Disruption Report:\n{text}"
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        data["source_type"] = SourceType.TEXT.value
        return DisruptionEvent.model_validate(data)

    except Exception as e:
        logger.warning(f"[EventExtractor] Gemini API call or validation failed ({e}). Falling back to heuristic.")
        event = extract_event_rule_heuristic(text, SourceType.TEXT)
        event.assumptions.append(f"Gemini API parse failed ({e}); parsed using deterministic rule engine.")
        return event


def extract_event_from_image(image_bytes: bytes, mime_type: str = "image/png") -> DisruptionEvent:
    """
    Extract disruption event from image advisory using Gemini Multimodal vision capabilities.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    offline = os.getenv("CHAINSIGHT_OFFLINE_MODE", "false").lower() == "true"
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    if not api_key or offline:
        logger.info("[EventExtractor] Gemini key missing or offline; producing placeholder for image advisory.")
        return DisruptionEvent(
            event_id=f"EVT-IMG-{uuid.uuid4().hex[:6].upper()}",
            event_type=DisruptionType.CYCLONE,
            description="Uploaded meteorological/port advisory image (Processed via offline baseline).",
            location="Shanghai, China",
            severity=SeverityLevel.HIGH,
            expected_duration_hours=48.0,
            affected_entity_types=["port"],
            source_type=SourceType.IMAGE_ADVISORY,
            extraction_confidence=0.75,
            assumptions=["Extracted via offline fallback fixture as GEMINI_API_KEY is not configured."],
            requires_confirmation=True,
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        prompt = (
            f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
            "Analyze the attached advisory screenshot/document. Extract all discernible supply-chain disruption information."
        )

        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, part],
        )

        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        data["source_type"] = SourceType.IMAGE_ADVISORY.value
        return DisruptionEvent.model_validate(data)

    except Exception as e:
        logger.warning(f"[EventExtractor] Gemini vision extraction failed ({e}). Returning safe advisory template.")
        return DisruptionEvent(
            event_id=f"EVT-IMG-ERR-{uuid.uuid4().hex[:6].upper()}",
            event_type=DisruptionType.OTHER,
            description=f"Image advisory could not be processed automatically: {e}",
            location="Unknown Location",
            severity=SeverityLevel.MEDIUM,
            expected_duration_hours=24.0,
            affected_entity_types=["port"],
            source_type=SourceType.IMAGE_ADVISORY,
            extraction_confidence=0.3,
            assumptions=["Vision inference failed; human review required."],
            requires_confirmation=True,
        )
