#!/usr/bin/env python3
"""Generate static OG image for CMMC Watch"""

from PIL import Image, ImageDraw, ImageFont
import os


def create_og_image():
    """Create a branded 1200x630 OG image."""

    # Image dimensions (standard OG size)
    width, height = 1200, 630

    # Colors (matching site theme)
    bg_dark = (15, 23, 42)  # Slate 900
    accent_primary = (99, 102, 241)  # Indigo 500 #6366f1
    accent_secondary = (139, 92, 246)  # Purple 500 #8b5cf6
    text_white = (255, 255, 255)
    text_muted = (148, 163, 184)  # Slate 400

    # Create base image with gradient
    img = Image.new("RGB", (width, height), bg_dark)
    draw = ImageDraw.Draw(img)

    # Create gradient background (top-left to bottom-right)
    for y in range(height):
        for x in range(width):
            # Calculate gradient factor
            factor = (x / width * 0.3) + (y / height * 0.3)
            factor = min(factor, 0.6)

            # Blend from dark to slightly lighter with accent tint
            r = int(bg_dark[0] + (accent_primary[0] - bg_dark[0]) * factor * 0.15)
            g = int(bg_dark[1] + (accent_primary[1] - bg_dark[1]) * factor * 0.15)
            b = int(bg_dark[2] + (accent_primary[2] - bg_dark[2]) * factor * 0.2)

            img.putpixel((x, y), (r, g, b))

    draw = ImageDraw.Draw(img)

    # Add decorative elements - gradient accent bar at top
    for x in range(width):
        factor = x / width
        r = int(accent_primary[0] + (accent_secondary[0] - accent_primary[0]) * factor)
        g = int(accent_primary[1] + (accent_secondary[1] - accent_primary[1]) * factor)
        b = int(accent_primary[2] + (accent_secondary[2] - accent_primary[2]) * factor)
        for y in range(6):
            img.putpixel((x, y), (r, g, b))

    # Add decorative circles/dots pattern
    for i in range(8):
        x_pos = 950 + (i % 4) * 60
        y_pos = 450 + (i // 4) * 60
        radius = 4
        draw.ellipse(
            [x_pos - radius, y_pos - radius, x_pos + radius, y_pos + radius],
            fill=(*accent_primary, 80),
        )

    # Try to load fonts, fall back to default if not available
    try:
        # Try system fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        font_large = None
        font_medium = None
        font_small = None

        for font_path in font_paths:
            if os.path.exists(font_path):
                font_large = ImageFont.truetype(font_path, 72)
                font_medium = ImageFont.truetype(font_path, 32)
                font_small = ImageFont.truetype(font_path, 24)
                break

        if not font_large:
            raise Exception("No font found")

    except Exception:
        # Use default font
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw site name
    site_name = "CMMC Watch"
    draw.text((80, 200), site_name, font=font_large, fill=text_white)

    # Draw accent underline under site name
    draw.rectangle([80, 290, 480, 296], fill=accent_primary)

    # Draw tagline
    tagline = "CMMC & DIB Compliance News"
    draw.text((80, 320), tagline, font=font_medium, fill=text_muted)

    # Draw description
    description = "Defense Industrial Base news aggregated daily"
    draw.text((80, 380), description, font=font_small, fill=text_muted)

    # Draw source badges
    sources = ["FedScoop", "DefenseScoop", "NextGov", "GovCon", "CISA"]
    badge_x = 80
    badge_y = 450
    badge_padding = 12
    badge_spacing = 15

    for source in sources:
        # Calculate badge width based on text
        try:
            bbox = draw.textbbox((0, 0), source, font=font_small)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(source) * 10

        badge_width = text_width + badge_padding * 2

        # Draw badge background
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + 36],
            radius=6,
            fill=(30, 41, 59),  # Slate 800
        )

        # Draw badge text
        draw.text(
            (badge_x + badge_padding, badge_y + 6),
            source,
            font=font_small,
            fill=text_muted,
        )

        badge_x += badge_width + badge_spacing

    # Draw "Updated Daily" indicator
    draw.text(
        (80, 540), "Updated Daily at 6 AM EST", font=font_small, fill=accent_primary
    )

    # Add corner accent
    draw.polygon(
        [(width, 0), (width - 150, 0), (width, 150)], fill=(*accent_secondary, 30)
    )

    # Save image
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "public", "og-image.png"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"Created OG image: {output_path}")

    # Also create a smaller version for Twitter
    twitter_img = img.resize((1200, 600), Image.Resampling.LANCZOS)
    twitter_path = os.path.join(
        os.path.dirname(__file__), "..", "public", "twitter-image.png"
    )
    twitter_img.save(twitter_path, "PNG", optimize=True)
    print(f"Created Twitter image: {twitter_path}")

    return output_path


if __name__ == "__main__":
    create_og_image()
