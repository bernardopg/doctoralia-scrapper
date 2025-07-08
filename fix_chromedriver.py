#!/usr/bin/env python3

import re

# Read the original file
with open("src/scraper.py", "r") as f:
    content = f.read()

# Add import after the other selenium imports
import_pattern = r"(from selenium\.webdriver\.common\.by import By\n)(from selenium\.webdriver\.support import expected_conditions as EC)"
import_replacement = r"\1from webdriver_manager.chrome import ChromeDriverManager\n\2"
content = re.sub(import_pattern, import_replacement, content)

# Replace the ChromeDriver detection logic
old_logic = r"""                # Encontrar ChromeDriver
                chromedriver_paths = \[
                    "/usr/bin/chromedriver",
                    "/usr/local/bin/chromedriver",
                    "chromedriver",
                \]

                chromedriver_binary = None
                for path in chromedriver_paths:
                    if os\.path\.exists\(path\) and os\.access\(path, os\.X_OK\):
                        chromedriver_binary = path
                        break
                    elif path == "chromedriver":
                        # Tenta usar chromedriver no PATH
                        chromedriver_binary = path
                        break

                if not chromedriver_binary:
                    self\.logger\.error\("ChromeDriver não encontrado"\)
                    return False"""

new_logic = """                # Use webdriver-manager to automatically manage ChromeDriver
                chromedriver_binary = ChromeDriverManager().install()"""

content = re.sub(old_logic, new_logic, content, flags=re.MULTILINE)

# Write the modified content back
with open("src/scraper.py", "w") as f:
    f.write(content)

print("Successfully updated scraper.py to use webdriver-manager")
