"""
text_normalizer.py — 제로폭/유니코드 정규화 (DOCX·PDF 공통)

- 제로폭 문자 탐지 및 제거. 발견 시 사유 "ZERO_WIDTH_CHARS".
- (보너스) Base64로 의심되는 긴 문자열 탐지 → 디코딩 시도 → 사람이 읽는
  문자열이 나오면 사유 "ENCODED_TEXT". 시간 여유용, 없어도 됨.
"""

import base64
import re

# 제로폭 및 비가시 서식 문자
ZERO_WIDTH_CHARS = {
    "​": "ZERO WIDTH SPACE",
    "‌": "ZERO WIDTH NON-JOINER",
    "‍": "ZERO WIDTH JOINER",
    "﻿": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "⁠": "WORD JOINER",
    "᠎": "MONGOLIAN VOWEL SEPARATOR",
}

_ZW_PATTERN = re.compile("[" + "".join(ZERO_WIDTH_CHARS.keys()) + "]")

# Base64 후보: 24자 이상의 base64 알파벳 연속
_B64_PATTERN = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def find_zero_width(text):
    """
    text 안의 제로폭 문자를 찾는다.
    반환: {"count": int, "kinds": [사람이 읽는 이름...], "cleaned": 제거된 문자열}
          제로폭이 없으면 count == 0.
    """
    if not text:
        return {"count": 0, "kinds": [], "cleaned": text or ""}

    found = _ZW_PATTERN.findall(text)
    kinds = sorted({ZERO_WIDTH_CHARS[ch] for ch in found})
    cleaned = _ZW_PATTERN.sub("", text)
    return {"count": len(found), "kinds": kinds, "cleaned": cleaned}


def strip_zero_width(text):
    """제로폭 문자를 제거한 문자열만 반환 (간편 함수)."""
    if not text:
        return text or ""
    return _ZW_PATTERN.sub("", text)


def find_encoded_text(text):
    """
    (보너스) Base64로 의심되는 긴 문자열을 찾아 디코딩을 시도한다.
    디코딩 결과가 사람이 읽을 만한 텍스트(출력 가능 문자 위주)면 반환.
    반환: [{"encoded": ..., "decoded": ...}, ...]  (없으면 빈 리스트)
    """
    if not text:
        return []

    results = []
    for match in _B64_PATTERN.finditer(text):
        candidate = match.group(0)
        # base64는 길이가 4의 배수여야 정상 디코딩
        if len(candidate) % 4 != 0:
            continue
        try:
            raw = base64.b64decode(candidate, validate=True)
            decoded = raw.decode("utf-8")
        except Exception:
            continue
        # 디코딩 결과가 대부분 출력 가능 문자인지 확인 (바이너리 오탐 방지)
        printable = sum(1 for c in decoded if c.isprintable() or c.isspace())
        if decoded and printable / len(decoded) >= 0.9:
            results.append({"encoded": candidate, "decoded": decoded})
    return results


if __name__ == "__main__":
    # 간단한 자체 점검
    sample = "정상​텍스트‍숨김"
    print(find_zero_width(sample))
    print(find_encoded_text("aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Q="))
