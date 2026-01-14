"""
Application configuration module.

Centralized settings for easy feature toggles and customization.
Modify this file to enable/disable features without changing core logic.
"""

from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """
    Main application configuration.

    Toggle features on/off by setting boolean flags.
    Customize behavior by modifying values.
    """

    # === Feature Toggles ===
    enable_quran_detection: bool = True
    enable_hadith_detection: bool = True
    enable_auto_highlight: bool = True
    enable_progress_tracking: bool = True
    enable_export: bool = True

    # === UI Settings ===
    app_title: str = "Islamic Text Annotation Tool"
    paragraphs_per_page: int = 10  # For pagination (0 = show all)
    show_detection_confidence: bool = False  # Future feature

    # === Detection Settings ===
    min_surah_number: int = 1
    max_surah_number: int = 114
    min_ayah_number: int = 1
    max_ayah_number: int = 286  # Al-Baqarah has most ayahs

    # === Export Settings ===
    export_format: str = "json"  # Currently only json supported
    include_unreviewed: bool = True
    pretty_print_json: bool = True

    # === Debug Settings ===
    debug_mode: bool = False
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR


@dataclass
class ColorConfig:
    """Color scheme configuration for highlights."""

    quran_bg: str = "#d4edda"
    quran_text: str = "#155724"
    hadith_bg: str = "#cce5ff"
    hadith_text: str = "#004085"
    reviewed_bg: str = "#f8f9fa"
    pending_bg: str = "#ffffff"


# Global config instances (import and modify as needed)
app_config = AppConfig()
color_config = ColorConfig()


def get_config() -> AppConfig:
    """Get the current app configuration."""
    return app_config


def get_colors() -> ColorConfig:
    """Get the current color configuration."""
    return color_config
