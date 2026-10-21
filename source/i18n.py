# © 2026 uglywolf — GPL-3.0
"""화면·로그 글을 설정 언어(atom_config.json 의 language)로 고른다.

아톰은 한국인만 쓰는 게 아니다 — 영어권 사용자도 한글채팅 없이 혼자 쓴다(2026-10-21 사용자).
사람이 읽는 글은 한국어만 적지 말고 T("한국어", "English") 로 둘 다 적을 것.
"""
LANG = "ko"


def T(ko, en):
    return en if LANG == "en" else ko
