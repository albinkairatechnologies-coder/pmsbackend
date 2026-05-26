import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    modified = False
    
    for i, line in enumerate(lines):
        # Match 'bdm' or "bdm" and verify 'bdm_head' or "bdm_head" is not already in this line
        if ('\'bdm\'' in line or '"bdm"' in line) and ('bdm_head' not in line):
            # Do replacement for single quotes
            new_line = line.replace('\'bdm\'', '\'bdm\', \'bdm_head\'')
            # Do replacement for double quotes
            new_line = new_line.replace('"bdm"', '"bdm", "bdm_head"')
            
            if new_line != line:
                lines[i] = new_line
                modified = True
                print(f"[{os.path.basename(filepath)}:{i+1}] Changed: {line.strip()} -> {new_line.strip()}")

    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

def main():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_dir = os.path.join(backend_dir, 'app')
    
    print(f"Scanning python files in {app_dir} to automatically add 'bdm_head' support...")
    for root, dirs, files in os.walk(app_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                process_file(filepath)
                
    print("\nFinish scanning and modifying roles.")

if __name__ == '__main__':
    main()
