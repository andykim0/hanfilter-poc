"""
pdf_detector.py — PDF 구조 파싱 + 은닉 탐지

pdfplumber로 페이지별 page.chars(문자 단위 리스트)를 순회한다.
각 char에는 색상(non_stroking_color)·폰트크기(size)·좌표(x0/x1/top/bottom)가 있다.

검사 항목:
  - HIDDEN_WHITE_TEXT : char 색상이 흰색(1,1,1 또는 그레이스케일 1)
  - TINY_FONT         : char size가 임계값(TINY_FONT_PT) 이하
  - OFFPAGE_TEXT      : char 좌표가 페이지 경계 밖 (보너스)

주의:
  - 색상 표현이 그레이스케일(단일 값)일 수도, RGB/CMYK(튜플)일 수도 있으니 모두 처리.
  - 연속된 의심 char는 단어/문장으로 묶어 리포트한다 (문자 하나씩 출력 금지).
"""

import pdfplumber

try:
    from .text_normalizer import find_zero_width
except ImportError:
    from text_normalizer import find_zero_width

TINY_FONT_PT = 4.0        # 4pt 이하면 초소형으로 판정
_COLOR_EPS = 0.02         # 흰색 판정 허용 오차


def _is_white(color):
    """non_stroking_color 값이 흰색인지 판정. 그레이스케일/RGB/CMYK 모두 처리."""
    if color is None:
        return False
    # 그레이스케일: 단일 숫자 (1.0 = 흰색)
    if isinstance(color, (int, float)):
        return color >= 1.0 - _COLOR_EPS
    # 튜플/리스트
    if isinstance(color, (tuple, list)):
        if len(color) == 1:
            return color[0] >= 1.0 - _COLOR_EPS
        if len(color) == 3:  # RGB → 모두 1.0 이면 흰색
            return all(c >= 1.0 - _COLOR_EPS for c in color)
        if len(color) == 4:  # CMYK → 모두 0 이면 흰색
            return all(c <= _COLOR_EPS for c in color)
    return False


def _flush(group, page_num, reason, findings):
    """연속 의심 char 그룹을 하나의 finding으로 묶어 추가."""
    if not group:
        return
    text = "".join(ch["text"] for ch in group)
    if not text.strip():
        return
    if reason == "TINY_FONT":
        size = group[0].get("size") or 0
        text = f"{size:.1f}pt: {text}"
    findings.append({
        "reason": reason,
        "location": f"page {page_num}",
        "text": text.strip(),
    })


def detect(path):
    """
    PDF 파일을 검사해 findings 리스트를 반환한다.
    각 finding: {"reason", "location", "text"}
    """
    findings = []

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            width, height = page.width, page.height

            white_group, tiny_group, offpage_group = [], [], []
            page_text_parts = []

            for ch in page.chars:
                page_text_parts.append(ch.get("text", ""))

                # 흰색 텍스트
                if _is_white(ch.get("non_stroking_color")):
                    white_group.append(ch)
                else:
                    _flush(white_group, page_num, "HIDDEN_WHITE_TEXT", findings)
                    white_group = []

                # 초소형 폰트
                size = ch.get("size")
                if size is not None and size <= TINY_FONT_PT:
                    tiny_group.append(ch)
                else:
                    _flush(tiny_group, page_num, "TINY_FONT", findings)
                    tiny_group = []

                # 페이지 밖 좌표 (보너스): 문자가 페이지 경계 밖으로 나감
                x0, x1 = ch.get("x0", 0), ch.get("x1", 0)
                top, bottom = ch.get("top", 0), ch.get("bottom", 0)
                if x1 < 0 or x0 > width or bottom < 0 or top > height:
                    offpage_group.append(ch)
                else:
                    _flush(offpage_group, page_num, "OFFPAGE_TEXT", findings)
                    offpage_group = []

            # 페이지 끝에서 남은 그룹 flush
            _flush(white_group, page_num, "HIDDEN_WHITE_TEXT", findings)
            _flush(tiny_group, page_num, "TINY_FONT", findings)
            _flush(offpage_group, page_num, "OFFPAGE_TEXT", findings)

            # 제로폭 문자 검사 (페이지 전체 텍스트 대상)
            page_text = "".join(page_text_parts)
            zw = find_zero_width(page_text)
            if zw["count"] > 0:
                findings.append({
                    "reason": "ZERO_WIDTH_CHARS",
                    "location": f"page {page_num}",
                    "text": f"{zw['count']}개 제로폭 문자 ({', '.join(zw['kinds'])})",
                })

    return findings


if __name__ == "__main__":
    import sys
    for f in detect(sys.argv[1]):
        print(f)
