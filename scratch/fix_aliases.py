import os
import glob

def safe_replace(pattern, replacement, path_glob):
    for f in glob.glob(path_glob, recursive=True):
        if os.path.isfile(f):
            with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
            if pattern in content:
                print(f"Updating {f}...")
                new_content = content.replace(pattern, replacement)
                with open(f, 'w', encoding='utf-8') as file:
                    file.write(new_content)

# Target dashboard components
safe_replace('@/lib/api', '../../lib/api', 'frontend/src/components/dashboard/*.jsx')
# Target chat components
safe_replace('@/lib/api', '../../lib/api', 'frontend/src/components/chat/*.jsx')
# Target UI components if any
safe_replace('@/lib/api', '../../lib/api', 'frontend/src/components/ui/*.jsx')
