"""
Skill Engine - 动态技能扫描和执行系统
- 扫描 skills/ 目录下的所有 skill.md 文件
- 自动注册为可用的 skill/expert
- 支持动态扩展：添加新的 skill 目录即可
"""
import os
import re
import json
from typing import List, Dict, Optional
from dataclasses import dataclass

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")


@dataclass
class SkillInfo:
    name: str
    display_name: str
    description: str
    icon: str
    system_prompt: str
    instructions: str
    md_content: str


def _parse_skill_md(content: str) -> Optional[SkillInfo]:
    """Parse a skill.md file into SkillInfo."""
    lines = content.split('\n')

    # Parse header comments (# name:, # display_name:, etc.)
    name = ""
    display_name = ""
    description = ""
    icon = "Sparkles"

    for line in lines[:10]:
        line = line.strip()
        if line.startswith("# name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("# display_name:"):
            display_name = line.split(":", 1)[1].strip()
        elif line.startswith("# description:"):
            description = line.split(":", 1)[1].strip()
        elif line.startswith("# icon:"):
            icon = line.split(":", 1)[1].strip()

    if not name:
        return None

    # Extract sections
    system_prompt = ""
    instructions = ""

    in_system_prompt = False
    in_instructions = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## System Prompt"):
            in_system_prompt = True
            in_instructions = False
            continue
        elif stripped.startswith("## Instructions"):
            in_system_prompt = False
            in_instructions = True
            continue
        elif stripped.startswith("## "):
            in_system_prompt = False
            in_instructions = False
            continue

        if in_system_prompt:
            system_prompt += line + "\n"
        elif in_instructions:
            instructions += line + "\n"

    return SkillInfo(
        name=name,
        display_name=display_name or name,
        description=description,
        icon=icon,
        system_prompt=system_prompt.strip(),
        instructions=instructions.strip(),
        md_content=content,
    )


def scan_skills() -> List[SkillInfo]:
    """Scan skills directory and return all available skills."""
    skills = []

    if not os.path.exists(SKILLS_DIR):
        return skills

    for entry in os.listdir(SKILLS_DIR):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue

        md_path = os.path.join(skill_dir, "skill.md")
        if not os.path.exists(md_path):
            continue

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            skill = _parse_skill_md(content)
            if skill:
                skills.append(skill)
        except Exception:
            continue

    return skills


def get_skill(name: str) -> Optional[SkillInfo]:
    """Get a specific skill by name."""
    for skill in scan_skills():
        if skill.name == name:
            return skill
    return None


def get_skill_list() -> List[Dict[str, str]]:
    """Get skill list for frontend dropdown."""
    return [
        {
            "name": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "icon": s.icon,
        }
        for s in scan_skills()
    ]
