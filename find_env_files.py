import os
from pathlib import Path

def find_env_files(start_path='.'):
    print("Searching for environment files...")
    print("-" * 50)
    
    root_dir = Path(start_path).resolve()
    print(f"Starting search from: {root_dir}\n")
    
    env_files = []
    for path in root_dir.rglob('*'):
        if path.name in ['.env', '.flaskenv', 'env', '.env.local', '.env.development']:
            env_files.append(path)
            
            # Try to read and print first line (safely)
            try:
                with open(path, 'r') as f:
                    first_line = next(f, '').strip()
                    if first_line and not first_line.startswith('#'):
                        first_line = '(contains sensitive data)'
            except:
                first_line = '(unable to read file)'
                
            print(f"Found: {path}")
            print(f"First line: {first_line}")
            print(f"File size: {path.stat().st_size} bytes")
            print()
    
    if not env_files:
        print("No environment files found!")
    
    return env_files

if __name__ == '__main__':
    find_env_files() 