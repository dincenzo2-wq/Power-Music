import re

with open('music_organizer.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Replace existing hardcoded 'Montserrat' with FONTS['title']
code = code.replace('family="Montserrat"', 'family=FONTS["title"]')

# 2. Find all ctk.CTkFont(...) that don't already have 'family=' and inject it
# This regex looks for 'ctk.CTkFont(' followed by anything that isn't 'family=' until the closing ')'
code = re.sub(r'ctk\.CTkFont\((?!.*?family=)(.*?)\)', r'ctk.CTkFont(family=FONTS["text"], \1)', code)

# Clean up any weird comma issues like `family=FONTS["text"], )` -> `family=FONTS["text"])`
code = code.replace(', )', ')')

# 3. For specific header labels, if they got "text", change them to "title"
# First we find all 'self.something_label = ctk.CTkLabel(' and replace 'FONTS["text"]' with 'FONTS["title"]' inside them
title_labels = ['nav_label', 'add_cat_label', 'file_list_label', 'logo_label']

for label in title_labels:
    # A bit hacky but simple string replace for the lines we care about.
    # We find the string 'self.nav_label = ctk.CTkLabel' and just process line by line
    pass

# Actually, doing it line by line is safer
lines = code.split('\n')
for i, line in enumerate(lines):
    if any(lbl in line for lbl in title_labels) and 'CTkLabel' in line:
        if 'FONTS["text"]' in line:
            lines[i] = line.replace('FONTS["text"]', 'FONTS["title"]')
            
    # Settings dialog headers
    if 'CTkLabel(dialog' in line and ('weight="bold"' in line or 'size=13' in line):
        if 'FONTS["text"]' in line:
            lines[i] = line.replace('FONTS["text"]', 'FONTS["title"]')

code = '\n'.join(lines)

with open('music_organizer.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Fonts updated!")
