import os
import re
import yaml
from pathlib import Path


def convert_skills(skills_dir: Path, output_dir: Path):
    if not skills_dir.exists():
        print(f"Skills directory does not exist: {skills_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    for root, _, files in os.walk(skills_dir):
        for file in files:
            if file.endswith(".md"):
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8")
                    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
                    if not match:
                        continue

                    frontmatter_text = match.group(1)
                    markdown_text = match.group(2)

                    metadata = yaml.safe_load(frontmatter_text)
                    if not metadata or "name" not in metadata:
                        continue

                    # Map PromptWise metadata to Copilot .agent.md spec
                    copilot_meta = {
                        "name": metadata["name"],
                        "description": metadata.get("description", ""),
                        "keywords": metadata.get("triggers", []),
                        "model": "gpt-4o"  # default mapping for copilot
                    }

                    output_content = (
                        "---\n" +
                        yaml.dump(copilot_meta, sort_keys=False) +
                        "---\n\n" +
                        markdown_text.strip() + "\n"
                    )

                    out_file = output_dir / f"{metadata['name']}.agent.md"
                    out_file.write_text(output_content, encoding="utf-8")
                    print(f"Converted {file_path.name} -> {out_file.name}")

                except Exception as e:
                    print(f"Failed to convert {file_path.name}: {e}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    skills_dir = project_root / "skills"
    output_dir = project_root / ".github" / "agents"
    print("Converting PromptWise skills to GitHub Copilot .agent.md format...")
    convert_skills(skills_dir, output_dir)
