from __future__ import annotations

from io import BytesIO
from typing import Any
from typing import TYPE_CHECKING
from dataclasses import dataclass
from collections import Counter

if TYPE_CHECKING:
    from PIL import Image as PILImage

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None


@dataclass
class ColorInfo:
    """Dominant colors extracted from image."""
    dominant_color: tuple[int, int, int]  # RGB
    primary_colors: list[tuple[int, int, int]]
    color_names: list[str]


@dataclass
class ImageFeatures:
    """Features extracted from image."""
    colors: ColorInfo
    dimensions: tuple[int, int]
    aspect_ratio: float
    average_brightness: float
    attributes: dict[str, Any]


class ImageProcessor:
    """Processes images to extract visual features."""

    # Common color names and their RGB ranges
    COLOR_NAMES = {
        "red": ((255, 0, 0), "أحمر"),
        "blue": ((0, 0, 255), "أزرق"),
        "green": ((0, 128, 0), "أخضر"),
        "black": ((0, 0, 0), "أسود"),
        "white": ((255, 255, 255), "أبيض"),
        "yellow": ((255, 255, 0), "أصفر"),
        "orange": ((255, 165, 0), "برتقالي"),
        "purple": ((128, 0, 128), "بنفسجي"),
        "pink": ((255, 192, 203), "وردي"),
        "brown": ((165, 42, 42), "بني"),
        "gray": ((128, 128, 128), "رمادي"),
        "beige": ((245, 245, 220), "بيج"),
        "navy": ((0, 0, 128), "أزرق داكن"),
        "gold": ((255, 215, 0), "ذهبي"),
        "silver": ((192, 192, 192), "فضي"),
    }

    def __init__(self, max_width: int = 512, max_height: int = 512):
        self.max_width = max_width
        self.max_height = max_height

    def process_image_file(self, image_file) -> ImageFeatures:
        """
        Process an image file or file-like object.
        
        Args:
            image_file: Django ImageField file or file-like object
            
        Returns:
            ImageFeatures with extracted information
        """
        if Image is None or np is None:
            raise RuntimeError("PIL and numpy are required for image processing")

        try:
            image_data = image_file.read() if hasattr(image_file, "read") else image_file
            image = Image.open(BytesIO(image_data) if isinstance(image_data, bytes) else image_data)
        except Exception as exc:
            raise ValueError(f"Failed to open image: {exc}")

        return self.process_image(image)

    def process_image(self, image: "PILImage.Image") -> ImageFeatures:
        """
        Process a PIL Image object.
        
        Args:
            image: PIL Image object
            
        Returns:
            ImageFeatures with extracted information
        """
        if Image is None or np is None:
            raise RuntimeError("PIL and numpy are required for image processing")

        # Resize while maintaining aspect ratio
        image.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Extract features
        colors = self._extract_colors(image)
        dimensions = image.size  # (width, height)
        aspect_ratio = dimensions[0] / max(dimensions[1], 1)
        brightness = self._calculate_brightness(image)

        attributes = {
            "color_ar": colors.color_names[0] if colors.color_names else "متعدد الألوان",
            "color_en": "multi-color" if not colors.color_names else colors.color_names[0].lower(),
            "brightness": "bright" if brightness > 200 else "dark" if brightness < 100 else "medium",
            "has_pattern": self._detect_pattern(image),
        }

        return ImageFeatures(
            colors=colors,
            dimensions=dimensions,
            aspect_ratio=aspect_ratio,
            average_brightness=brightness,
            attributes=attributes,
        )

    def _extract_colors(self, image: "PILImage.Image") -> ColorInfo:
        """Extract dominant colors from image."""
        if np is None:
            raise RuntimeError("numpy is required for color extraction")

        # Resize for color analysis
        small_image = image.resize((50, 50), Image.Resampling.LANCZOS)
        pixels = np.array(small_image).reshape(-1, 3)

        # Find dominant color using k-means clustering
        dominant_color = tuple(pixels.mean(axis=0).astype(int))

        # Get 5 dominant colors
        pixel_colors = [tuple(pixel) for pixel in pixels]
        color_counts = Counter(pixel_colors)
        primary_colors = [color for color, _ in color_counts.most_common(5)]

        # Map to color names
        color_names = []
        for color in primary_colors:
            name = self._find_nearest_color_name(color)
            if name and name not in color_names:
                color_names.append(name)
            if len(color_names) >= 3:
                break

        return ColorInfo(
            dominant_color=dominant_color,
            primary_colors=primary_colors[:5],
            color_names=color_names,
        )

    def _find_nearest_color_name(self, rgb: tuple[int, int, int]) -> str | None:
        """Find the nearest color name for an RGB tuple."""
        min_distance = float("inf")
        nearest_name = None

        for name, (reference_rgb, _) in self.COLOR_NAMES.items():
            distance = sum((a - b) ** 2 for a, b in zip(rgb, reference_rgb))
            if distance < min_distance:
                min_distance = distance
                nearest_name = name

        return nearest_name if min_distance < 50000 else None

    def _calculate_brightness(self, image: "PILImage.Image") -> float:
        """Calculate average brightness of image."""
        if np is None:
            raise RuntimeError("numpy is required for brightness calculation")

        pixels = np.array(image)
        # Convert RGB to grayscale using standard formula
        grayscale = 0.299 * pixels[:, :, 0] + 0.587 * pixels[:, :, 1] + 0.114 * pixels[:, :, 2]
        return float(grayscale.mean())

    def _detect_pattern(self, image: "PILImage.Image") -> bool:
        """Simple pattern detection based on color variance."""
        if np is None:
            raise RuntimeError("numpy is required for pattern detection")

        pixels = np.array(image)
        # Calculate variance - high variance suggests pattern
        variance = pixels.var()
        return variance > 5000  # Threshold for pattern detection


def color_to_category_hint(color_names: list[str]) -> str:
    """
    Map colors to product category hints.
    
    Examples:
        ['red', 'gold'] -> 'accessories'
        ['brown', 'leather'] -> 'bags'
    """
    if not color_names:
        return "general"

    primary_color = color_names[0].lower() if color_names else ""

    # Simple heuristics
    if primary_color in {"red", "pink", "gold"}:
        return "fashion-accessories"
    elif primary_color in {"brown", "black"}:
        return "bags-footwear"
    elif primary_color in {"blue", "green"}:
        return "apparel"
    elif primary_color in {"gold", "silver"}:
        return "jewelry"

    return "general"
