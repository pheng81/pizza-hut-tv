#!/usr/bin/env python3
"""Test script to verify Pi mobile sync addon works"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test imports
try:
    import pygame
    logger.info("✅ pygame imported")
except ImportError as e:
    logger.error(f"❌ pygame import failed: {e}")
    sys.exit(1)

try:
    import qrcode
    logger.info("✅ qrcode imported")
except ImportError as e:
    logger.error(f"❌ qrcode import failed: {e}")
    sys.exit(1)

try:
    from PIL import Image
    logger.info("✅ PIL imported")
except ImportError as e:
    logger.error(f"❌ PIL import failed: {e}")
    sys.exit(1)

# Test creating a QR code
try:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data("https://everydayadvertise.com/webplayer/?session=test123")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    logger.info("✅ QR code created successfully")
except Exception as e:
    logger.error(f"❌ QR code creation failed: {e}")
    sys.exit(1)

# Test pygame init
try:
    pygame.init()
    logger.info("✅ pygame initialized")
except Exception as e:
    logger.error(f"❌ pygame init failed: {e}")
    sys.exit(1)

# Test converting PIL to pygame surface
try:
    import io
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    qr_surface = pygame.image.load(img_bytes)
    qr_surface = pygame.transform.scale(qr_surface, (300, 300))
    logger.info("✅ QR code converted to pygame surface")
    logger.info(f"   Surface size: {qr_surface.get_size()}")
except Exception as e:
    logger.error(f"❌ PIL to pygame conversion failed: {e}")
    sys.exit(1)

logger.info("✅✅✅ All tests passed! Mobile sync addon should work!")
