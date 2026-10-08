import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Prompt Injection Regular Expressions
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|earlier|above|before)\s+(instructions?|prompts?|commands?|directives?)",
    r"forget\s+(all\s+)?(previous|prior|earlier|above|before)\s+(instructions?|prompts?|commands?)",
    r"disregard\s+(all\s+)?(previous|prior|earlier|above|before)\s+(instructions?|prompts?|commands?)",
    r"override\s+(all\s+)?(previous|prior|earlier|above|before)\s+(instructions?|prompts?|commands?)",
    r"(what|tell|show|reveal|display|list|repeat|copy|print)\s+(are|is|was|were)\s+(your|the)\s+(system\s+)?(prompt|instructions?|directives?|commands?|rules?|guidelines?)",
    r"(what|tell|show|reveal|display|list|repeat|copy|print)\s+(your|the)\s+(original|initial|starting|first)\s+(system\s+)?(prompt|instructions?|directives?|commands?)",
    r"repeat\s+(everything|all|the)\s+(you\s+)?(were\s+)?(told|instructed|said|given)",
    r"you\s+(are|will\s+be|must\s+be|should\s+be)\s+(no\s+longer|not)\s+",
    r"you\s+(are|will\s+be|must\s+be|should\s+be)\s+(now|currently)\s+",
    r"act\s+as\s+(if\s+you\s+are\s+)?(a|an)\s+",
    r"pretend\s+(you\s+are\s+)?(to\s+be\s+)?(a|an)\s+",
    r"follow\s+(these|the|my|this)\s+(new\s+)?(instructions?|rules?|commands?)",
    r"execute\s+(these|the|my|this)\s+(instructions?|commands?|directives?)",
    r"<\|.*?\|>",
    r"\[INST\].*?\[/INST\]",
    r"<\|im_start\|>.*?<\|im_end\|>",
]

HIGH_CONFIDENCE_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?previous\s+instructions",
    r"what\s+are\s+your\s+system\s+prompts?",
    r"reveal\s+(your|the)\s+system\s+prompt",
    r"you\s+are\s+no\s+longer",
]


class Guardrails:
    """
    Guardrails service for input validation, prompt injection detection,
    and content safety.
    """

    @staticmethod
    def detect_prompt_injection(input_text: str) -> Dict[str, Any]:
        """Detect prompt injection attempts in input text."""
        if not input_text:
            return {"is_injection": False, "confidence": "low"}

        detected_patterns: List[str] = []
        confidence = "low"
        match_count = 0

        # Check high confidence patterns
        for pattern in HIGH_CONFIDENCE_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                detected_patterns.append(pattern)
                match_count += 1
                confidence = "high"

        # Check general patterns
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                if pattern not in detected_patterns:
                    detected_patterns.append(pattern)
                    match_count += 1

        if match_count == 0:
            return {"is_injection": False, "confidence": "low"}

        if confidence != "high":
            confidence = "high" if match_count >= 2 else "medium"

        is_injection = confidence in ("medium", "high")
        if is_injection:
            logger.warning(f"Prompt injection detected [confidence: {confidence}]: {detected_patterns}")

        return {
            "is_injection": is_injection,
            "confidence": confidence,
            "detected_patterns": detected_patterns,
        }

    @staticmethod
    def validate_input(input_text: str, max_length: int = 4000) -> Dict[str, Any]:
        """Validate input length and basic formatting."""
        if not input_text or not input_text.strip():
            return {"is_valid": False, "reason": "Input is empty"}

        if len(input_text) > max_length:
            return {"is_valid": False, "reason": f"Input exceeds max length of {max_length} characters"}

        return {"is_valid": True}
