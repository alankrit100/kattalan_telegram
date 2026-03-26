import os

ignore_dirs = ['.venv', '__pycache__', '.git', 'data']

with open("latest_code.txt", "w", encoding="utf-8") as out_file:
    for root, dirs, files in os.walk("."):
        # Skip the junk folders
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith(".py") or file.endswith(".env.example"):
                filepath = os.path.join(root, file)
                out_file.write(f"\n\n{'='*50}\nFILE: {filepath}\n{'='*50}\n")
                try:
                    with open(filepath, "r", encoding="utf-8") as in_file:
                        out_file.write(in_file.read())
                except Exception as e:
                    out_file.write(f"[Error reading file: {e}]\n")

print("✅ Success! Open latest_code.txt, copy everything, and paste it to the AI.")