import os
import re


def fix_json_filenames(directory):
    for filename in os.listdir(directory):
        # Check if the current file is a JSON file
        if filename.endswith(".json"):
            # Attempt to find a matching image file
            base_filename = filename[:-5]  # Remove '.json' extension
            # Handle specific pattern: move index before the extension
            # e.g., 'obj_attachment (20).jfif(3).json' -> 'obj_attachment (20)(3).jfif.json'
            pattern = re.compile(r"(.*) \((\d+)\)\.([a-zA-Z0-9]+)\((\d+)\)")
            match = pattern.match(base_filename)
            if match:
                intended_name = (
                    f"{match.group(1)} ({match.group(2)})(3).{match.group(3)}.json"
                )
                original_path = os.path.join(directory, filename)
                intended_path = os.path.join(directory, intended_name)
                if os.path.exists(original_path) and not os.path.exists(intended_path):
                    print(f"Renaming '{filename}' to '{intended_name}'")
                    os.rename(original_path, intended_path)
                else:
                    if os.path.exists(intended_path):
                        print(f"Target file already exists: {intended_path}")
                        with open(intended_path, 'r', encoding='utf-8') as file:
                            contents = file.read()
                            print(contents)
                    if not os.path.exists(original_path):
                        print(f"Original file does not exist: {original_path}")
            # else:
            # print(f"No match or not affected: {filename}")


# Replace 'your_directory_path' with the path to your directory containing the files
fix_json_filenames("temp")
