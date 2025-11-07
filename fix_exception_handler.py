#!/usr/bin/env python3
"""
Fix the overly broad exception handler in load_store_config_for_user_safe_key
Change: except Exception: -> except json.JSONDecodeError as e:
Add logging to see what error occurs
"""
import sys

app_py_path = '/var/www/pizza-hut-tv/app.py'

# Read the file
with open(app_py_path, 'r') as f:
    lines = f.readlines()

# Find and fix line 3473 (index 3472)
target_line_num = 3473
if len(lines) >= target_line_num:
    original_line = lines[target_line_num - 1]
    
    if 'except Exception:' in original_line and '# Corrupt' in lines[target_line_num]:
        # Change Exception to json.JSONDecodeError and add 'as e'
        lines[target_line_num - 1] = original_line.replace(
            'except Exception:',
            'except json.JSONDecodeError as e:'
        )
        
        # Insert logging line right after the exception (line 3474, before the comment)
        indent = '        '
        log_line = f'{indent}logging.error(f"⚠️ Config load failed for {{safe_key}}: {{type(e).__name__}}: {{e}}")\n'
        lines.insert(target_line_num, log_line)
        
        print(f'✓ Fixed line {target_line_num}: except Exception: -> except json.JSONDecodeError as e:')
        print(f'✓ Added logging at line {target_line_num + 1}')
    else:
        print(f'✗ Line {target_line_num} does not match expected pattern')
        print(f'  Line content: {original_line.strip()}')
        sys.exit(1)
else:
    print(f'✗ File has fewer than {target_line_num} lines')
    sys.exit(1)

# Write back
with open(app_py_path, 'w') as f:
    f.writelines(lines)

print('✓ app.py updated successfully')
print('\nNow only JSON decode errors will reset the config.')
print('Other errors (file locks, permissions, etc.) will NOT destroy data.')
