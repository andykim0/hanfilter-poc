#!/usr/bin/env python3
"""
detect.py — HANFILTER PoC 메인 탐지기 (CLI 진입점)

문서 파일을 구조 레벨에서 파싱해, 사람 눈에 보이지 않게 숨겨진 텍스트
(흰색·초소형 폰트·숨김 속성·메타데이터·제로폭 문자)를 찾아낸다.
AI/LLM 없이 전부 결정론적 코드로 동작한다.

사용법:
    python detect.py samples/attack_hidden_white.docx
    python detect.py samples/                     # 폴더 전체 일괄 검사
    python detect.py samples/attack_metadata.docx --json report.json
"""

import argparse
import json
import os
import sys

from rich.console import Console
from rich.table import Table
from rich import box

from detectors import docx_detector, pdf_detector

# 사유 코드 → 사람이 읽는 한국어 설명
REASON_LABELS = {
    "HIDDEN_WHITE_TEXT": "흰색/은닉색 글자",
    "TINY_FONT": "초소형 폰트",
    "HIDDEN_ATTRIBUTE": "숨김 속성(vanish)",
    "METADATA_TEXT": "메타데이터 텍스트",
    "ZERO_WIDTH_CHARS": "제로폭 문자",
    "OFFPAGE_TEXT": "페이지 밖 텍스트",
    "ENCODED_TEXT": "인코딩된 텍스트",
}

console = Console()


def analyze_file(path):
    """단일 파일을 확장자로 분기해 검사. 결과 dict 반환."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        findings = docx_detector.detect(path)
    elif ext == ".pdf":
        findings = pdf_detector.detect(path)
    else:
        return None  # 지원하지 않는 확장자

    return {
        "file": os.path.basename(path),
        "path": path,
        "findings": findings,
        "verdict": "SUSPICIOUS" if findings else "CLEAN",
    }


def collect_targets(target):
    """파일이면 그 파일, 폴더면 안의 .docx/.pdf 전체를 정렬해 반환."""
    if os.path.isdir(target):
        out = []
        for name in sorted(os.listdir(target)):
            if name.lower().endswith((".docx", ".pdf")):
                out.append(os.path.join(target, name))
        return out
    return [target]


def _truncate(text, limit=70):
    text = " ".join(str(text).split())  # 개행/중복공백 정리
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_table(results):
    """rich 표로 탐지 결과 출력. 위험=빨강, clean=초록."""
    table = Table(
        title="HANFILTER — 문서 은닉 텍스트 탐지 결과",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("파일", style="bold", no_wrap=True)
    table.add_column("은닉 사유", no_wrap=True)
    table.add_column("위치", style="dim", no_wrap=True)
    table.add_column("추출 텍스트")
    table.add_column("판정", justify="center", no_wrap=True)

    for res in results:
        verdict = res["verdict"]
        verdict_cell = (
            "[bold red]⚠ SUSPICIOUS[/]" if verdict == "SUSPICIOUS"
            else "[bold green]✓ CLEAN[/]"
        )
        if not res["findings"]:
            table.add_row(res["file"], "[green]—[/]", "—", "[green]은닉 신호 없음[/]", verdict_cell)
            continue

        for i, f in enumerate(res["findings"]):
            label = REASON_LABELS.get(f["reason"], f["reason"])
            table.add_row(
                res["file"] if i == 0 else "",
                f"[red]{label}[/]\n[dim]{f['reason']}[/]",
                f["location"],
                _truncate(f["text"]),
                verdict_cell if i == 0 else "",
            )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="문서 구조에 숨겨진 프롬프트 인젝션을 탐지한다 (결정론적, AI 미사용)."
    )
    parser.add_argument("target", help="검사할 .docx/.pdf 파일 또는 폴더 경로")
    parser.add_argument("--json", metavar="경로", help="결과를 JSON 파일로도 저장")
    args = parser.parse_args()

    if not os.path.exists(args.target):
        console.print(f"[bold red]경로를 찾을 수 없음:[/] {args.target}")
        sys.exit(1)

    targets = collect_targets(args.target)
    if not targets:
        console.print("[yellow]검사할 .docx/.pdf 파일이 없습니다.[/]")
        sys.exit(0)

    results = []
    for path in targets:
        res = analyze_file(path)
        if res is None:
            console.print(f"[yellow]건너뜀(미지원 형식):[/] {path}")
            continue
        results.append(res)

    render_table(results)

    # 요약 한 줄
    total = len(results)
    suspicious = sum(1 for r in results if r["verdict"] == "SUSPICIOUS")
    style = "bold red" if suspicious else "bold green"
    console.print(
        f"\n[{style}]요약: {total}개 문서 중 {suspicious}개에서 은닉 텍스트 발견[/]"
    )

    # JSON 저장
    if args.json:
        payload = [
            {"file": r["file"], "findings": r["findings"], "verdict": r["verdict"]}
            for r in results
        ]
        with open(args.json, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
        console.print(f"[dim]JSON 저장됨: {args.json}[/]")

    # 은닉 발견 시 종료 코드 1 (CI/파이프라인 연동용)
    sys.exit(1 if suspicious else 0)


if __name__ == "__main__":
    main()
