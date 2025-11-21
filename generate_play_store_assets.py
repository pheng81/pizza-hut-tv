"""
Generate Google Play Store graphics for Everyday Advertise app
Creates: App icon, Feature graphic, TV banner
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_gradient(width, height):
    """Create pink to blue gradient background"""
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # Gradient colors (pink -> purple -> blue)
    start_color = (255, 45, 132)  # #ff2d84
    mid_color = (181, 68, 255)    # #b544ff
    end_color = (60, 108, 255)    # #3c6cff
    
    for y in range(height):
        # Calculate position (0.0 to 1.0)
        ratio = y / height
        
        if ratio < 0.5:
            # First half: pink to purple
            local_ratio = ratio * 2
            r = int(start_color[0] + (mid_color[0] - start_color[0]) * local_ratio)
            g = int(start_color[1] + (mid_color[1] - start_color[1]) * local_ratio)
            b = int(start_color[2] + (mid_color[2] - start_color[2]) * local_ratio)
        else:
            # Second half: purple to blue
            local_ratio = (ratio - 0.5) * 2
            r = int(mid_color[0] + (end_color[0] - mid_color[0]) * local_ratio)
            g = int(mid_color[1] + (end_color[1] - mid_color[1]) * local_ratio)
            b = int(mid_color[2] + (end_color[2] - mid_color[2]) * local_ratio)
        
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    return img

def create_rounded_rectangle_mask(size, radius):
    """Create a rounded rectangle mask"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask

def create_app_icon(size=512):
    """Create 512x512 app icon with EP text"""
    print(f"Creating {size}x{size} app icon...")
    
    # Create gradient background
    img = create_gradient(size, size)
    
    # Create rounded rectangle mask (18% radius)
    radius = int(size * 0.18)
    mask = create_rounded_rectangle_mask((size, size), radius)
    
    # Apply mask
    img.putalpha(mask)
    
    # Add EP text in bold, chunky font
    draw = ImageDraw.Draw(img)
    
    # Try multiple bold fonts
    font_size = int(size * 0.55)
    font = None
    
    # List of bold fonts to try (in order of preference)
    bold_fonts = [
        "arialbd.ttf",      # Arial Bold
        "ariblk.ttf",       # Arial Black
        "impact.ttf",       # Impact
        "BRLNSR.TTF",       # Berlin Sans FB
        "GOTHICB.TTF",      # Century Gothic Bold
        "calibrib.ttf",     # Calibri Bold
        "seguisb.ttf",      # Segoe UI Bold
    ]
    
    for font_name in bold_fonts:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except:
            continue
    
    if font is None:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    text = "EP"
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center text
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - bbox[1]
    
    # Draw text with white fill
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    return img

def create_feature_graphic():
    """Create 1024x500 feature graphic"""
    print("Creating 1024x500 feature graphic...")
    
    width, height = 1024, 500
    
    # Create gradient background
    img = create_gradient(width, height)
    draw = ImageDraw.Draw(img)
    
    # Add EA logo on the left
    logo_size = 300
    logo = create_app_icon(logo_size)
    # Remove alpha for pasting
    logo_rgb = Image.new('RGB', (logo_size, logo_size), (255, 45, 132))
    logo_rgb.paste(logo, (0, 0), logo)
    img.paste(logo_rgb, (50, (height - logo_size) // 2))
    
    # Add text on the right
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 80)
        subtitle_font = ImageFont.truetype("arial.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
    
    # Title - using EP branding
    title = "EveryDay Publish"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = width - title_width - 50
    title_y = 120
    draw.text((title_x, title_y), title, fill=(255, 255, 255), font=title_font)
    
    # Subtitle
    subtitle = "Digital Signage for Restaurants"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = width - subtitle_width - 50
    subtitle_y = title_y + 100
    draw.text((subtitle_x, subtitle_y), subtitle, fill=(255, 255, 255), font=subtitle_font)
    
    # Tagline
    tagline = "Manage screens remotely • Real-time updates"
    tagline_bbox = draw.textbbox((0, 0), tagline, font=subtitle_font)
    tagline_width = tagline_bbox[2] - tagline_bbox[0]
    tagline_x = width - tagline_width - 50
    tagline_y = subtitle_y + 60
    draw.text((tagline_x, tagline_y), tagline, fill=(255, 255, 255, 200), font=subtitle_font)
    
    return img

def create_tv_banner():
    """Create 1280x720 TV banner"""
    print("Creating 1280x720 TV banner...")
    
    width, height = 1280, 720
    
    # Create gradient background
    img = create_gradient(width, height)
    draw = ImageDraw.Draw(img)
    
    # Add EA logo in center-left
    logo_size = 400
    logo = create_app_icon(logo_size)
    logo_rgb = Image.new('RGB', (logo_size, logo_size), (255, 45, 132))
    logo_rgb.paste(logo, (0, 0), logo)
    img.paste(logo_rgb, (100, (height - logo_size) // 2))
    
    # Add text on the right
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 110)
        subtitle_font = ImageFont.truetype("arial.ttf", 50)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
    
    # Title - using EP branding
    title = "EveryDay Publish"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = width - title_width - 100
    title_y = 200
    draw.text((title_x, title_y), title, fill=(255, 255, 255), font=title_font)
    
    # Subtitle
    subtitle = "Digital Signage Solution"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = width - subtitle_width - 100
    subtitle_y = title_y + 140
    draw.text((subtitle_x, subtitle_y), subtitle, fill=(255, 255, 255), font=subtitle_font)
    
    # Features
    features = "Remote Management • Multi-Screen • Real-Time Updates"
    features_bbox = draw.textbbox((0, 0), features, font=subtitle_font)
    features_width = features_bbox[2] - features_bbox[0]
    features_x = width - features_width - 100
    features_y = subtitle_y + 80
    draw.text((features_x, features_y), features, fill=(255, 255, 255, 200), font=subtitle_font)
    
    return img

def main():
    """Generate all Play Store assets"""
    print("=" * 60)
    print("Generating Google Play Store Assets")
    print("=" * 60)
    
    # Create output directory
    output_dir = "play_store_assets"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nOutput directory: {output_dir}/\n")
    
    # 1. App Icon (512x512)
    icon = create_app_icon(512)
    icon_path = os.path.join(output_dir, "app_icon_512x512.png")
    icon.save(icon_path, "PNG")
    print(f"✓ Saved: {icon_path}")
    
    # 2. Feature Graphic (1024x500)
    feature = create_feature_graphic()
    feature_path = os.path.join(output_dir, "feature_graphic_1024x500.png")
    feature.save(feature_path, "PNG")
    print(f"✓ Saved: {feature_path}")
    
    # 3. TV Banner (1280x720)
    banner = create_tv_banner()
    banner_path = os.path.join(output_dir, "tv_banner_1280x720.png")
    banner.save(banner_path, "PNG")
    print(f"✓ Saved: {banner_path}")
    
    print("\n" + "=" * 60)
    print("✓ All assets generated successfully!")
    print("=" * 60)
    print(f"\nFiles created in: {os.path.abspath(output_dir)}/")
    print("\nNext steps:")
    print("1. Review the generated images")
    print("2. Take screenshots from your running app")
    print("3. Upload to Google Play Console")

if __name__ == "__main__":
    main()
