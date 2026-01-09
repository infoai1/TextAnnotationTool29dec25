"""
Sunnah.com API Integration
Fetches hadith text, validates references, and performs text matching.
"""

import httpx
import re
from typing import Dict, Any, Optional, List, Tuple
import streamlit as st
from difflib import SequenceMatcher

SUNNAH_API_BASE = "https://api.sunnah.com/v1"

# Collection name mappings to sunnah.com collection names
COLLECTION_MAP = {
    "sahih al-bukhari": "bukhari",
    "sahih bukhari": "bukhari",
    "bukhari": "bukhari",
    "sahih muslim": "muslim",
    "muslim": "muslim",
    "sunan at-tirmidhi": "tirmidhi",
    "tirmidhi": "tirmidhi",
    "sunan abi dawood": "abudawud",
    "sunan abu dawood": "abudawud",
    "abu dawood": "abudawud",
    "sunan an-nasa'i": "nasai",
    "nasa'i": "nasai",
    "nasai": "nasai",
    "sunan ibn majah": "ibnmajah",
    "ibn majah": "ibnmajah",
    "muwatta malik": "malik",
    "malik": "malik",
    "musnad ahmad": "ahmad",
    "ahmad": "ahmad",
}


class HadithAPI:
    """Client for sunnah.com API"""

    def __init__(self, api_key: Optional[str] = None):
        self.base_url = SUNNAH_API_BASE
        self.api_key = api_key
        self.timeout = 15.0
        # Cache for hadith data
        if 'hadith_cache' not in st.session_state:
            st.session_state.hadith_cache = {}

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication if available."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _normalize_collection(self, collection: str) -> Optional[str]:
        """Convert collection name to sunnah.com format."""
        if not collection:
            return None
        normalized = collection.lower().strip()
        return COLLECTION_MAP.get(normalized, normalized)

    def get_hadith_by_number(self, collection: str, hadith_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a hadith by collection and number.

        Note: sunnah.com uses different numbering systems.
        This tries the hadith number directly.

        Args:
            collection: Collection name
            hadith_number: Hadith number

        Returns:
            Hadith data or None
        """
        collection_key = self._normalize_collection(collection)
        if not collection_key:
            return None

        cache_key = f"{collection_key}:{hadith_number}"

        # Check cache
        if cache_key in st.session_state.hadith_cache:
            return st.session_state.hadith_cache[cache_key]

        try:
            url = f"{self.base_url}/hadiths/{collection_key}:{hadith_number}"

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=self._get_headers())

                if response.status_code == 200:
                    data = response.json()
                    result = self._parse_hadith_response(data, collection_key)
                    st.session_state.hadith_cache[cache_key] = result
                    return result

                elif response.status_code == 404:
                    return {
                        "found": False,
                        "collection": collection,
                        "number": hadith_number,
                        "error": "Hadith not found with this number"
                    }

        except Exception as e:
            return {
                "found": False,
                "collection": collection,
                "number": hadith_number,
                "error": str(e)
            }

        return None

    def search_hadith_text(self, text: str, collection: Optional[str] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for hadith by text content.

        Args:
            text: Text to search for
            collection: Optional collection to limit search
            limit: Maximum results

        Returns:
            List of matching hadiths
        """
        # Clean search text
        search_text = re.sub(r'\s+', ' ', text.strip())

        # Take first 100 chars for search
        if len(search_text) > 100:
            search_text = search_text[:100]

        try:
            url = f"{self.base_url}/hadiths"
            params = {
                "q": search_text,
                "limit": limit
            }

            if collection:
                collection_key = self._normalize_collection(collection)
                if collection_key:
                    params["collection"] = collection_key

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params, headers=self._get_headers())

                if response.status_code == 200:
                    data = response.json()
                    hadiths = data.get("data", [])

                    results = []
                    for h in hadiths:
                        parsed = self._parse_hadith_response(h)
                        if parsed.get("found"):
                            # Calculate similarity score
                            similarity = self._calculate_similarity(
                                text,
                                parsed.get("english", "") + " " + parsed.get("arabic", "")
                            )
                            parsed["similarity_score"] = similarity
                            results.append(parsed)

                    # Sort by similarity
                    results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
                    return results

        except Exception as e:
            st.warning(f"Hadith search error: {e}")

        return []

    def _parse_hadith_response(self, data: Dict, collection_key: str = "") -> Dict[str, Any]:
        """Parse hadith API response into standardized format."""
        if not data:
            return {"found": False}

        # Handle both single hadith and list item formats
        hadith = data.get("hadith", data)

        return {
            "found": True,
            "collection": hadith.get("collection", collection_key),
            "book_number": hadith.get("bookNumber"),
            "hadith_number": hadith.get("hadithNumber"),
            "arabic": hadith.get("body", ""),
            "english": hadith.get("bodyEnglish", hadith.get("englishNarration", "")),
            "grade": hadith.get("grade", ""),
            "grades": hadith.get("grades", []),
            "chapter": hadith.get("chapterTitle", ""),
            "narrator": hadith.get("englishNarrator", ""),
            "sunnah_url": f"https://sunnah.com/{hadith.get('collection', collection_key)}/{hadith.get('hadithNumber', '')}"
        }

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity score (0-1)."""
        # Clean and normalize texts
        t1 = re.sub(r'[^\w\s]', '', text1.lower())
        t2 = re.sub(r'[^\w\s]', '', text2.lower())

        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, t1, t2).ratio()

    def fuzzy_match_hadith(self, maulana_text: str, collection: Optional[str] = None,
                          threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Find hadith that matches the given text using fuzzy matching.

        Args:
            maulana_text: Text from Maulana's book
            collection: Optional collection to limit search
            threshold: Minimum similarity score (0-1)

        Returns:
            List of potential matches with similarity scores
        """
        # Search sunnah.com
        results = self.search_hadith_text(maulana_text, collection, limit=10)

        # Filter by threshold
        matches = [r for r in results if r.get("similarity_score", 0) >= threshold]

        # Add match status
        for match in matches:
            score = match.get("similarity_score", 0)
            if score >= 0.9:
                match["match_quality"] = "high"
            elif score >= 0.7:
                match["match_quality"] = "medium"
            else:
                match["match_quality"] = "low"

        return matches

    def get_collection_info(self, collection: str) -> Optional[Dict[str, Any]]:
        """Get information about a hadith collection."""
        collection_key = self._normalize_collection(collection)
        if not collection_key:
            return None

        try:
            url = f"{self.base_url}/collections/{collection_key}"
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=self._get_headers())
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return None


def get_hadith_api(api_key: Optional[str] = None) -> HadithAPI:
    """Get or create HadithAPI instance."""
    if 'hadith_api' not in st.session_state:
        st.session_state.hadith_api = HadithAPI(api_key)
    return st.session_state.hadith_api


# Grade descriptions
HADITH_GRADES = {
    "sahih": {"label": "Sahih (Authentic)", "color": "green"},
    "hasan": {"label": "Hasan (Good)", "color": "blue"},
    "da'if": {"label": "Da'if (Weak)", "color": "orange"},
    "daif": {"label": "Da'if (Weak)", "color": "orange"},
    "maudu": {"label": "Maudu' (Fabricated)", "color": "red"},
    "mawdu": {"label": "Maudu' (Fabricated)", "color": "red"},
}


def format_hadith_grade(grade: str) -> Tuple[str, str]:
    """Format hadith grade for display."""
    if not grade:
        return "Unknown", "gray"

    grade_lower = grade.lower().strip()
    for key, info in HADITH_GRADES.items():
        if key in grade_lower:
            return info["label"], info["color"]

    return grade, "gray"
