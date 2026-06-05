"""YAML 프롬프트 로더 (config/prompts/*).

[설계] 프롬프트를 코드 밖(YAML)에 두고 {{ var }} 치환만 지원하는 최소 로더.
Jinja2 같은 템플릿 엔진은 필요해질 때 도입한다(YAGNI).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

# app/utils/prompts.py → 리포 루트 /config/prompts
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "config" / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> dict:
    """'graphrag/entity_extraction' → 해당 YAML 을 dict 로 로드(프로세스당 1회)."""
    path = _PROMPTS_DIR / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render(template: str, **variables: object) -> str:
    """'{{ var }}' / '{{var}}' 플레이스홀더 치환. 누락 변수는 그대로 둔다."""
    for key, value in variables.items():
        for token in (f"{{{{ {key} }}}}", f"{{{{{key}}}}}"):
            template = template.replace(token, str(value))
    return template
