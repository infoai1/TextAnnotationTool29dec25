"""
Quran.com API Integration
Fetches verse text and validates references.
"""

import httpx
from typing import Dict, Any, Optional, List
import streamlit as st

QURAN_API_BASE = "https://api.quran.com/api/v4"


class QuranAPI:
    """Client for Quran.com API"""

    def __init__(self):
        self.base_url = QURAN_API_BASE
        self.timeout = 10.0
        # Cache for verse data
        if 'quran_cache' not in st.session_state:
            st.session_state.quran_cache = {}

    def get_verse(self, surah: int, ayah: int, translation_id: int = 131) -> Optional[Dict[str, Any]]:
        """
        Fetch a single verse from Quran.com API.

        Args:
            surah: Surah number (1-114)
            ayah: Ayah number
            translation_id: Translation ID (131 = Sahih International, 85 = Abdul Haleem)

        Returns:
            Dictionary with verse data or None if not found
        """
        cache_key = f"{surah}:{ayah}:{translation_id}"

        # Check cache first
        if cache_key in st.session_state.quran_cache:
            return st.session_state.quran_cache[cache_key]

        try:
            # API endpoint for verse by key
            verse_key = f"{surah}:{ayah}"
            url = f"{self.base_url}/verses/by_key/{verse_key}"
            params = {
                "translations": translation_id,
                "fields": "text_uthmani,text_indopak"
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    verse = data.get("verse", {})

                    result = {
                        "surah": surah,
                        "ayah": ayah,
                        "verse_key": verse_key,
                        "arabic": verse.get("text_uthmani", ""),
                        "translation": "",
                        "valid": True
                    }

                    # Extract translation
                    translations = verse.get("translations", [])
                    if translations:
                        result["translation"] = translations[0].get("text", "")

                    # Cache the result
                    st.session_state.quran_cache[cache_key] = result
                    return result

                elif response.status_code == 404:
                    # Verse doesn't exist
                    result = {
                        "surah": surah,
                        "ayah": ayah,
                        "verse_key": verse_key,
                        "valid": False,
                        "error": "Verse not found"
                    }
                    st.session_state.quran_cache[cache_key] = result
                    return result

        except Exception as e:
            return {
                "surah": surah,
                "ayah": ayah,
                "valid": False,
                "error": str(e)
            }

        return None

    def get_verse_range(self, surah: int, ayah_start: int, ayah_end: int,
                        translation_id: int = 131) -> List[Dict[str, Any]]:
        """
        Fetch a range of verses.

        Args:
            surah: Surah number
            ayah_start: Starting ayah
            ayah_end: Ending ayah
            translation_id: Translation ID

        Returns:
            List of verse dictionaries
        """
        verses = []
        for ayah in range(ayah_start, ayah_end + 1):
            verse = self.get_verse(surah, ayah, translation_id)
            if verse:
                verses.append(verse)
        return verses

    def validate_reference(self, surah: int, ayah_start: int,
                          ayah_end: Optional[int] = None) -> Dict[str, Any]:
        """
        Validate a Quran reference.

        Args:
            surah: Surah number
            ayah_start: Starting ayah
            ayah_end: Ending ayah (optional)

        Returns:
            Validation result with verse text if valid
        """
        # First check basic bounds
        if surah < 1 or surah > 114:
            return {
                "valid": False,
                "error": f"Invalid surah number: {surah}. Must be 1-114."
            }

        # Fetch the verse(s)
        if ayah_end and ayah_end > ayah_start:
            verses = self.get_verse_range(surah, ayah_start, ayah_end)
            if not verses:
                return {"valid": False, "error": "Could not fetch verses"}

            # Check if all verses are valid
            invalid = [v for v in verses if not v.get("valid", False)]
            if invalid:
                return {
                    "valid": False,
                    "error": f"Invalid ayah(s): {[v['ayah'] for v in invalid]}"
                }

            return {
                "valid": True,
                "surah": surah,
                "ayah_start": ayah_start,
                "ayah_end": ayah_end,
                "verses": verses,
                "combined_translation": " ".join(v.get("translation", "") for v in verses)
            }
        else:
            verse = self.get_verse(surah, ayah_start)
            if not verse:
                return {"valid": False, "error": "Could not fetch verse"}

            return {
                "valid": verse.get("valid", False),
                "surah": surah,
                "ayah": ayah_start,
                "arabic": verse.get("arabic", ""),
                "translation": verse.get("translation", ""),
                "error": verse.get("error")
            }

    def get_surah_info(self, surah: int) -> Optional[Dict[str, Any]]:
        """Get information about a surah."""
        try:
            url = f"{self.base_url}/chapters/{surah}"
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    chapter = data.get("chapter", {})
                    return {
                        "id": surah,
                        "name_arabic": chapter.get("name_arabic", ""),
                        "name_simple": chapter.get("name_simple", ""),
                        "name_complex": chapter.get("name_complex", ""),
                        "verses_count": chapter.get("verses_count", 0),
                        "revelation_place": chapter.get("revelation_place", "")
                    }
        except Exception:
            pass
        return None


def get_quran_api() -> QuranAPI:
    """Get or create QuranAPI instance."""
    if 'quran_api' not in st.session_state:
        st.session_state.quran_api = QuranAPI()
    return st.session_state.quran_api
