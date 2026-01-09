"""
LLM-based Reference Detector
Uses Gemini (primary) or GPT-4o-mini (fallback) to detect prose references.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
import streamlit as st

# Try importing Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Try importing OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


DETECTION_PROMPT = """Analyze the following Islamic text and extract any Quran or Hadith references.

Look for:
1. **Quran references** - Both explicit (e.g., "3:195", "Surah Al-Baqarah") and prose mentions (e.g., "the verse about patience", "where Allah says about forgiveness")
2. **Hadith references** - Both explicit (e.g., "Bukhari 123") and prose mentions (e.g., "the Prophet said about patience", "a famous hadith about knowledge")

For each reference found, provide:
- type: "quran" or "hadith"
- explicit: true if clearly stated (like "3:195"), false if implied/prose
- surah (for Quran): number if known, null if only topic mentioned
- ayah (for Quran): number if known, null if only topic mentioned
- collection (for Hadith): name if known, null if not
- number (for Hadith): number if known, null if not
- topic: what the verse/hadith is about (e.g., "patience", "prayer")
- matched_text: the exact text in the passage that refers to this

Return JSON array. If no references found, return empty array [].

TEXT TO ANALYZE:
{text}

Return ONLY valid JSON array, no other text."""


class LLMDetector:
    """LLM-based detector for prose Islamic references."""

    def __init__(self, gemini_key: Optional[str] = None, openai_key: Optional[str] = None):
        self.gemini_key = gemini_key or os.getenv("GOOGLE_API_KEY")
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.gemini_model = None
        self.openai_client = None

        # Initialize Gemini if available
        if GEMINI_AVAILABLE and self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                st.warning(f"Gemini init failed: {e}")

        # Initialize OpenAI if available
        if OPENAI_AVAILABLE and self.openai_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_key)
            except Exception as e:
                st.warning(f"OpenAI init failed: {e}")

    def detect_references(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect Islamic references in text using LLM.

        Args:
            text: Text to analyze

        Returns:
            List of detected references
        """
        # Skip if text is too short
        if len(text.strip()) < 20:
            return []

        # Try Gemini first
        if self.gemini_model:
            result = self._detect_with_gemini(text)
            if result is not None:
                return result

        # Fallback to OpenAI
        if self.openai_client:
            result = self._detect_with_openai(text)
            if result is not None:
                return result

        # No LLM available
        return []

    def _detect_with_gemini(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Use Gemini to detect references."""
        try:
            prompt = DETECTION_PROMPT.format(text=text[:2000])  # Limit text length

            response = self.gemini_model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 1024,
                }
            )

            # Parse JSON response
            response_text = response.text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            refs = json.loads(response_text)

            # Validate and standardize
            return self._standardize_refs(refs)

        except Exception as e:
            # Log but don't crash
            return None

    def _detect_with_openai(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Use OpenAI to detect references."""
        try:
            prompt = DETECTION_PROMPT.format(text=text[:2000])

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes Islamic texts. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1024
            )

            response_text = response.choices[0].message.content.strip()

            # Extract JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            refs = json.loads(response_text)
            return self._standardize_refs(refs)

        except Exception as e:
            return None

    def _standardize_refs(self, refs: List[Dict]) -> List[Dict[str, Any]]:
        """Standardize LLM output to expected format."""
        if not isinstance(refs, list):
            return []

        standardized = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue

            ref_type = ref.get("type", "").lower()

            if ref_type == "quran":
                standardized.append({
                    "type": "quran",
                    "detection": "llm",
                    "explicit": ref.get("explicit", False),
                    "surah": ref.get("surah"),
                    "ayah_start": ref.get("ayah") or ref.get("ayah_start"),
                    "ayah_end": ref.get("ayah_end"),
                    "topic": ref.get("topic", ""),
                    "matched_text": ref.get("matched_text", ""),
                    "verified": False,
                    "needs_verification": not ref.get("explicit", False)
                })
            elif ref_type == "hadith":
                standardized.append({
                    "type": "hadith",
                    "detection": "llm",
                    "explicit": ref.get("explicit", False),
                    "collection": ref.get("collection"),
                    "number": ref.get("number"),
                    "topic": ref.get("topic", ""),
                    "matched_text": ref.get("matched_text", ""),
                    "verified": False,
                    "needs_verification": True  # Always needs verification for hadith
                })

        return standardized

    @property
    def is_available(self) -> bool:
        """Check if any LLM is available."""
        return bool(self.gemini_model or self.openai_client)

    @property
    def active_model(self) -> str:
        """Get the name of the active model."""
        if self.gemini_model:
            return "Gemini 1.5 Flash"
        elif self.openai_client:
            return "GPT-4o-mini"
        return "None"


def get_llm_detector() -> LLMDetector:
    """Get or create LLMDetector instance."""
    if 'llm_detector' not in st.session_state:
        st.session_state.llm_detector = LLMDetector()
    return st.session_state.llm_detector


def detect_prose_references(text: str) -> List[Dict[str, Any]]:
    """
    Convenience function to detect prose references.

    Args:
        text: Text to analyze

    Returns:
        List of detected references
    """
    detector = get_llm_detector()
    if detector.is_available:
        return detector.detect_references(text)
    return []
