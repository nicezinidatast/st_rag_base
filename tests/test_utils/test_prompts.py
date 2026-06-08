"""utils/prompts: YAML 프롬프트 로더 테스트."""
from __future__ import annotations

from app.utils.prompts import load_prompt, render


def test_load_prompt_reads_graphrag_yaml():
    p = load_prompt("graphrag/entity_extraction")
    assert p["name"] == "entity_extraction"
    assert "{{ text }}" in p["user"]


def test_render_substitutes_both_spacings():
    assert render("질문: {{ query }} / {{query}}", query="수도?") == "질문: 수도? / 수도?"


def test_render_keeps_unknown_placeholders():
    assert render("{{ keep }}", other=1) == "{{ keep }}"
