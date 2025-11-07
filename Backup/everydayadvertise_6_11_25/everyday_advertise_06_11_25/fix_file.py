with open(r'C:\Users\toeng\Pizza Hut TV\ea_tv_pi.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines containing the undefined variable
fixed_lines = []
skip_next_lines = 0
for i, line in enumerate(lines):
    if 'current_has_mixed_media' in line:
        # Skip this line and the next 2 print lines
        skip_next_lines = 3
        continue
    if skip_next_lines > 0:
        skip_next_lines -= 1
        continue
    fixed_lines.append(line)

with open(r'C:\Users\toeng\Pizza Hut TV\ea_tv_pi.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("Fixed file - removed undefined variable reference")
