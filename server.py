#!/usr/bin/env python3
"""
server.py — HANFILTER 데모 백엔드 (FastAPI)

CLI(detect.py)와 동일한 결정론적 탐지기(detectors/)를 그대로 재사용해,
문서 업로드 → 구조 파싱 → 은닉 텍스트 탐지 결과를 JSON으로 돌려준다.
프론트엔드(web/)를 정적 파일로 서빙한다. AI/모델 없음.

실행:
    python server.py            # http://localhost:8000
    python server.py --port 9000
"""

import argparse
import os
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from detectors import docx_detector, pdf_detector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

SUPPORTED = (".docx", ".pdf")

# 사유 코드 → (한국어 라벨, 한 줄 설명) — 프론트엔드 배지/툴팁용
REASON_META = {
    "HIDDEN_WHITE_TEXT": ("흰색/은닉색 글자", "흰 배경에서 보이지 않는 흰색 텍스트"),
    "TINY_FONT": ("초소형 폰트", "사실상 안 보이는 극소 폰트 크기"),
    "HIDDEN_ATTRIBUTE": ("숨김 속성", "DOCX vanish 속성이 켜진 텍스트"),
    "METADATA_TEXT": ("메타데이터 텍스트", "본문 아닌 문서 속성에 심긴 명령형 텍스트"),
    "ZERO_WIDTH_CHARS": ("제로폭 문자", "제로폭 공백/조이너로 은닉·분절된 텍스트"),
    "OFFPAGE_TEXT": ("페이지 밖 텍스트", "페이지 경계 밖 좌표에 렌더된 텍스트"),
    "ENCODED_TEXT": ("인코딩된 텍스트", "Base64 등으로 인코딩되어 숨겨진 텍스트"),
}

app = FastAPI(title="HANFILTER Demo", version="0.1.0")


# ---------------------------------------------------------------------------
# 핵심 스캔 로직 (CLI와 동일한 detectors 재사용)
# ---------------------------------------------------------------------------

def scan_path(path, display_name=None):
    """단일 파일을 확장자로 분기해 검사. 결과 dict 반환."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        findings = docx_detector.detect(path)
    elif ext == ".pdf":
        findings = pdf_detector.detect(path)
    else:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 형식: {ext}")

    # 사유별 사람이 읽는 라벨/설명 부착
    enriched = []
    for f in findings:
        label, desc = REASON_META.get(f["reason"], (f["reason"], ""))
        enriched.append({**f, "label": label, "description": desc})

    return {
        "file": display_name or os.path.basename(path),
        "type": ext.lstrip("."),
        "findings": enriched,
        "verdict": "SUSPICIOUS" if enriched else "CLEAN",
        "reason_counts": _count_reasons(enriched),
    }


def _count_reasons(findings):
    counts = {}
    for f in findings:
        counts[f["reason"]] = counts.get(f["reason"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/samples")
def list_samples():
    """번들된 샘플 목록. 파일명으로 attack/clean 카테고리를 유추해 반환."""
    if not os.path.isdir(SAMPLES_DIR):
        return []
    out = []
    for name in sorted(os.listdir(SAMPLES_DIR)):
        if not name.lower().endswith(SUPPORTED):
            continue
        category = "attack" if name.startswith("attack") else "clean"
        out.append({
            "name": name,
            "type": os.path.splitext(name)[1].lstrip("."),
            "category": category,
        })
    return out


@app.post("/api/scan/sample/{name}")
def scan_sample(name):
    """번들된 샘플을 이름으로 검사 (업로드 없이 데모 시연용)."""
    # 경로 조작 방지: basename만 허용
    safe = os.path.basename(name)
    path = os.path.join(SAMPLES_DIR, safe)
    if not os.path.isfile(path) or not safe.lower().endswith(SUPPORTED):
        raise HTTPException(status_code=404, detail="샘플을 찾을 수 없습니다.")
    return scan_path(path, display_name=safe)


@app.post("/api/scan")
async def scan_upload(file: UploadFile = File(...)):
    """업로드된 문서를 검사."""
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED:
        raise HTTPException(status_code=400, detail="지원 형식: .docx, .pdf")

    data = await file.read()
    # 탐지기는 파일 경로를 받으므로 임시 파일에 기록 후 검사
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return scan_path(tmp_path, display_name=filename)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@app.get("/api/reasons")
def reasons():
    """탐지 항목 사전 (프론트 범례용)."""
    return {k: {"label": v[0], "description": v[1]} for k, v in REASON_META.items()}


# ---------------------------------------------------------------------------
# 정적 프론트엔드 서빙
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def main():
    parser = argparse.ArgumentParser(description="HANFILTER 데모 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn
    print(f"HANFILTER 데모: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
