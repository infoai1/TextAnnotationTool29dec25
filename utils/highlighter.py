"""Text highlighter for Quran and Hadith references with configurable styling."""

from dataclasses import dataclass, field
from typing import Protocol
import html


@dataclass
class HighlightConfig:
    """
    Configuration for highlight styling.

    Modify these values to change colors/styles without touching logic.
    """
    quran_bg_color: str = "#d4edda"      # Light green
    quran_text_color: str = "#155724"    # Dark green
    hadith_bg_color: str = "#cce5ff"     # Light blue
    hadith_text_color: str = "#004085"   # Dark blue
    border_radius: str = "3px"
    padding: str = "2px 4px"


# Default config instance
DEFAULT_CONFIG = HighlightConfig()


class Reference(Protocol):
    """Protocol for reference objects (Quran or Hadith)."""
    start_pos: int
    end_pos: int
    matched_text: str


def _build_style(bg_color: str, text_color: str, config: HighlightConfig) -> str:
    """Build inline CSS style string."""
    return (
        f"background-color: {bg_color}; "
        f"color: {text_color}; "
        f"border-radius: {config.border_radius}; "
        f"padding: {config.padding};"
    )


def highlight_references(
    text: str,
    quran_refs: list[Reference],
    hadith_refs: list[Reference],
    config: HighlightConfig | None = None,
) -> str:
    """
    Apply HTML highlighting to detected references in text.

    Uses efficient list-based string building (O(n) instead of O(n²)).

    Args:
        text: Original paragraph text
        quran_refs: List of Quran reference objects
        hadith_refs: List of Hadith reference objects
        config: Optional custom highlight configuration

    Returns:
        HTML string with highlighted references
    """
    if config is None:
        config = DEFAULT_CONFIG

    if not quran_refs and not hadith_refs:
        return html.escape(text)

    # Merge and sort all references by position
    all_refs: list[tuple[int, int, str, str]] = []  # (start, end, type, style)

    quran_style = _build_style(config.quran_bg_color, config.quran_text_color, config)
    hadith_style = _build_style(config.hadith_bg_color, config.hadith_text_color, config)

    for ref in quran_refs:
        all_refs.append((ref.start_pos, ref.end_pos, "quran", quran_style))

    for ref in hadith_refs:
        all_refs.append((ref.start_pos, ref.end_pos, "hadith", hadith_style))

    # Sort by start position
    all_refs.sort(key=lambda x: x[0])

    # Build output using list (O(n) complexity)
    parts: list[str] = []
    last_end = 0

    for start, end, ref_type, style in all_refs:
        # Skip overlapping references
        if start < last_end:
            continue

        # Add text before this reference (escaped)
        if start > last_end:
            parts.append(html.escape(text[last_end:start]))

        # Add highlighted reference
        ref_text = html.escape(text[start:end])
        parts.append(f'<span class="ref-{ref_type}" style="{style}">{ref_text}</span>')
        last_end = end

    # Add remaining text after last reference
    if last_end < len(text):
        parts.append(html.escape(text[last_end:]))

    return ''.join(parts)


def highlight_single_ref(text: str, ref_type: str, config: HighlightConfig | None = None) -> str:
    """
    Highlight an entire text string as a reference.

    Args:
        text: Text to highlight
        ref_type: Either "quran" or "hadith"
        config: Optional custom configuration

    Returns:
        HTML span with appropriate styling
    """
    if config is None:
        config = DEFAULT_CONFIG

    if ref_type == "quran":
        style = _build_style(config.quran_bg_color, config.quran_text_color, config)
    else:
        style = _build_style(config.hadith_bg_color, config.hadith_text_color, config)

    return f'<span class="ref-{ref_type}" style="{style}">{html.escape(text)}</span>'
