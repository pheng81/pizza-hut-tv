#!/usr/bin/env python3
"""
Quick fix for syntax error in webplayer_style_pi_client.py
"""
import re

# Read the file
with open('webplayer_style_pi_client.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Fix the malformed emoji character
content = re.sub(r'�️', '📐', content)
content = re.sub(r'�', '📐', content)

# Write back
with open('webplayer_style_pi_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed syntax error - replaced malformed emoji characters")