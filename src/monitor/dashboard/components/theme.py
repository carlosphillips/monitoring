"""Professional theme configuration for Breach Pivot Dashboard.

Defines colors, typography, spacing, and styling constants for a modern
investment app aesthetic. Consistent with institutional financial dashboards
(clean, data-focused, professional).

Color Palette:
- Breach directions: RED (lower) / BLUE (upper) per financial risk convention
- Backgrounds: Light grays, whites for clarity
- Text: Dark grays for readability
- Accents: Professional blues for interactive elements

Typography:
- Headers: Bold, clean sans-serif
- Body: Clear, readable sizes with adequate spacing
- Monospace: For numeric data and code blocks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ColorPalette:
    """Breach pivot dashboard color palette."""

    # Breach directions (critical)
    breach_lower: str = "#d32f2f"  # Red: lower breaches (underperformance)
    breach_upper: str = "#1976d2"  # Blue: upper breaches (outperformance)

    # Background and neutral
    bg_primary: str = "#ffffff"  # Pure white background
    bg_secondary: str = "#f5f5f5"  # Light gray for sections
    bg_tertiary: str = "#fafafa"  # Very light gray for hover/alt states
    border_light: str = "#e0e0e0"  # Light gray borders

    # Text colors
    text_primary: str = "#212121"  # Dark gray (high contrast)
    text_secondary: str = "#666666"  # Medium gray (secondary text)
    text_muted: str = "#999999"  # Light gray (muted/helper text)
    text_inverse: str = "#ffffff"  # White text on dark backgrounds

    # Interactive elements
    primary_action: str = "#1976d2"  # Blue for buttons
    primary_hover: str = "#1565c0"  # Darker blue on hover
    success: str = "#388e3c"  # Green for positive values
    warning: str = "#f57c00"  # Orange for warnings
    error: str = "#d32f2f"  # Red for errors

    # Charts and visualizations
    chart_grid: str = "#e0e0e0"  # Grid lines
    chart_background: str = "#ffffff"  # Chart background


@dataclass
class Typography:
    """Typography settings for dashboard."""

    # Font family (sans-serif for clean, modern look)
    font_family: str = "'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif"
    font_family_mono: str = "'Courier New', 'Monaco', monospace"

    # Font sizes (in rem)
    size_xs: float = 0.75  # 12px
    size_sm: float = 0.875  # 14px
    size_base: float = 1.0  # 16px
    size_lg: float = 1.125  # 18px
    size_xl: float = 1.25  # 20px
    size_2xl: float = 1.5  # 24px
    size_3xl: float = 1.875  # 30px

    # Font weights
    weight_normal: int = 400
    weight_semibold: int = 600
    weight_bold: int = 700

    # Line heights
    line_height_tight: float = 1.2
    line_height_normal: float = 1.5
    line_height_relaxed: float = 1.75


@dataclass
class Spacing:
    """Spacing constants (in pixels)."""

    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass
class BorderRadius:
    """Border radius constants (in pixels)."""

    sm: int = 2
    md: int = 4
    lg: int = 8
    xl: int = 12


@dataclass
class Shadows:
    """Box shadow definitions."""

    sm: str = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1)"


class ThemeConfig:
    """Centralized theme configuration.

    Usage:
        from monitor.dashboard.components.theme import THEME_CONFIG

        # Access colors
        breach_lower_color = THEME_CONFIG.colors.breach_lower
        header_font = THEME_CONFIG.typography.font_family

        # Apply to Dash layout
        html.Div(
            style={
                "color": THEME_CONFIG.colors.text_primary,
                "fontFamily": THEME_CONFIG.typography.font_family,
                "padding": f"{THEME_CONFIG.spacing.lg}px",
            }
        )
    """

    def __init__(self):
        """Initialize theme configuration."""
        self.colors = ColorPalette()
        self.typography = Typography()
        self.spacing = Spacing()
        self.border_radius = BorderRadius()
        self.shadows = Shadows()

    def get_breach_direction_color(self, direction: str) -> str:
        """Get color for breach direction.

        Args:
            direction: "upper" or "lower"

        Returns:
            Hex color code
        """
        if direction.lower() == "upper":
            return self.colors.breach_upper
        elif direction.lower() == "lower":
            return self.colors.breach_lower
        else:
            return self.colors.text_muted

    def get_style_header(self) -> dict:
        """Get style dict for dashboard header.

        Returns:
            Dict with style properties
        """
        return {
            "color": self.colors.text_primary,
            "fontFamily": self.typography.font_family,
            "fontSize": f"{self.typography.size_3xl}rem",
            "fontWeight": self.typography.weight_bold,
            "marginBottom": f"{self.spacing.md}px",
        }

    def get_style_label(self) -> dict:
        """Get style dict for form labels.

        Returns:
            Dict with style properties
        """
        return {
            "color": self.colors.text_primary,
            "fontFamily": self.typography.font_family,
            "fontSize": f"{self.typography.size_sm}rem",
            "fontWeight": self.typography.weight_semibold,
            "marginBottom": f"{self.spacing.sm}px",
        }

    def get_style_text_muted(self) -> dict:
        """Get style dict for muted/helper text.

        Returns:
            Dict with style properties
        """
        return {
            "color": self.colors.text_muted,
            "fontFamily": self.typography.font_family,
            "fontSize": f"{self.typography.size_sm}rem",
        }

    def get_style_card(self) -> dict:
        """Get style dict for card/container background.

        Returns:
            Dict with style properties
        """
        return {
            "backgroundColor": self.colors.bg_secondary,
            "borderRadius": f"{self.border_radius.md}px",
            "padding": f"{self.spacing.lg}px",
            "boxShadow": self.shadows.sm,
        }


# Global theme instance
THEME_CONFIG = ThemeConfig()


# ============================================================================
# CSS Classes & Stylesheet
# ============================================================================


def get_custom_css() -> str:
    """Get custom CSS for dashboard styling.

    Returns:
        CSS string ready for <style> tag
    """
    colors = THEME_CONFIG.colors
    typography = THEME_CONFIG.typography
    spacing = THEME_CONFIG.spacing

    css = f"""
    /* Base styles */
    body {{
        font-family: {typography.font_family};
        color: {colors.text_primary};
        background-color: {colors.bg_primary};
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: {colors.text_primary};
        font-weight: {typography.weight_bold};
    }}

    h1 {{ font-size: {typography.size_3xl}rem; }}
    h2 {{ font-size: {typography.size_2xl}rem; }}
    h3 {{ font-size: {typography.size_xl}rem; }}
    h4 {{ font-size: {typography.size_lg}rem; }}
    h5 {{ font-size: {typography.size_base}rem; }}

    /* Text colors */
    .text-primary {{ color: {colors.text_primary}; }}
    .text-secondary {{ color: {colors.text_secondary}; }}
    .text-muted {{ color: {colors.text_muted}; }}

    /* Form controls */
    .form-control {{
        border: 1px solid {colors.border_light};
        border-radius: {THEME_CONFIG.border_radius.md}px;
        padding: {spacing.md}px {spacing.md}px;
        font-family: {typography.font_family};
        font-size: {typography.size_sm}rem;
        color: {colors.text_primary};
    }}

    .form-control:focus {{
        border-color: {colors.primary_action};
        box-shadow: 0 0 0 0.2rem rgba(25, 118, 210, 0.25);
    }}

    /* Labels */
    label {{
        color: {colors.text_primary};
        font-weight: {typography.weight_semibold};
        margin-bottom: {spacing.sm}px;
    }}

    /* Buttons */
    .btn {{
        border-radius: {THEME_CONFIG.border_radius.md}px;
        font-weight: {typography.weight_semibold};
        padding: {spacing.sm}px {spacing.lg}px;
    }}

    .btn-primary {{
        background-color: {colors.primary_action};
        border-color: {colors.primary_action};
        color: {colors.text_inverse};
    }}

    .btn-primary:hover {{
        background-color: {colors.primary_hover};
        border-color: {colors.primary_hover};
    }}

    /* Cards and containers */
    .card {{
        border: 1px solid {colors.border_light};
        border-radius: {THEME_CONFIG.border_radius.lg}px;
        box-shadow: {THEME_CONFIG.shadows.sm};
    }}

    /* Dashboard-specific classes */
    .breach-direction-upper {{
        color: {colors.breach_upper};
        font-weight: {typography.weight_bold};
    }}

    .breach-direction-lower {{
        color: {colors.breach_lower};
        font-weight: {typography.weight_bold};
    }}

    /* Grid backgrounds */
    .bg-light {{
        background-color: {colors.bg_secondary};
    }}

    .border {{
        border: 1px solid {colors.border_light} !important;
    }}

    .border-top {{
        border-top: 1px solid {colors.border_light} !important;
    }}

    /* Responsive utilities */
    @media (max-width: 768px) {{
        .container-fluid {{
            padding-left: {spacing.md}px;
            padding-right: {spacing.md}px;
        }}
    }}
    """

    return css
