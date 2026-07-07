"use strict";

const $ = (sel) => document.querySelector(sel);
const resultEl = $("#result");
const galleryEl = $("#sampleGallery");
const dropzone = $("#dropzone");
const fileInput = $("#fileInput");

// ---------------------------------------------------------------------------
// 샘플 갤러리
// ---------------------------------------------------------------------------
async function loadSamples() {
  try {
    const res = await fetch("/api/samples");
    const samples = await res.json();
    if (!samples.length) {
      galleryEl.innerHTML =
        '<div class="loading">샘플이 없습니다. 먼저 <code>python generate_samples.py</code> 실행.</div>';
      return;
    }
    galleryEl.innerHTML = "";
    for (const s of samples) {
      const card = document.createElement("div");
      card.className = "sample-card";
      card.innerHTML = `
        <span class="sc-dot ${s.category}"></span>
        <span class="sc-name">${s.name}</span>
        <span class="sc-type">${s.type}</span>`;
      card.addEventListener("click", () => {
        document.querySelectorAll(".sample-card").forEach((c) => c.classList.remove("active"));
        card.classList.add("active");
        scanSample(s.name);
      });
      galleryEl.appendChild(card);
    }
  } catch (e) {
    galleryEl.innerHTML = '<div class="loading">샘플 목록을 불러오지 못했습니다.</div>';
  }
}

// ---------------------------------------------------------------------------
// 스캔 요청
// ---------------------------------------------------------------------------
function showScanning(name) {
  resultEl.className = "";
  resultEl.innerHTML = `<div class="scanning"><span class="spinner"></span> <span>${name} 구조 파싱 중…</span></div>`;
}

async function scanSample(name) {
  showScanning(name);
  try {
    const res = await fetch(`/api/scan/sample/${encodeURIComponent(name)}`, { method: "POST" });
    if (!res.ok) throw new Error((await res.json()).detail || "스캔 실패");
    renderResult(await res.json());
  } catch (e) {
    showError(e.message);
  }
}

async function scanUpload(file) {
  document.querySelectorAll(".sample-card").forEach((c) => c.classList.remove("active"));
  showScanning(file.name);
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/scan", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "스캔 실패");
    renderResult(await res.json());
  } catch (e) {
    showError(e.message);
  }
}

function showError(msg) {
  resultEl.className = "";
  resultEl.innerHTML = `<div class="error-box">⚠ ${msg}</div>`;
}

// ---------------------------------------------------------------------------
// 결과 렌더
// ---------------------------------------------------------------------------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function renderResult(data) {
  resultEl.className = "";
  const suspicious = data.verdict === "SUSPICIOUS";

  const banner = suspicious
    ? `<div class="verdict-banner suspicious">
         <span class="vb-icon">⚠️</span>
         <div class="vb-text">
           <h3>SUSPICIOUS — 은닉 텍스트 발견</h3>
           <p><span class="vb-file">${escapeHtml(data.file)}</span> 에서 ${data.findings.length}건의 은닉 신호</p>
         </div>
       </div>`
    : `<div class="verdict-banner clean">
         <span class="vb-icon">✅</span>
         <div class="vb-text">
           <h3>CLEAN — 은닉 신호 없음</h3>
           <p><span class="vb-file">${escapeHtml(data.file)}</span> 구조에서 숨겨진 텍스트를 찾지 못함</p>
         </div>
       </div>`;

  let findingsHtml = "";
  if (suspicious) {
    findingsHtml = '<div class="findings">' + data.findings.map((f) => `
      <div class="finding">
        <div class="f-top">
          <span class="f-badge">${escapeHtml(f.label || f.reason)}</span>
          <span class="f-reason">${escapeHtml(f.reason)}</span>
          <span class="f-loc">${escapeHtml(f.location)}</span>
        </div>
        ${f.description ? `<div class="f-desc">${escapeHtml(f.description)}</div>` : ""}
        <div class="f-text">${escapeHtml(f.text)}</div>
      </div>`).join("") + "</div>";
  }

  const reasonCounts = Object.entries(data.reason_counts || {})
    .map(([k, v]) => `<span><b>${v}</b> × ${escapeHtml(k)}</span>`).join("");
  const summary = `<div class="result-summary">
      <span>형식: <b>${escapeHtml(data.type.toUpperCase())}</b></span>
      <span>총 findings: <b>${data.findings.length}</b></span>
      ${reasonCounts}
    </div>`;

  resultEl.innerHTML = banner + findingsHtml + summary;
}

// ---------------------------------------------------------------------------
// 드래그&드롭 / 클릭 업로드
// ---------------------------------------------------------------------------
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) scanUpload(e.target.files[0]);
});
["dragover", "dragenter"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) scanUpload(e.dataTransfer.files[0]);
});

loadSamples();
