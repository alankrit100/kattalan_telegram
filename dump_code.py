import os

# Ignore heavy frontend and backend junk folders
ignore_dirs = ['.venv', '__pycache__', '.git', 'data', 'node_modules', '.svelte-kit', 'build', 'dist']

valid_extensions = ('.py', '.svelte', '.ts', '.js', '.css', '.html')
valid_configs = ('package.json', 'tailwind.config.js', 'tailwind.config.ts', 'svelte.config.js', 'vite.config.ts', '.env.example')

with open("latest_code.txt", "w", encoding="utf-8") as out_file:
    for root, dirs, files in os.walk("."):
        # Skip the junk folders
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            # Grab backend and frontend files
            if file.endswith(valid_extensions) or file in valid_configs:
                filepath = os.path.join(root, file)
                out_file.write(f"\n\n{'='*50}\nFILE: {filepath}\n{'='*50}\n")
                try:
                    with open(filepath, "r", encoding="utf-8") as in_file:
                        out_file.write(in_file.read())
                except Exception as e:
                    out_file.write(f"[Error reading file: {e}]\n")

print("✅ Success! Open latest_code.txt, copy everything, and paste it here.")