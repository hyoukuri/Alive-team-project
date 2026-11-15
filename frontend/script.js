
/* SEEDU:ON - 학년별 세특 입력과 AI 대시보드 */
const studentRecords = { 1: "", 2: "" };
let activeGrade = 1;

const $ = (id) => document.getElementById(id);
const gradeTabs = document.querySelectorAll(".grade-tab");
const steps = document.querySelectorAll(".step");
const textarea = $("student-record");
const gradeSelect = $("current-grade");
const analyzeButton = $("analyze-button");
const analysisResults = $("analysis-results");
const planResults = $("plan-results");
let latestAnalysis = null;
let latestAnalyzedRecords = null;

function saveRecord() {
  studentRecords[activeGrade] = textarea.value;
}

function updateCount() {
  saveRecord();
  const current = Number(gradeSelect.value);
  const total = Array.from(
    { length: current },
    (_, i) => studentRecords[i + 1].length
  ).reduce((a, b) => a + b, 0);

  $("character-count").textContent =
    `${activeGrade}학년: ${studentRecords[activeGrade].length.toLocaleString()}자 / 전체: ${total.toLocaleString()}자`;
}

function switchGrade(grade) {
  if (grade < 1 || grade > 2 || grade > Number(gradeSelect.value)) return;

  saveRecord();
  activeGrade = grade;
  textarea.value = studentRecords[grade];

  gradeTabs.forEach((tab) =>
    tab.classList.toggle(
      "active",
      Number(tab.dataset.grade) === grade
    )
  );

  updateCount();
}

function updateVisibleGrades() {
  const current = Number(gradeSelect.value);

  gradeTabs.forEach((tab) => {
    tab.hidden = Number(tab.dataset.grade) > current;
  });

  if (activeGrade > current) switchGrade(current);
  updateCount();
}

function showPage(page) {
  const homePage = $("home-page");
  if (homePage) homePage.hidden = page !== 0;
  $("input-page").hidden = page !== 1;
  $("analysis-page").hidden = page !== 2;
  $("plan-page").hidden = page !== 3;
  const recordsPage = $("records-page");
  if (recordsPage) recordsPage.hidden = page !== 4;

  steps.forEach((step, i) =>
    step.classList.toggle("active", i === page - 1)
  );

  // 디자인용: 페이지별 컨테이너 폭과 헤더의 현재 페이지 이름
  document.body.dataset.page = String(page);
  const headerPage = $("header-page");
  if (headerPage) {
    headerPage.textContent =
      ["나의 진로 설계", "생기부 입력", "AI 역량 분석", "맞춤 진로 설계"][page] || "";
  }

  window.scrollTo(0, 0);

  // 내 기록 화면은 열 때마다 서버에서 최신 목록을 불러온다
  if (page === 4 && typeof loadRecords === "function") loadRecords();
}

function el(tag, className, content) {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (content !== undefined) {
    node.textContent = String(content);
  }

  return node;
}

function card(title, extraClass = "") {
  const section = el("section", `result-card ${extraClass}`);
  section.append(el("h2", "card-heading", title));
  return section;
}

// 학과 적합도 점수(0~100)를 화면 표시용 단계로 바꾼다
function fitLevel(score) {
  if (score >= 80) return "적합도 높음";
  if (score >= 60) return "적합도 보통";
  return "적합도 낮음";
}

function radarChart(items) {
  const wrap = el("div", "radar-wrap");
  const canvas = document.createElement("canvas");

  canvas.width = 620;
  canvas.height = 360;
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    "5대 역량 레이더 차트. " +
      items
        .map((item) => `${item.name} ${item.score === null ? "근거 부족" : Math.round(item.score) + "점"}`)
        .join(", ") +
      " (100점 만점)"
  );

  wrap.append(canvas);

  const ctx = canvas.getContext("2d");
  const cx = 310;
  const cy = 182;
  const radius = 124;

  const angle = (i) =>
    -Math.PI / 2 + (i * Math.PI * 2) / 5;

  const point = (i, r) => [
    cx + Math.cos(angle(i)) * r,
    cy + Math.sin(angle(i)) * r
  ];

  function polygon(scale, fill, stroke, width = 1, useScore = false) {
    ctx.beginPath();

    items.forEach((item, i) => {
      const scoreScale = useScore
        ? Number(item.score ?? 0) / 100
        : 1;

      const [x, y] = point(
        i,
        radius * scale * scoreScale
      );

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.closePath();

    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }

    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  // 캔버스는 CSS 변수를 직접 못 쓰므로 디자인 토큰을 읽어 온다
  const css = getComputedStyle(document.documentElement);
  const token = (name, fallback) =>
    css.getPropertyValue(name).trim() || fallback;

  const gridColor = token("--chip", "#CBD5E1");
  const lineColor = token("--accent-deep", "#CA8A04");
  const labelColor = token("--on-card", "#0F172A");

  [0.25, 0.5, 0.75].forEach((r) => {
    ctx.globalAlpha = 0.6;
    polygon(r, null, gridColor);
    ctx.globalAlpha = 1;
  });
  polygon(1, null, gridColor, 1.5);

  items.forEach((_, i) => {
    const [x, y] = point(i, radius);

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(x, y);
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  polygon(
    1,
    "rgba(250,204,21,0.40)",
    lineColor,
    2.5,
    true
  );

  ctx.font = '500 15px "Noto Sans KR", "Malgun Gothic", sans-serif';
  ctx.fillStyle = labelColor;
  ctx.textAlign = "center";

  items.forEach((item, i) => {
    const [x, y] = point(i, radius + 49);
    ctx.fillText(item.name, x, y + 5);
  });

  return wrap;
}

// 출처가 섞인 이전 분석 결과도 잘못된 과목명으로 표시하지 않습니다.
// 예: "공통수학1: 행동특성 및 종합의견: ..." -> "행동특성 및 종합의견: ..."
function canonicalEvidenceProvenance(value) {
  const raw = String(value ?? '').replace(/\s+/g, ' ').trim();
  const nested = raw.match(/^(?:(?:\d학년\s+)?(?:과목:\s*)?[^:：]{2,40}\s*[:：]\s*){0,2}(행동특성 및 종합의견|자율[·ㆍ]자치활동|동아리활동|진로활동)\s*[:：]\s*(.*)$/);
  return nested ? `${nested[1]}: ${nested[2]}` : raw;
}
function evidenceSourceLabel(source, quote) {
  const content = canonicalEvidenceProvenance(quote);
  const explicit = content.match(/^(행동특성 및 종합의견|자율[·ㆍ]자치활동|동아리활동|진로활동)\s*[:：]/);
  return explicit ? explicit[1] : String(source ?? '').replace(/^과목:\s*/, '').trim();
}
// 화면에서 원문을 중간에 자르지 않고, 핵심 수행 행위를 완결된 문장으로 요약합니다.
// 원문은 세부 보기에서 별도로 확인할 수 있습니다.
// Evidence can contain several subject records joined by " / ".
// Never take a label from one record and a sentence from another.
function splitEvidenceEntries(value) {
  return String(value ?? '').split(/\s+\/\s+(?=(?:(?:[123]학년\s+)?(?:과목:\s*)?(?:공통|통합|과학탐구|한국사|정보|체육|음악|미술|기술|가정|행동특성|자율|동아리|진로)|외\s+\d+개\s+활동))/)
    .map(x => x.trim()).filter(Boolean);
}
function evidenceEntryParts(value) {
  const raw = canonicalEvidenceProvenance(value).replace(/\s+/g, ' ').trim();
  // These patterns identify the provenance of the SAME evidence item.
  const category = raw.match(/^(?:(?:[123]학년\s+)?(?:과목:\s*)?)?(행동특성 및 종합의견|자율[·ㆍ]자치활동|동아리활동|진로활동)\s*[:：]\s*(.*)$/);
  if (category) return { label: category[1], body: category[2] };
  const subject = raw.match(/^(?:(?:[123]학년\s+)?(?:과목:\s*)?)([^:：]{2,45})\s*[:：]\s*(.*)$/);
  if (subject && !/^(?:확인된 활동|추천 근거|보완 방향|평가 이유|강점|학업역량|탐구역량|진로역량|공동체역량|성장가능성)$/.test(subject[1])) {
    return { label: subject[1].trim(), body: subject[2] };
  }
  return { label: '', body: raw };
}
function evidenceSummary(value) {
  const entries = splitEvidenceEntries(value).filter(x => !/^외\s+\d+개\s+활동/.test(x));
  if (!entries.length) return '이 항목에서 확인된 활동 근거가 없습니다.';
  // A summary must be drawn from one record, including its own source label.
  const { label, body: originalBody } = evidenceEntryParts(entries[0]);
  const prefix = label ? `${label}: ` : '';
  const body = originalBody.replace(/[“”]/g, '"').replace(/[‘’]/g, "'")
    .replace(/^(?:확인된 활동|추천 근거)\s*[:：]\s*/, '').trim();
  const action = /(조사|비교|분석|실험|측정|제작|발표|작성|탐구|검증|토론|해석|설계|정리|제안|수집|평가|활용|관찰|설명)/;
  const sentences = body.split(/(?<=[.!?。])\s+/).map(x => x.trim());
  const complete = sentences.find(x => x.length >= 18 && /[.!?。]$/.test(x) && !/(?:…|\.\.\.)/.test(x) && action.test(x));
  if (complete && complete.length <= 220) return prefix + complete;
  // The following topic descriptions are used only when the SAME entry contains the topic.
  const topics = [
    [/산성화|산성비|중화 방법/, '산성비와 토양·호수의 중화 방법을 조사·탐구한 활동이 확인됩니다.'],
    [/중화열|혼합용액|중화점/, '중화 반응에서 용액의 변화를 측정·분석한 활동이 확인됩니다.'],
    [/진원지|원의 방정식|지진/, '원의 방정식을 활용한 지진 진원지 탐색 활동이 확인됩니다.'],
    [/탱자나무|로트레크|닉부이/, '문학 작품의 표현 방식과 작가의 의도를 비교·분석한 활동이 확인됩니다.'],
    [/기억에 남는 경험|영어 글쓰기/, '경험을 소재로 한 영어 글쓰기 활동이 확인됩니다.'],
    [/이산화탄소|환기|공기 질/, '교실 환경과 공기 질을 관찰·분석한 활동이 확인됩니다.'],
  ];
  const matched = topics.find(([pattern]) => pattern.test(body));
  if (matched) return prefix + matched[1];
  if (complete) return prefix + complete; // show complete evidence, never cut mid-sentence
  const title = body.match(/["']([^"']{4,80})["']/)?.[1];
  if (title && !/(?:…|\.\.\.)/.test(title)) return `${prefix}「${title}」을 주제로 한 활동이 확인됩니다.`;
  return `${prefix}활동 기록이 확인되지만, 정확한 수행 내용은 원문을 다시 확인해야 합니다.`;
}
// Duplicated evidence may carry different subject/competency prefixes.
// Compare the original quoted activity, not its decorative label.
function evidenceIdentity(value) {
  const raw = canonicalEvidenceProvenance(value);
  const afterDash = raw.includes('—') ? raw.split('—').slice(-1)[0].trim() : '';
  const quoted = raw.match(/[“"]([^”"]{12,})[”"]/)?.[1] || '';
  const body = afterDash || quoted || raw.replace(/^(?:.*?\d학년\s+)?(?:과목:\s*)?[^:：]{1,45}[:：]\s*/, '');
  return body.replace(/[“”"'‘’\s.,!?。·]/g, '').toLowerCase();
}
function evidenceLabelQuality(value) {
  const label = String(value ?? '').trim();
  // Prefer a correctly written official subject name over a shortened typo.
  if (/^(?:\d학년\s+)?(?:과목:\s*)?공통수학1\s*[:：]/.test(label)) return 2;
  if (/^(?:\d학년\s+)?(?:과목:\s*)?통수학1\s*[:：]/.test(label)) return 0;
  return 1;
}
function uniqueEvidenceItems(values) {
  const unique = new Map();
  values.forEach(value => {
    const key = evidenceIdentity(value);
    if (!key) return;
    if (!unique.has(key) || evidenceLabelQuality(value) > evidenceLabelQuality(unique.get(key))) {
      unique.set(key, value);
    }
  });
  return [...unique.values()];
}
function dedupeGrowthSummary(value) {
  const raw = String(value ?? '');
  // Growth records separate independently evidenced activities with ' / '.
  const parts = raw.split(/\s+\/\s+/);
  return parts.length < 2 ? raw : uniqueEvidenceItems(parts).join(' / ');
}
function conciseText(value) { return evidenceSummary(value); }
function compactEvidence(value) { return evidenceSummary(value); }
function seeduFeedbackSummary(value) { return evidenceSummary(value); }
// Select distinct existing records only. No invented or cross-subject
// sentences; the original source text is kept under the expand control.
function selectCompetencyEvidence(raw, competency, limit = 3) {
  const entries = uniqueEvidenceItems(splitEvidenceEntries(raw))
    .filter(x => x && !/^외\\s+\\d+개\\s+활동/.test(x) && !/(?:…|\\.\\.\\.)/.test(x));
  const terms = {
    "학업역량": /이해|적용|활용|계산|해석|분석|설명|문제|개념|정리|비교|방정식|함수|수학|과학|실험|보고서|중화|인포그래픽|자료/,
    "진로역량": /진로|전공|직업|학과|탐색|연계|심화|관련|계획/,
    "탐구역량": /탐구|조사|실험|측정|검증|설계|분석|비교|자료|오차/,
    "공동체역량": /협업|협력|조율|팀|모둠|역할|기여|공동|지원|의견/,
    "성장가능성": /피드백|수정|보완|개선|성찰|재검토|발전|후속|재실험/
  };
  const activity = /조사|비교|분석|실험|측정|제작|발표|작성|탐구|검증|토론|해석|설계|정리|제안|수집|평가|활용|관찰|설명|수정|개선/;
  const scored = entries.map((entry, index) => {
    const {label, body} = evidenceEntryParts(entry);
    const meaningful = String(body || "").replace(/^[“"'‘’]+|[“"'‘’]+$/g, "").trim();
    const matches = terms[competency]?.test(meaningful) || false;
    return {entry, index, label, meaningful, matches,
      score: (matches ? 3 : 0) + (activity.test(meaningful) ? 2 : 0) +
        (/\\d|결과|그래프|보고서|발표자료|산출물/.test(meaningful) ? 1 : 0)};
  }).filter(x => x.meaningful.length >= 15 && activity.test(x.meaningful));
  // Do not present unrelated activities as a competency-specific top three.
  const relevant = scored.filter(x => x.matches).sort((a,b) => b.score-a.score || a.index-b.index);
  return relevant.slice(0, limit).map(x => {
    const prefix = x.label ? x.label + ": " : "";
    return prefix + x.meaningful;
  });
}
function appendEvidencePreview(parent, raw, heading = "원문 근거 보기") {
  const source = String(raw || "").trim();
  if (!source) return;
  const details = el("details", "seedu-original-evidence");
  details.append(el("summary", "", heading));
  const entries = splitEvidenceEntries(source);
  entries.forEach(entry => {
    if (/^외\s+\d+개\s+활동/.test(entry)) {
      details.append(el("p", "seedu-evidence-item", entry));
      return;
    }
    const incomplete = /(?:…|\.\.\.)/.test(entry);
    details.append(el("p", "seedu-evidence-item", incomplete
      ? "이전 분석 결과에 불완전한 인용이 저장되어 있습니다. 전체 학생부 기록으로 새로 분석하면 원문을 확인할 수 있습니다."
      : entry));
  });
  parent.append(details);
}

// A major is selected separately from the five general competencies.
// Use ONLY verified, major-linked evidenceSources from the server; never
// infer a student's personal strength from a high generic competency score.
function majorFeedbackProfile(major) {
  const name = String(major || "");
  const profiles = [
    [/기계|자동차|로봇|항공우주|건축공학|토목/, "수학·물리 개념을 실제 구조와 시스템에 적용하는 역량", "변인(재료·형상·하중 등)을 정해 모형을 설계하고 동일 조건에서 반복 측정한 뒤 오차를 분석해 보세요."],
    [/화학|신소재|환경공학|에너지/, "물질 변화와 실험 데이터를 해석하는 역량", "반응 조건을 통제하고 정량 측정값을 수집해 반복 실험·오차 분석·후속 가설을 제시해 보세요."],
    [/국어국문|영어영문|일어일문|중어중문|언어학/, "텍스트·언어 자료를 근거로 해석하고 비교하는 역량", "서로 다른 작품이나 언어 자료를 같은 기준으로 비교하고 반대 해석까지 검토한 비평·분석 보고서를 작성해 보세요."],
    [/수학|통계|데이터사이언스|인공지능|컴퓨터|소프트웨어|정보보안/, "수리적 모델링과 데이터·알고리즘을 활용한 문제 해결 역량", "자료의 출처·표본·모형 가정을 명시하고 다른 조건의 데이터로 예측·분석 결과를 검증해 보세요."],
    [/생명|의예|약학|간호|보건|치의|수의/, "생명·건강 현상을 과학적 근거로 해석하는 역량", "생명·건강 관련 탐구에서 대조 조건과 자료 신뢰도를 확인하고 연구 윤리·한계를 함께 정리해 보세요."],
    [/교육|심리|사회|경제|경영|정치|행정|법학/, "사회·인간 현상을 근거 자료와 개념으로 설명하는 역량", "명확한 연구 질문을 설정하고 사례·통계·문헌 자료를 비교해 대안과 한계를 제시해 보세요."],
    [/디자인|미디어|광고|영상|애니메이션|음악|무용/, "표현·제작 의도를 분석하고 결과물을 개선하는 역량", "대상 사용자·감상자의 반응을 수집하고 제작 전후 결과를 같은 기준으로 비교해 개선안을 제시해 보세요."]
  ];
  const profile = profiles.find(([rx]) => rx.test(name));
  return profile ? { connection: profile[1], next: profile[2] } : {
    connection: `${name}의 핵심 개념을 교과 활동에 적용하는 역량`,
    next: `${name}의 기초 개념을 정리하고 관련 탐구 질문·방법·검증 기준을 구체화해 후속 활동을 기록해 보세요.`
  };
}

function buildMajorFeedback(major) {
  const profile = majorFeedbackProfile(major?.name);
  const evidence = (major?.evidenceSources || []).filter(x => x && x.quote && x.source);
  const seen = new Set();
  const unique = evidence.filter(item => {
    const key = `${item.grade}|${String(item.quote).replace(/\s+/g, "").toLowerCase()}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const strengths = unique.slice(0, 2).map(item => {
    const subject = evidenceSourceLabel(item.source, item.quote);
    const summary = evidenceSummary(item.quote);
    return `${item.grade}학년 ${subject}: ${summary} 이 활동은 ${profile.connection}과 연결해 발전시킬 수 있습니다.`;
  });
  if (!strengths.length) strengths.push(`${major?.name || "선택 전공"}과 직접 연결된 검증 근거가 현재 분석 결과에서 확인되지 않았습니다. 전공 관련 강점을 단정하지 않습니다.`);
  const coverage = major?.categoryCoverage || {};
  const missing = ["탐구 심화도", "관심의 지속성", "융합 역량", "전공 관련 활동", "학업 역량"].filter(k => !(Number(coverage[k]) > 0));
  const labels = {
    "탐구 심화도": "자료 수집 → 분석 → 재검증을 이어 간 후속 기록",
    "관심의 지속성": "같은 전공 주제를 학기·학년을 넘어 발전시킨 기록",
    "융합 역량": "두 교과의 개념을 하나의 전공 문제에 적용한 기록",
    "전공 관련 활동": "전공 주제와 직접 연결되는 수행 과정·결과 기록",
    "학업 역량": "관련 교과 개념을 적용하고 오류를 검토한 기록"
  };
  const improvements = [];
  if (missing.length) {
    improvements.push(`현재 연결된 학생부 근거에서 '${missing[0]}' 지표를 평가할 자료가 충분히 확인되지 않았습니다. ${labels[missing[0]]}을 확인하거나 새롭게 계획해 보세요. (능력 부족 판정이 아닙니다.)`);
  } else {
    improvements.push("전공 관련 평가 지표에 일부 근거가 연결되어 있습니다. 다음 단계에서는 수행 결과의 타당성과 반복 검증 기록을 더 확인해 보세요.");
  }
  improvements.push(`${major?.name || "희망 전공"} 후속 탐구: ${profile.next}`);
  return {strengths, improvements};
}

function appendFeedbackList(box, values) {
  const list = el("ul", "seedu-feedback-list");
  values.forEach(value => list.append(el("li", "", value)));
  box.append(list);
}

function renderDashboard(data) {
  analysisResults.replaceChildren();

  // AI 서비스 오류는 학생부의 근거 부족(N/E)과 다르다.
  if (data.aiReview?.status === "error" || data.aiReview?.status === "fallback") {
    const failed = card("분석 서비스 오류", "span-full");
    failed.append(el("p", "evidence", "학생부 내용이 부족하다는 뜻이 아닙니다. AI 의미 분석이 완료되지 않아 점수와 추천을 생성하지 않았습니다."));
    failed.append(el("p", "evidence", "Render의 환경변수 OPENAI_API_KEY / OPENAI_MODEL을 확인하고, 서버 로그에서 실제 오류 원인을 확인해 주세요."));
    const retry = el("button", "btn btn-primary", "다시 분석하기");
    retry.type = "button";
    retry.style.marginTop = "16px";
    retry.addEventListener("click", () => showPage(1));
    failed.append(retry);
    analysisResults.append(failed);
    return;
  }

  const title = el("div", "result-intro");
  title.append(
    el("p", "eyebrow", data.aiReview?.used ? "SEEDU:ON · SEMANTIC ANALYSIS" : "SEEDU:ON · ANALYSIS PENDING")
  );
  title.append(
    el("h2", "result-title", "나의 역량 분석 리포트")
  );
  title.append(
    el(
      "p",
      "muted",
      data.aiReview?.used ? "AI가 학생부 문맥과 수행 근거를 분석하고 Python이 등급을 검증했습니다. N/E는 점수로 환산하지 않습니다." : "AI 의미 검토를 완료하지 못해 점수 평가를 보류했습니다. 기록 내용은 보존되며 재분석할 수 있습니다."
    )
  );

  analysisResults.append(title);

  // All original chunks are still analyzed. Present only grouped summaries.
  if (data.inputCoverage?.activities) {
    const cv = data.inputCoverage;
    const grouped = new Map();
    cv.activities.forEach((item) => {
      const name = String(item.source || '기타').replace(/^과목:\s*/, '').trim();
      const key = `${item.grade}학년 ${name}`;
      const prev = grouped.get(key) || { chars: 0, processed: 0, facts: 0 };
      prev.chars += item.inputChars;
      prev.processed += item.processedChars;
      prev.facts += item.verifiedFacts;
      grouped.set(key, prev);
    });
    const audit = card('전체 세특 분석 현황', 'span-full');
    const done = [...grouped.values()].filter(x => x.chars === x.processed).length;
    const cited = [...grouped.values()].filter(x => x.facts > 0).length;
    audit.append(el('p', 'evidence', `${grouped.size}개 과목·활동 중 ${done}개 원문 처리 완료 · ${cited}개에서 근거 확인`));
    const details = el('details', 'coverage-details');
    details.append(el('summary', '', '과목별 처리 내역 펼쳐보기'));
    const list = el('ul', '');
    [...grouped].forEach(([name, item]) => {
      list.append(el('li', 'evidence', `${name} · ${item.chars === item.processed ? '처리 완료' : '미완료'} · 근거 ${item.facts}건`));
    });
    details.append(list);
    audit.append(details);
    audit.append(el('p', 'muted', '근거 0건은 능력 부족을 뜻하지 않습니다. 모든 원문을 처리했어도 근거의 정확성은 별도 검토가 필요합니다.'));
    analysisResults.append(audit);
  }

  // Five concise scores; keep the detailed evidence available only on demand.
  const competencies = card("5대 핵심 역량", "span-full seedu-competency-section");
  competencies.append(el("p", "seedu-section-subtitle", "검증된 수행 근거를 기반으로 계산한 참고 지수입니다. 실제 능력이나 합격 가능성을 뜻하지 않습니다."));
  const scores = el("div", "seedu-skill-list");
  data.competencies.forEach((item) => {
    const box = el("div", "seedu-skill-item");
    const heading = el("div", "seedu-skill-heading");
    heading.append(el("strong", "", item.name));
    const rated = item.score !== null && Number.isFinite(item.score);
    heading.append(el("span", rated ? "seedu-skill-value" : "seedu-skill-ne", rated ? `${Math.round(item.score)}점` : (data.aiReview?.used === false ? "AI 평가 미실시" : "근거 확인 필요")));
    box.append(heading);
    if (rated) {
      const track = el("div", "seedu-track");
      const fill = el("div", "seedu-fill");
      fill.style.width = `${Math.max(0, Math.min(100, item.score))}%`;
      track.append(fill);
      box.append(track);
    }
    if (item.evidence) {
      // Show up to three distinct, source-linked records. Never generate a
      // score justification by copying one arbitrary sentence.
      const evidencePanel = el("div", "seedu-skill-detail");
      evidencePanel.append(el("p", "seedu-evidence-heading", "핵심 평가 근거"));
      const examples = selectCompetencyEvidence(item.evidence, item.name, 3);
      if (examples.length) {
        const list = el("ul", "seedu-core-evidence-list");
        examples.forEach(entry => list.append(el("li", "seedu-core-evidence-item", entry)));
        evidencePanel.append(list);
        evidencePanel.append(el("p", "seedu-core-evidence-note", "대표 활동을 간추린 것으로, 각 활동의 점수 기여도를 뜻하지 않습니다."));
      } else {
        evidencePanel.append(el("p", "seedu-core-evidence-note", "확인 가능한 개별 활동 근거가 부족합니다."));
      }
      appendEvidencePreview(evidencePanel, item.evidence, "전체 원문 근거 보기");
      box.append(evidencePanel);
    }
    scores.append(box);
  });
  // 레이더 그래프를 삭제하지 않는다. 원본 canvas 렌더러와 간결한 점수 카드를 함께 제공한다.
  const visual = el("div", "seedu-competency-visual");
  const radarPanel = el("div", "seedu-radar-panel");
  radarPanel.append(radarChart(data.competencies));
  radarPanel.append(el("p", "seedu-radar-caption", "근거 기반 참고 지수 · 평가 불가 항목은 0점이 아닌 보류로 처리합니다."));
  visual.append(radarPanel, scores);
  competencies.append(visual);
  analysisResults.append(competencies);

  // Separate generic competency feedback from MAJOR-SPECIFIC evidence.
  // Users can compare how the same record relates to each proposed major.
  const feedbackWrap = el("div", "seedu-feedback-grid span-full");
  const majorFeedbackTitle = el("div", "seedu-major-feedback-title span-full");
  majorFeedbackTitle.append(el("h2", "card-heading", "학과별 강점 · 보완할 점"));
  majorFeedbackTitle.append(el("p", "muted", "선택한 학과의 검증된 세특 근거만 사용합니다. 전공 관련 근거가 없으면 강점으로 단정하지 않습니다."));
  analysisResults.append(majorFeedbackTitle);
  const majorPicker = el("div", "seedu-major-feedback-picker span-full");
  const strengthCard = card("전공 연계 강점", "feedback-card strength-card seedu-brief-feedback");
  const improvementCard = card("전공 연계 보완 방향", "feedback-card improve-card seedu-brief-feedback");
  const paintMajor = major => {
    const result = buildMajorFeedback(major);
    strengthCard.replaceChildren(el("h2", "card-heading", `${major.name} · 강점`));
    improvementCard.replaceChildren(el("h2", "card-heading", `${major.name} · 보완 방향`));
    appendFeedbackList(strengthCard, result.strengths);
    appendFeedbackList(improvementCard, result.improvements);
  };
  if (data.majors.length) {
    data.majors.forEach((major, i) => {
      const btn = el("button", "seedu-major-feedback-button", major.name);
      btn.type = "button";
      btn.addEventListener("click", () => {
        majorPicker.querySelectorAll("button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        paintMajor(major);
      });
      majorPicker.append(btn);
      if (i === 0) btn.click();
    });
  } else {
    strengthCard.append(el("p", "muted", "검증된 학과별 추천 근거가 없어 전공 연계 강점을 판단하지 않습니다."));
    improvementCard.append(el("p", "muted", "희망 학과를 선택한 후 관련 세특 근거를 검토해 보세요."));
  }
  analysisResults.append(majorPicker);
  feedbackWrap.append(strengthCard, improvementCard);
  analysisResults.append(feedbackWrap);

  const majors = card("근거 중심 전공 탐색", "span-full");
  const majorList = el("div", "major-list");

  const categoryMax = {
    "전공 관련 활동": 30,
    "학업 역량": 25,
    "관심의 지속성": 20,
    "탐구 심화도": 15,
    "융합 역량": 10
  };

  if (!data.majors.length) {
    majorList.append(el("p", "evidence", "이번 기록에서 전공별 평가 지표와 연결되는 근거가 충분히 확인되지 않았습니다. 억지로 학과 3개를 추천하지 않습니다. 진로활동이나 교과 탐구의 전공 관련 근거를 검토해 보세요."));
  }
  data.majors.forEach((item) => {
    const box = el("div", "major-item seedu-major-compact");
    const coverage = Math.max(0, Math.min(100, Number(item.coverageWeight) || 0));
    const complete = item.scoreStatus === "complete" && item.fit !== null && coverage === 100;
    box.append(el("p", "major-rank", "현재 기록 기반 전공 탐색 결과"));
    box.append(el("h3", "major-name", item.name));

    // Preserve N/E in the underlying rubric. Show the evaluated scope instead
    // of labeling every partial student record as an overall evaluation failure.
    const scope = el("div", "seedu-major-evaluation-scope");
    if (complete) {
      scope.append(el("p", "seedu-evaluation-note", `전체 지표 평가 점수: ${item.fit.toFixed(1)}/100점`));
      scope.append(el("p", "muted", "16개 지표 모두 평가 가능한 기록이 확인되었습니다. 이 점수는 합격 확률이 아닙니다."));
    } else if (coverage > 0 && Number.isFinite(item.partialScore)) {
      const part = item.partialScore.toFixed(1).replace(/\.0$/, "");
      scope.append(el("p", "seedu-evaluation-note", `확인된 부분 평가 점수: ${part}/${coverage}점`));
      scope.append(el("p", "muted", `전체 100점 배점 중 ${coverage}점에 해당하는 지표를 평가했습니다. 나머지 ${100 - coverage}점 배점은 근거가 부족해 미평가 상태입니다.`));
    } else {
      scope.append(el("p", "seedu-evaluation-note", "현재 평가 가능한 세부 지표가 확인되지 않았습니다."));
      scope.append(el("p", "muted", "학생부 원문과 전공 관련 활동을 추가로 확인한 뒤 평가할 수 있습니다."));
    }
    scope.append(el("p", "seedu-evaluation-caution", "전공 적합도 확정 점수나 합격 확률이 아닙니다. 근거 미확인(N/E)은 0점으로 계산하지 않습니다."));
    box.append(scope);
    appendEvidencePreview(box, item.reason, "추천 근거 원문 보기");

    const details = el("details", "major-fit-details seedu-major-details");
    details.append(el("summary", "", "점수 산정 이유 보기"));
    // Rubric 3.2: self-designed 16-indicator anchors, informed by educational research.
  const indicatorFocus = {
    "전공 주제 관련성":"전공 지식·질문과 실제 활동의 연결",
    "활동의 구체성":"학생이 수행한 역할·방법·산출물·수정",
    "활동 간 연계성":"서로 다른 활동 사이의 실제 후속 연결",
    "전공 기초 교과 역량":"전공 관련 교과 개념의 이해와 응용",
    "지식의 실제 적용":"교과 지식을 실제 문제 또는 산출물에 적용",
    "학습 태도와 개선":"오류·피드백을 반영한 학습 조정",
    "관심 주제의 반복·유지":"기록된 기간에서 실제 관심이 이어진 정황",
    "관심의 발전 과정":"초기 탐색에서 후속 활동으로의 발전",
    "자기주도적 확장":"추가 탐색이나 실행의 자기주도성",
    "탐구 문제 설정":"탐구 질문의 구체성·필요성·범위",
    "탐구 방법 설계":"방법 선택의 이유와 설계·개선",
    "결과 분석 및 검증":"자료와 결론의 연결 및 재확인",
    "개선 및 후속 탐구":"한계를 진단하고 실제로 후속 개선을 실행",
    "타 분야 지식 활용":"다른 분야의 개념을 실질적으로 연결",
    "융합적 문제해결":"서로 다른 분야의 방법을 결합한 문제 해결",
    "융합 결과의 타당성":"융합 산출물의 결과·한계·효과 검증"
  };
  const levelMeaning = {
    1:"관심이나 기초적인 참여·탐색 수준",
    2:"학생 자신의 구체적인 수행 행동이 확인된 수준",
    3:"같은 활동에서 방법과 결과의 연결이 확인된 수준",
    4:"검증·수정·개선 효과 등 심화 수행이 확인된 수준"
  };
  const nextAction = {
      "전공 관련 활동":"희망 학과 관련 질문을 정하고 교과 수업에서 실제 수행한 탐구 과정과 결과를 기록해 보세요.",
      "학업 역량":"해당 분야의 교과 개념을 적용한 풀이·분석·피드백 사례를 확인해 보세요.",
      "관심의 지속성":"학기별 후속 질문이나 기존 활동을 발전시킨 기록이 있는지 확인해 보세요.",
      "탐구 심화도":"자료 수집, 비교 기준, 결과 검증과 수정 과정을 포함한 탐구를 계획해 보세요.",
      "융합 역량":"서로 다른 교과 개념을 연결하여 동일한 문제를 해석한 사례를 찾아보세요."
    };
    Object.entries(categoryMax).forEach(([category, maximum]) => {
      const covered = Math.max(0, Number(item.categoryCoverage?.[category]) || 0);
      const rawScore = item.categoryScores?.[category];
      const value = rawScore == null || rawScore === "" ? NaN : Number(rawScore);
      const rated = covered > 0 && Number.isFinite(value);
      const row = el("div", "score-item seedu-indicator-row");
      const heading = el("div", "score-heading");
      heading.append(el("strong", "", category));
      heading.append(el("span", "score-number", rated ? `${value.toFixed(1)}점` : "평가 보류"));
      row.append(heading);
      if (rated) {
        const track = el("div", "bar-track");
        const fill = el("div", "bar-fill");
        fill.style.width = `${Math.max(0, Math.min(100, value / maximum * 100))}%`;
        track.append(fill);
        row.append(track);
      }
      const related = (item.indicatorDetails || []).filter(d => d && d.category === category);
      const explanation = el("div", "seedu-score-explanation");
      if (related.length) {
        related.forEach(d => {
          const indicator = el("div", "seedu-score-indicator");
          const weight = Number(d.weight) || 0;
          const rating = d.rating === null || d.rating === undefined ? NaN : Number(d.rating);
          const isRated = Number.isInteger(rating) && rating >= 0 && rating <= 4;
          const contribution = isRated ? (weight * rating / 4).toFixed(2).replace(/\.?0+$/, "") : null;
          indicator.append(el("strong", "", `${d.indicator || "세부 지표"} · ${weight}점 배점`));
          indicator.append(el("p", "seedu-indicator-criterion", `평가 기준: ${indicatorFocus[d.indicator] || "실제 수행 행동과 검증 가능한 기록"}`));
          if (isRated) {
            indicator.append(el("p", "", `${rating}/4등급 · 해당 지표 점수 ${contribution}점 (${weight} × ${rating}/4)`));
            indicator.append(el("p", "seedu-indicator-criterion", `등급의 일반적 의미: ${levelMeaning[rating] || "평가 가능한 자료에서 확인된 수행 수준"}. 실제 판단은 아래 연결된 기록을 확인해야 합니다.`));
            const quote = String(d.quote || "").trim();
            if (quote && d.verified) {
              const grade = d.grade ? `${d.grade}학년 · ` : "";
              const source = String(d.source || "출처 미표시");
              indicator.append(el("p", "seedu-indicator-source", `연결된 기록: ${grade}${source}`));
              indicator.append(el("p", "seedu-indicator-quote", evidenceSummary(quote)));
              appendEvidencePreview(indicator, quote, "근거 원문 보기");
            } else {
              indicator.append(el("p", "seedu-ne-guidance", "이 지표의 원문 근거가 전달되지 않았습니다. 점수의 타당성을 별도로 확인해야 합니다."));
            }
          } else {
            indicator.append(el("p", "seedu-ne-guidance", "평가 보류(N/E): 연결된 수행 근거가 부족합니다. 0점으로 계산하지 않습니다."));
          }
          explanation.append(indicator);
        });
      } else {
        explanation.append(el("p", "seedu-ne-guidance", "세부 지표별 점수·근거 자료가 분석 응답에 포함되지 않았습니다. 임의의 이유를 만들지 않습니다."));
      }
      row.append(explanation);
      if (!rated) row.append(el("p", "seedu-ne-guidance", `다음 탐색: ${nextAction[category]}`));
      details.append(row);
    });
    details.append(el("p", "seedu-rubric-provenance", "평가 체계: 교육·AI 관련 연구를 참고한 SEEDU:ON 자체 루브릭 3.2. 0~4등급, 16개 지표 및 30·25·20·15·10점 배점은 프로젝트 자체 설계 기준이며, 학술 논문에서 검증된 점수표를 그대로 사용한 것이 아닙니다."));
    box.append(details);
    majorList.append(box);
  });

  majors.append(majorList);

  majors.append(
    el(
      "p",
      "disclaimer",
      "※ 현재 입력된 학생부를 바탕으로 한 전공 탐색 결과입니다. 평가하지 못한 지표는 0점으로 간주하지 않으며, 부분 점수는 학과 순위나 합격 확률을 의미하지 않습니다."
    )
  );

  analysisResults.append(majors);

  // Make the next step reachable without scrolling past the full growth timeline.
  const roadmapCta = el("div", "seedu-roadmap-cta span-full");
  const ctaButton = el("button", "btn btn-primary", "희망 학과 선택하고 진로 로드맵 만들기 →");
  ctaButton.type = "button";
  ctaButton.addEventListener("click", () => {
    setupMajorSelection(data.majors);
    planResults.replaceChildren();
    showPage(3);
  });
  roadmapCta.append(ctaButton);
  analysisResults.append(roadmapCta);

  const growth = card("학년별 성장 과정", "span-full");
  const timeline = el("div", "growth-timeline");

  [...data.growth]
    .sort((a, b) => Number(a.grade) - Number(b.grade))
    .forEach((item) => {
      const row = el("div", "growth-item");

      row.append(
        el("span", "growth-year", `${item.grade}학년`)
      );
      const summary = dedupeGrowthSummary(String(item.summary || ''));
      row.append(el("p", "", evidenceSummary(summary)));
      appendEvidencePreview(row, summary, "성장 기록 원문 보기");

      timeline.append(row);
    });

  growth.append(timeline);
  analysisResults.append(growth);
}


/* =========================================
   2부: API 연결 및 데이터 형식 통일
========================================= */

const API_BASE = "https://seedu-on-api.onrender.com";

/* 다양한 AI 응답 형식을 하나로 통일 */

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value == null) return [];
  return [value];
}

function asText(value, fallback = "") {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (value == null) return fallback;
  return JSON.stringify(value);
}

function toScore(value, fallback = null) {
  if (value === null || value === undefined || value === "") return fallback;
  const number = Number(value);

  if (!Number.isFinite(number)) return fallback;

  return Math.max(0, Math.min(100, number));
}

function normalizeCompetencies(raw) {
  const source =
    raw.competencies ??
    raw.scores ??
    raw.abilities ??
    [];

  const defaultNames = [
    "학업역량",
    "진로역량",
    "탐구역량",
    "공동체역량",
    "성장가능성"
  ];

  if (Array.isArray(source)) {
    return defaultNames.map((name, i) => {
      const item = source[i] ?? {};

      if (typeof item === "number") {
        return {
          name,
          score: toScore(item),
          evidence: "세특 기록을 바탕으로 산출한 참고 점수입니다."
        };
      }

      return {
        name: asText(item.name ?? item.label, name),
        score: (item.score === null || item.status === "insufficient_evidence") ? null : toScore(item.score ?? item.value),
        evidence: asText(
          item.evidence ?? item.reason ?? item.description,
          "세특에서 확인된 활동을 바탕으로 평가했습니다."
        )
      };
    });
  }

  return defaultNames.map((name) => {
    const value = source[name];

    if (typeof value === "number") {
      return {
        name,
        score: toScore(value),
        evidence: "세특을 바탕으로 평가한 참고 점수입니다."
      };
    }

    return {
      name,
      score: (value?.score === null || value?.status === "insufficient_evidence") ? null : toScore(value?.score ?? value?.value),
      evidence: asText(
        value?.evidence ?? value?.reason,
        "세특에서 확인된 활동을 바탕으로 평가했습니다."
      )
    };
  });
}


function normalizeMajors(raw) {
  const source =
    raw.recommended_majors ??
    raw.majors ??
    raw.top_majors ??
    raw.recommendations ??
    [];

  const fitResults = Array.isArray(raw.major_fit)
    ? raw.major_fit
    : [];

  return asArray(source).slice(0, 3).map((item, i) => {
    const name = typeof item === "string"
      ? item
      : asText(
          item.major ?? item.name ?? item.department,
          `추천 학과 ${i + 1}`
        );

    const reason = typeof item === "string"
      ? "세특에 나타난 관심 분야를 바탕으로 추천했습니다."
      : asText(
          item.reason ?? item.description ?? item.explanation,
          "학생의 탐구 활동과 관심 분야를 고려했습니다."
        );

    const evaluation = fitResults.find(
      (entry) => entry.major === name
    );

    const score = Number(evaluation?.total_score);
    const hasScore =
      evaluation?.total_score != null &&
      Number.isFinite(score) &&
      score >= 0 &&
      score <= 100;

    return {
      name,
      reason,
      fit: hasScore ? score : null,
      scoreStatus: evaluation?.score_status || (hasScore ? "complete" : "insufficient_evidence"),
      partialScore: evaluation?.partial_score != null ? Number(evaluation.partial_score) : null,
      coverageWeight: Number(evaluation?.coverage_weight ?? 0),
      categoryScores: evaluation?.category_scores ?? {},
      indicatorDetails: asArray(evaluation?.indicator_details),
      categoryCoverage: evaluation?.category_coverage_weight ?? (Array.isArray(evaluation?.indicator_details) ? evaluation.indicator_details.reduce((acc,d) => { if (Number.isInteger(d.rating)) acc[d.category] = (acc[d.category] || 0) + Number(d.weight || 0); return acc; }, {}) : {}),
      evidence: asText(evaluation?.evidence, ""),
      improvement: asText(evaluation?.improvement, ""),
      evidenceSources: asArray(evaluation?.evidence_sources).map(x => ({
        grade: x.grade, source: asText(x.source), quote: asText(x.quote)
      }))
    };
  });
}


function normalizeGrowth(raw, currentGrade) {
  const source =
    raw.growth ??
    raw.growth_analysis ??
    raw.grade_growth ??
    [];

  if (Array.isArray(source)) {
    return source.map((item, i) => {
      if (typeof item === "string") {
        return {
          grade: i + 1,
          summary: item
        };
      }

      return {
        grade: Number(item.grade) || i + 1,
        summary: asText(
          item.summary ?? item.description ?? item.analysis,
          "학년별 활동 분석"
        )
      };
    });
  }

  if (typeof source === "string" && source.trim()) {
    return [{
      grade: currentGrade,
      summary: source
    }];
  }

  if (source && typeof source === "object") {
    return Object.entries(source).map(([grade, value]) => ({
      grade: Number(grade.replace(/\D/g, "")) || currentGrade,
      summary: asText(value)
    }));
  }

  return [{
    grade: currentGrade,
    summary: "입력된 세특을 바탕으로 성장 방향을 분석했습니다."
  }];
}

function normalizeAnalysis(raw, currentGrade) {
  if (!raw || typeof raw !== "object") {
    throw new Error("AI 분석 결과가 비어 있습니다.");
  }

  // 서버가 결과를 data 또는 result 안에 넣은 경우
  const data = raw.data ?? raw.result ?? raw;

  const competencies = normalizeCompetencies(data);
  const majors = normalizeMajors(data);


  return {
    competencies,
    majors,
    aiReview: data.ai_review ?? {used:false,status:"skipped"},
    inputCoverage: data.input_coverage ? {
      activitiesReceived: Number(data.input_coverage.activities_received ?? 0),
      activitiesProcessed: Number(data.input_coverage.activities_processed ?? 0),
      activitiesWithVerifiedFacts: Number(data.input_coverage.activities_with_verified_facts ?? 0),
      activities: asArray(data.input_coverage.activities).map(item => ({
        grade: item.grade, source: asText(item.source),
        inputChars: Number(item.input_chars ?? 0),
        processedChars: Number(item.processed_chars ?? 0),
        verifiedFacts: Number(item.verified_facts ?? 0)
      }))
    } : null,
    growth: normalizeGrowth(data, currentGrade),
    strengths: asArray(
      data.strengths ?? data.strong_points ?? []
    ).map((item) => asText(item)),
    improvements: asArray(
      data.weaknesses ??
      data.improvements ??
      data.weak_points ??
      []
    ).map((item) => asText(item))
  };
}

/* =========================================
   로드맵 데이터 형식 통일
========================================= */

function roadmapList(value) {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  if (typeof value === "object") return Object.entries(value).map(([name, info]) =>
    typeof info === "object" && info !== null ? { name, ...info } : { name, reason: String(info) }
  );
  return [value];
}

function normalizeRoadmap(raw) {
  if (!raw || typeof raw !== "object") throw new Error("로드맵 응답이 비어 있습니다.");
  const data = raw.data ?? raw.result ?? raw.roadmap ?? raw;
  const subjectRaw = data.recommended_subjects ?? data.subjects ?? data.electives ?? data.subject_recommendations ?? [];
  const activityRaw = data.research_activities ?? data.activities ?? data.projects ?? data.exploration_activities ?? data.recommended_activities ?? [];
  const gradeRaw = data.grade_plan ?? data.gradePlan ?? data.yearly_plan ?? data.timeline ?? [];
  const subjects = roadmapList(subjectRaw).map((item) => typeof item === "string"
    ? { name: item, reason: "" }
    : { name: asText(item.subject ?? item.name ?? item.title, "추천 과목"), reason: asText(item.reason ?? item.description ?? item.detail, "") }
  );
  const activities = roadmapList(activityRaw).map((item, i) => typeof item === "string"
    ? { title:item, description:"", steps:[], expectedResult:"", recordConnection:"", researchQuestion:"", duration:"", dataToCollect:"", evaluation:"", extension:"" }
    : { title:asText(item.title ?? item.name ?? item.activity, `탐구활동 ${i+1}`),
        description:asText(item.description ?? item.detail ?? item.reason, ""),
        steps:roadmapList(item.steps ?? item.process ?? item.actions ?? []).map(x => asText(x.name ?? x.action ?? x.step ?? x)),
        expectedResult:asText(item.expected_result ?? item.expectedResult ?? item.output, ""),
        recordConnection:asText(item.record_connection ?? item.recordConnection, ""),
        researchQuestion:asText(item.research_question ?? item.researchQuestion, ""),
        duration:asText(item.duration, ""),
        dataToCollect:asText(item.data_to_collect ?? item.dataToCollect, ""),
        evaluation:asText(item.evaluation, ""),
        extension:asText(item.extension, "") }
  );
  const gradePlan = roadmapList(gradeRaw).map((item, i) => {
    if (typeof item === "string") return {grade:i+1, goal:item, actions:[], deliverable:""};
    return { grade:Number(item.grade) || Number(String(item.name ?? "").replace(/\D/g,"")) || i+1,
      goal:asText(item.goal ?? item.title ?? item.summary ?? item.name,""),
      actions:roadmapList(item.actions ?? item.tasks ?? item.steps ?? []).map(x => asText(x.name ?? x.action ?? x.task ?? x)),
      deliverable:asText(item.deliverable ?? item.output, "") };
  });
  const advice = asText(data.advice ?? data.summary ?? data.final_advice ?? data.guidance, "");
  if (!subjects.length && !activities.length && !gradePlan.length && !advice) {
    throw new Error("서버에서 로드맵 내용이 전달되지 않았습니다. 백엔드 /roadmap 응답 형식을 확인해 주세요.");
  }
  return {major:asText(data.major ?? data.target_major,""),subjects,activities,gradePlan,advice,proposalMode:asText(data.analysis_mode,"")};
}

/* =========================================
   Render 서버 요청
========================================= */

async function apiRequest(path, payload) {
  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch (error) {
    throw new Error(
      "AI 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
    );
  }

  let result;

  try {
    result = await response.json();
  } catch (error) {
    throw new Error(
      "서버에서 올바른 JSON 응답을 받지 못했습니다."
    );
  }

  if (!response.ok) {
    const detail =
      typeof result.detail === "string"
        ? result.detail
        : JSON.stringify(result.detail ?? result);

    throw new Error(
      `서버 오류 (${response.status}): ${detail}`
    );
  }

  return result;
}


/* =========================================
   3부: 로드맵 화면 출력 및 버튼 연결
========================================= */

let selectedMajor = "";

/* 로드맵 화면 출력: 긴 탐구 계획은 한 줄 카드가 아닌 전체 너비 세로 카드 */
function roadmapField(parent, title, value) {
  if (!value || (Array.isArray(value) && !value.length)) return;
  const field = el("div", "roadmap-detail-field");
  field.append(el("h4", "roadmap-detail-label", title));
  if (Array.isArray(value)) {
    const list = el("ul", "roadmap-detail-list");
    value.forEach(v => list.append(el("li", "", v)));
    field.append(list);
  } else {
    field.append(el("p", "roadmap-detail-value", value));
  }
  parent.append(field);
}

function renderRoadmap(data) {
  planResults.replaceChildren();
  const personalized = data.proposalMode === "ai_record_grounded_proposals";
  const intro = el("div", "result-intro");
  intro.append(
    el("p", "eyebrow", "SEEDU:ON · PERSONAL ROADMAP"),
    el("h2", "result-title", `${data.major || selectedMajor} 진로 로드맵`),
    el("p", "muted", personalized
      ? "학생부에서 확인된 활동을 바탕으로 향후 수행할 탐구 계획을 제안합니다."
      : "전공 분야별 탐구 설계 예시입니다. 학생부를 직접 해석한 개인화 결과는 아닙니다.")
  );
  planResults.append(intro);

  const matchedMajor = latestAnalysis?.majors?.find(item => item.name === (data.major || selectedMajor));
  const majorFeedbackCard = card("희망 학과 기준 · 나의 강점과 보완 방향", "span-full seedu-roadmap-major-feedback");
  if (matchedMajor) {
    const linked = buildMajorFeedback(matchedMajor);
    const columns = el("div", "seedu-feedback-grid");
    const a = card("전공 연계 강점", "feedback-card strength-card");
    const b = card("전공 연계 보완 방향", "feedback-card improve-card");
    appendFeedbackList(a, linked.strengths);
    appendFeedbackList(b, linked.improvements);
    columns.append(a, b);
    majorFeedbackCard.append(columns);
  } else {
    majorFeedbackCard.append(el("p", "muted", "선택 학과와 연결된 검증 근거가 이전 분석 결과에 없습니다. 이 전공의 강점을 추측하지 않고, 아래에 후속 탐구 계획만 제안합니다."));
  }
  planResults.append(majorFeedbackCard);

  const subjectCard = card("추천 선택과목 · 왜 필요한가요?");
  subjectCard.append(el("p", "roadmap-section-note", "실제 학교 개설 과목과 교육과정에 따라 과목명·선택 가능 여부가 달라질 수 있습니다."));
  const subjectList = el("div", "subject-list");
  data.subjects.forEach(item => {
    const box = el("div", "subject-item");
    box.append(el("h3", "", item.name));
    if (item.reason) box.append(el("p", "evidence", item.reason));
    subjectList.append(box);
  });
  subjectCard.append(data.subjects.length ? subjectList : el("p", "muted", "추천 과목 정보가 없습니다."));
  planResults.append(subjectCard);

  const activityCard = card("심화 탐구활동 TOP 3 · 실행 계획");
  activityCard.append(el("p", "roadmap-section-note", "각 활동은 연구 질문 → 수행 절차 → 검증 → 결과물 순서로 설계했습니다. 이미 수행한 활동으로 기록하지 마세요."));
  const activityList = el("div", "activity-list");
  data.activities.slice(0,3).forEach((item,i) => {
    const box = el("article", "activity-item roadmap-project");
    const heading = el("div", "roadmap-project-heading");
    heading.append(el("span", "activity-number", `PROJECT 0${i+1}`),el("h3", "", item.title));
    if (item.duration) heading.append(el("span", "roadmap-duration", item.duration));
    box.append(heading);
    roadmapField(box, "기록과 연결되는 이유", item.recordConnection);
    roadmapField(box, "핵심 탐구 질문", item.researchQuestion);
    roadmapField(box, "탐구 목적", item.description);
    if (item.steps.length) {
      const field = el("div", "roadmap-detail-field");
      field.append(el("h4", "roadmap-detail-label", "구체적인 수행 절차"));
      const list = el("ol", "activity-steps");
      item.steps.forEach(step => list.append(el("li", "", step)));
      field.append(list);
      box.append(field);
    }
    roadmapField(box, "수집·측정할 자료", item.dataToCollect);
    roadmapField(box, "결과 검증 기준", item.evaluation);
    roadmapField(box, "최종 산출물", item.expectedResult);
    roadmapField(box, "다음 심화 탐구", item.extension);
    activityList.append(box);
  });
  activityCard.append(data.activities.length ? activityList : el("p", "muted", "추천 탐구활동 정보가 없습니다."));
  planResults.append(activityCard);

  const gradeCard = card("학년별 성장 로드맵");
  if (!data.gradePlan.length) gradeCard.append(el("p", "muted", "학년별 계획 정보가 없습니다."));
  data.gradePlan.forEach(item => {
    const box = el("div", "grade-plan-item");
    box.append(el("h3", "", `${item.grade}학년 · ${item.goal}`));
    if (item.actions.length) {
      const list = el("ul", "grade-actions");
      item.actions.forEach(action => list.append(el("li", "", action)));
      box.append(list);
    }
    roadmapField(box,"학년별 목표 산출물",item.deliverable);
    gradeCard.append(box);
  });
  planResults.append(gradeCard);

  if (data.advice) {
    const adviceCard = card("AI 진로 코칭 · 확인할 점");
    adviceCard.append(el("p", "advice-text", data.advice));
    planResults.append(adviceCard);
  }
}

/* =========================================
   입력 데이터 수집
========================================= */

function collectRecords() {
  saveRecord();

  const current = Number(gradeSelect.value);
  const records = {};

  for (let grade = 1; grade <= current; grade++) {
    records[String(grade)] = studentRecords[grade].trim();
  }

  return records;
}

function collectSubjects() {
  const checked = document.querySelectorAll(
    'input[name="subjects"]:checked, input[name="subject"]:checked'
  );

  return [...checked].map((input) =>
    input.value
  );
}

function setLoading(button, loading, message) {
  if (!button) return;

  if (loading) {
    button.dataset.originalText = button.textContent;
    button.disabled = true;
    button.textContent = message;
  } else {
    button.disabled = false;
    button.textContent =
      button.dataset.originalText || button.textContent;
  }
}

/* =========================================
   AI 역량 분석 실행
========================================= */

async function runAnalysis() {
  const records = collectRecords();
  const currentGrade = Number(gradeSelect.value);

  const combinedText = Object.entries(records)
    .filter(([, text]) => text)
    .map(([grade, text]) =>
      `[${grade}학년]\n${text}`
    )
    .join("\n\n");

  if (!combinedText.trim()) {
    alert("세특 내용을 먼저 입력해 주세요.");
    return;
  }

  setLoading(analyzeButton, true, "루브릭 분석 중...");

  try {
    const response = await apiRequest("/analyze", {
      grade: currentGrade,
      records,
      text: combinedText,
      subjects: collectSubjects()
    });

    const data = normalizeAnalysis(
      response,
      currentGrade
    );

    latestAnalysis = data;
    latestAnalyzedRecords = { ...records };
    renderDashboard(data);
    showPage(2);

    // 분석 서비스 장애 시 무효한 결과를 정상 평가처럼 저장하지 않는다.
    if (data.aiReview?.status === "error" || data.aiReview?.status === "fallback") return;

    // 추천 학과 선택 버튼 생성
    setupMajorSelection(data.majors);

    // 로그인 상태면 결과 저장, 비회원이면 저장 배너 표시
    onAnalysisComplete(data, currentGrade);

  } catch (error) {
    console.error("AI 분석 오류:", error);
    alert(error.message);
  } finally {
    setLoading(analyzeButton, false);
  }
}

/* =========================================
   추천 학과 선택
========================================= */

function setupMajorSelection(majors) {
  const container =
    $("major-selection") ||
    $("major-options");

  if (!container) return;

  container.replaceChildren();
  selectedMajor = "";

  majors.forEach((major, index) => {
    const button = el(
      "button",
      "major-select-button",
      major.name
    );

    button.type = "button";

    button.addEventListener("click", () => {
      selectedMajor = major.name;

      container.querySelectorAll("button").forEach(
        (item) => item.classList.remove("active")
      );

      button.classList.add("active");

      const input =
        $("custom-major") ||
        $("major-input");

      if (input) input.value = "";
    });

    container.append(button);

    if (index === 0) {
      button.click();
    }
  });
}

/* =========================================
   AI 로드맵 생성
========================================= */

function roadmapStatus(message, isError = false) {
  planResults.replaceChildren();
  const box = el("section", `result-card seedu-roadmap-status${isError ? " seedu-roadmap-error" : ""}`);
  box.setAttribute("role", "status");
  box.append(el("h2", "card-heading", isError ? "로드맵을 표시하지 못했어요" : "진로 로드맵 생성 중"));
  box.append(el("p", "", message));
  if (isError) {
    const retry = el("button", "btn btn-primary", "다시 생성하기");
    retry.type = "button";
    retry.addEventListener("click", runRoadmap);
    box.append(retry);
  }
  planResults.append(box);
}

async function runRoadmap() {
  const majorInput = $("custom-major") || $("major-input");
  const customMajor = majorInput?.value.trim() || "";
  const major = customMajor || selectedMajor;
  if (!major) { alert("희망 학과를 선택하거나 직접 입력해 주세요."); majorInput?.focus(); return; }
  const button = $("roadmap-button") || $("generate-roadmap");
  setLoading(button, true, "맞춤 로드맵 생성 중...");
  roadmapStatus(`${major}에 맞는 선택과목과 탐구활동을 확인하고 있습니다.`);
  try {
    const currentRecords = collectRecords();
    const records = Object.values(currentRecords).some(v => String(v || "").trim())
      ? currentRecords : (latestAnalyzedRecords || {});
    const text = Object.entries(records).filter(([,v]) => String(v).trim()).map(([g,v]) => `[${g}학년]\n${v}`).join("\n\n");
    if (!text.trim()) throw new Error("로드맵을 만들 학생부 원문이 없습니다. 생기부 입력 화면에서 기록을 불러온 뒤 다시 시도해 주세요.");
    const response = await apiRequest("/roadmap", {
      grade:Number(gradeSelect.value), major, records, text, analysis:latestAnalysis
    });
    const data = normalizeRoadmap(response);
    renderRoadmap({...data, major:data.major || major});
    planResults.scrollIntoView({behavior:"smooth",block:"start"});
  } catch (error) {
    console.error("로드맵 생성 오류:", error);
    roadmapStatus(error.message || "로드맵 서버 응답을 확인하지 못했습니다.", true);
  } finally { setLoading(button, false); }
}

/* =========================================
   이벤트 연결
========================================= */

function initializeApp() {
  if (!gradeSelect || !textarea || !analyzeButton) {
    console.error(
      "필수 HTML 요소를 찾지 못했습니다. index.html의 ID를 확인하세요."
    );
    return;
  }

  gradeTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      switchGrade(Number(tab.dataset.grade));
    });
  });

  gradeSelect.addEventListener(
    "change",
    updateVisibleGrades
  );

  textarea.addEventListener(
    "input",
    updateCount
  );

  analyzeButton.addEventListener(
    "click",
    runAnalysis
  );

  const roadmapButton =
    $("roadmap-button") ||
    $("generate-roadmap");

  if (roadmapButton) {
    roadmapButton.addEventListener(
      "click",
      runRoadmap
    );
  }

  const goRoadmapButton = $("go-to-plan");

if (goRoadmapButton) {
  goRoadmapButton.addEventListener("click", () => {
    if (!latestAnalysis) {
      alert("AI 역량 분석을 먼저 진행해 주세요.");
      return;
    }
    setupMajorSelection(latestAnalysis.majors);
    planResults.replaceChildren();
    showPage(3);
  });
}

  const backButtons =
    document.querySelectorAll("[data-go-page]");

  backButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const page = Number(button.dataset.goPage);
      if ([0, 1, 2, 3, 4].includes(page)) {
        showPage(page);
      }
    });
  });

  // 디자인용 학년 라디오 버튼 → 기존 #current-grade 선택값과 동기화
  document
    .querySelectorAll('input[name="current-grade-choice"]')
    .forEach((radio) => {
      radio.checked = radio.value === gradeSelect.value;
      radio.addEventListener("change", () => {
        if (!radio.checked) return;
        gradeSelect.value = radio.value;
        gradeSelect.dispatchEvent(new Event("change"));
      });
    });

  updateVisibleGrades();
  updateCount();
  showPage(0); // 홈 화면에서 시작

  console.log("SEEDU:ON 초기화 완료");
}

if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeApp
  );
} else {
  initializeApp();
}


/* =========================================
   SEEDU:ON 학년별 과목 선택 및 세특 등록
   기존 script.js 맨 아래에 추가
========================================= */

(() => {
  const SUBJECT_LIST = {
    1: [
      "공통국어1", "공통국어2",
      "공통수학1", "공통수학2",
      "공통영어1", "공통영어2",
      "한국사1", "한국사2",
      "통합사회1", "통합사회2",
      "통합과학1", "통합과학2",
      "과학탐구실험1", "과학탐구실험2",
      "체육1", "체육2", "미술", "음악"
    ],

    2: [
      "문학", "화법과 언어",
      "대수", "미적분Ⅰ",
      "영어Ⅰ", "영어Ⅱ",
      "스포츠생활1", "스포츠생활2",
      "일본어", "일본어회화",
      "중국어", "중국어회화",
      "정보", "인공지능기초",
      "주제탐구독서", "문학과 영상",
      "경제수학", "기하",
      "영미문학읽기", "인공지능수학",
      "세계시민과 지리", "영어발표와 토론",
      "경제", "도시의 미래 탐구",
      "정치", "사회와 문화",
      "현대사회와 윤리", "윤리와 사상",
      "세계사", "동아시아 역사 기행",
      "물리학", "역학과 에너지",
      "화학", "물질과 에너지",
      "생명과학", "세포와 물질대사",
      "지구과학", "융합과학탐구"
    ],


  };

 
  // ========================================
  // SEEDU:ON 학생부 영역별 기록 등록
  // ========================================

  const CATEGORY_NAMES = {
    subject: "교과 세특",
    autonomy: "자율·자치활동",
    club: "동아리활동",
    career: "진로활동",
    behavior: "행동특성 및 종합의견"
  };

  const registeredActivities = {
    1: [],
    2: []
  };

  let editingId = null;

  function initSubjectInput() {
    const categorySelect =
      document.getElementById("record-category");
    const subjectSelect =
      document.getElementById("subject-select");
    const subjectField =
      document.getElementById("subject-field");
    const activityField =
      document.getElementById("activity-field");
    const activityTitle =
      document.getElementById("activity-title");
    const subjectRecord =
      document.getElementById("subject-record");
    const contentLabel =
      document.getElementById("record-content-label");
    const addButton =
      document.getElementById("add-subject-button");
    const registeredBox =
      document.getElementById("registered-subjects");
    const hiddenRecord =
      document.getElementById("student-record");
    const characterCount =
      document.getElementById("character-count");
    const currentGradeSelect =
      document.getElementById("current-grade");
    const analyzeButton =
      document.getElementById("analyze-button");

    const required = [
      categorySelect,
      subjectSelect,
      subjectField,
      activityField,
      activityTitle,
      subjectRecord,
      contentLabel,
      addButton,
      registeredBox,
      hiddenRecord,
      characterCount,
      currentGradeSelect,
      analyzeButton
    ];

    if (required.some(element => !element)) {
      console.error("학생부 입력 HTML 요소가 없습니다.");
      return;
    }

    function createId() {
      if (
        typeof crypto !== "undefined" &&
        typeof crypto.randomUUID === "function"
      ) {
        return crypto.randomUUID();
      }

      return Date.now().toString(36) + "-" +
        Math.random().toString(36).slice(2);
    }

    function resetForm() {
      editingId = null;
      subjectSelect.value = "";
      activityTitle.value = "";
      subjectRecord.value = "";
      addButton.textContent = "+ 기록 등록하기";
    }

    function updateCategoryUI() {
      const category = categorySelect.value;
      const isSubject = category === "subject";
      const isBehavior = category === "behavior";

      subjectField.hidden = !isSubject;
      activityField.hidden = isSubject || isBehavior;

      contentLabel.textContent = isSubject
        ? "세부능력 및 특기사항"
        : "학생부 활동 기록 내용";

      subjectRecord.placeholder = isSubject
        ? "선택한 과목의 세특 내용을 입력하세요."
        : "학생부에 기재된 활동 내용을 입력하세요.";
    }

    function updateSubjectOptions() {
      const grade = activeGrade;

      subjectSelect.replaceChildren();

      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "과목을 선택하세요";
      subjectSelect.append(placeholder);

      (SUBJECT_LIST[grade] || []).forEach(name => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        subjectSelect.append(option);
      });

      resetForm();
      updateCategoryUI();
      renderRegisteredActivities();
      syncRecords();
    }

    function makeGradeText(grade) {
      return registeredActivities[grade]
        .map(item => {
          const label = CATEGORY_NAMES[item.category];

          const heading = item.category === "subject"
            ? `[과목: ${item.title}]`
            : `[${label}: ${item.title}]`;

          return `${heading}\n${item.content}`;
        })
        .join("\n\n");
    }

    // 기존 분석 API와 데이터 형식 호환
    function syncRecords() {
      for (let grade = 1; grade <= 2; grade++) {
        studentRecords[grade] = makeGradeText(grade);
      }

      hiddenRecord.value = studentRecords[activeGrade];

      const currentGrade = Number(currentGradeSelect.value);

      let total = 0;

      for (let grade = 1; grade <= currentGrade; grade++) {
        total += studentRecords[grade].length;
      }

      characterCount.textContent =
        `${activeGrade}학년: ` +
        `${studentRecords[activeGrade].length.toLocaleString()}자` +
        ` / 전체: ${total.toLocaleString()}자`;
    }

    // 등록된 학생부 기록 출력
    function renderRegisteredActivities() {
      registeredBox.replaceChildren();

      const records = registeredActivities[activeGrade];

      if (records.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "아직 등록한 기록이 없습니다.";
        registeredBox.append(empty);
        return;
      }

      records.forEach(item => {
        const row = document.createElement("div");
        row.className = "registered-subject-item";

        const info = document.createElement("div");
        info.className = "registered-subject-info";

        const title = document.createElement("strong");
        title.textContent =
          `${CATEGORY_NAMES[item.category]} · ${item.title}`;

        const detail = document.createElement("p");
        detail.textContent =
          `${item.content.length}자 등록됨`;

        info.append(title, detail);

        const actions = document.createElement("div");
        actions.className = "registered-subject-actions";

        // 수정
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "subject-edit-button";
        edit.textContent = "수정";

        edit.addEventListener("click", () => {
          editingId = item.id;
          categorySelect.value = item.category;

          updateCategoryUI();

          subjectSelect.value =
            item.category === "subject"
              ? item.title
              : "";

          activityTitle.value =
            item.category === "subject" ||
            item.category === "behavior"
              ? ""
              : item.title;

          subjectRecord.value = item.content;
          addButton.textContent = "변경 내용 저장하기";

          subjectRecord.focus();
          subjectRecord.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
        });

        // 삭제
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "subject-delete-button";
        remove.textContent = "삭제";

        remove.addEventListener("click", () => {
          if (!confirm(
            `${item.title} 기록을 삭제할까요?`
          )) {
            return;
          }

          registeredActivities[activeGrade] =
            registeredActivities[activeGrade].filter(
              record => record.id !== item.id
            );

          if (editingId === item.id) {
            resetForm();
          }

          renderRegisteredActivities();
          syncRecords();
        });

        actions.append(edit, remove);
        row.append(info, actions);
        registeredBox.append(row);
      });
    }

    // 학생부 영역 변경
    categorySelect.addEventListener("change", () => {
      resetForm();
      updateCategoryUI();
    });

    // 과목 선택 변경 중 수정 상태 해제
    subjectSelect.addEventListener("change", () => {
      if (editingId !== null) {
        const existing = registeredActivities[activeGrade]
          .find(item => item.id === editingId);

        if (
          existing &&
          existing.category === "subject" &&
          existing.title !== subjectSelect.value
        ) {
          editingId = null;
          addButton.textContent = "+ 기록 등록하기";
        }
      }
    });

    // 학생부 기록 등록 및 수정
    addButton.addEventListener("click", () => {
      const category = categorySelect.value;
      const content = subjectRecord.value.trim();

      const title = category === "subject"
        ? subjectSelect.value
        : category === "behavior"
          ? "행동특성 및 종합의견"
          : activityTitle.value.trim() ||
            CATEGORY_NAMES[category];

      if (!title || !content) {
        alert("활동 유형과 기록 내용을 입력해 주세요.");
        return;
      }

      const records = registeredActivities[activeGrade];

      // 동일 학년의 동일 과목 중복 방지
      const duplicate = records.find(item =>
        item.category === "subject" &&
        category === "subject" &&
        item.title === title &&
        item.id !== editingId
      );

      if (duplicate) {
        alert(
          "이미 등록한 과목입니다. 수정 버튼을 이용하세요."
        );
        return;
      }

      if (editingId !== null) {
        const existing = records.find(
          item => item.id === editingId
        );

        if (!existing) {
          alert("수정할 기록을 찾을 수 없습니다.");
          resetForm();
          return;
        }

        existing.category = category;
        existing.title = title;
        existing.content = content;
      } else {
        records.push({
          id: createId(),
          category,
          title,
          content
        });
      }

      resetForm();
      renderRegisteredActivities();
      syncRecords();
    });

    // 기존 학년 전환 기능과 연동
    document.querySelectorAll(".grade-tab").forEach(tab => {
      tab.addEventListener("click", updateSubjectOptions);
    });

    currentGradeSelect.addEventListener(
      "change",
      updateSubjectOptions
    );

    // AI 분석 직전 등록 여부 검사
    analyzeButton.addEventListener(
      "click",
      event => {
        syncRecords();

        const current =
          Number(currentGradeSelect.value);

        const hasRecords = [1, 2].some(grade =>
          grade <= current &&
          registeredActivities[grade].length > 0
        );

        if (!hasRecords) {
          event.stopImmediatePropagation();
          alert("학생부 기록을 먼저 등록해 주세요.");
          return;
        }

        if (subjectRecord.value.trim()) {
          event.stopImmediatePropagation();
          alert(
            "작성 중인 내용을 먼저 등록해 주세요."
          );
        }
      },
      true
    );

    updateSubjectOptions();

    console.log(
      "SEEDU:ON 학생부 영역별 입력 기능 초기화 완료"
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initSubjectInput
    );
  } else {
    initSubjectInput();
  }
})();


/* =========================================
   SEEDU:ON 로그인 / 분석 기록 저장
   - 로그인·기록 API는 같은 사이트의 /api/... 로 요청한다
     (Vercel이 Render 서버로 넘겨 준다 → httpOnly 쿠키 사용)
   - 기존 /analyze, /roadmap 호출은 바꾸지 않는다
   - 생기부 원문은 저장하지 않는다 (분석 결과 + 학년 + 과목명만 저장)
========================================= */

const auth = { loggedIn: false, username: null };

// 결과 화면 상태: "live"(방금 분석) / "saved"(저장된 기록) / "sample"(예시)
let analysisMode = "live";
let currentLive = null;   // { grade, subjects, result, savedId, saving, error }
let viewingRecord = null; // 저장된 기록을 볼 때의 요약 정보

const SAMPLE_ANALYSIS = {
  competencies: [
    { name: "학업역량", score: 75, evidence: "(예시) 미분 단원의 변화율 개념을 실제 기록 자료에 적용함." },
    { name: "진로역량", score: 75, evidence: "(예시) 데이터 분석과 관련된 탐구를 꾸준히 이어 감." },
    { name: "탐구역량", score: 100, evidence: "(예시) 구간별 평균 변화율을 직접 계산하고 해석함." },
    { name: "공동체역량", score: 50, evidence: "(예시) 모둠 활동에서 맡은 역할이 기록에 잘 드러나지 않음." },
    { name: "성장가능성", score: 75, evidence: "(예시) 한계를 스스로 짚고 다음 계획을 제시함." }
  ],
  majors: [
    { name: "데이터사이언스학과", reason: "(예시) 측정, 분석, 가설 검증 기록이 이 학과의 핵심 역량과 연결돼요.", fit: 84,
      categoryScores: { "전공 관련 활동": 25, "학업 역량": 21, "관심의 지속성": 17, "탐구 심화도": 13, "융합 역량": 8 },
      evidence: "", improvement: "" },
    { name: "해양환경과학과", reason: "(예시) 관찰과 변수 통제 경험이 연결되지만 직접 근거는 적어요.", fit: 66,
      categoryScores: {}, evidence: "", improvement: "" },
    { name: "수학교육과", reason: "(예시) 설명하고 질문하는 기록이 보이지만 교육 관련 활동은 적어요.", fit: 62,
      categoryScores: {}, evidence: "", improvement: "" }
  ],
  growth: [{ grade: 2, summary: "(예시) 자료를 직접 수집하고 분석하며 탐구가 깊어짐." }],
  strengths: ["직접 측정하고 해석함", "한계를 스스로 짚음"],
  improvements: ["협업·소통 근거가 적음"]
};

/* ---------- API ---------- */

async function accountRequest(method, path, body) {
  let response;

  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined
    });
  } catch (error) {
    throw new Error("서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const detail = data && typeof data.detail === "string"
      ? data.detail
      : "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.";
    const err = new Error(detail);
    err.status = response.status;
    throw err;
  }

  return data;
}

/* ---------- 공통 화면 도우미 ---------- */

let toastTimer = null;

function showToast(message) {
  const toast = $("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3200);
}

function formatDate(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}.${pad(date.getMonth() + 1)}.${pad(date.getDate())}`;
}

function subjectsLabel(subjects) {
  if (!subjects || subjects.length === 0) return "";
  if (subjects.length <= 2) return subjects.join(", ");
  return `${subjects.slice(0, 2).join(", ")} 외 ${subjects.length - 2}개`;
}

function setAuth(loggedIn, username) {
  auth.loggedIn = loggedIn;
  auth.username = loggedIn ? username : null;
  document.body.dataset.auth = loggedIn ? "in" : "out";
  const name = $("header-username");
  if (name) name.textContent = auth.username || "";
  renderResultExtra();
}

// 분석 결과에 쓰인 과목명만 모은다 (세특 원문은 보내지 않는다)
function collectSubjectNames(grade) {
  const names = [];
  for (let g = 1; g <= grade; g++) {
    const text = studentRecords[g] || "";
    for (const match of text.matchAll(/\[과목: ([^\]\n]+)\]/g)) {
      names.push(match[1].trim());
    }
  }
  return [...new Set(names)];
}

/* ---------- 모달 (로그인 / 비회원 안내) ---------- */

let modalOpener = null;

function openDialog(id) {
  const dialog = $(id);
  if (!dialog) return;
  if (!dialog.open) {
    if (!modalOpener) modalOpener = document.activeElement;
    dialog.showModal();
  }
}

function closeDialog(id, restoreFocus = true) {
  const dialog = $(id);
  if (dialog && dialog.open) dialog.close();
  if (restoreFocus && modalOpener && document.contains(modalOpener)) {
    modalOpener.focus();
  }
  if (restoreFocus) modalOpener = null;
}

function setLoginError(message) {
  const box = $("login-error");
  const text = $("login-error-text");
  const fields = [$("login-username"), $("login-password")];

  if (message) {
    text.textContent = message;
    box.hidden = false;
    fields.forEach((field) => field.setAttribute("aria-invalid", "true"));
  } else {
    text.textContent = "";
    box.hidden = true;
    fields.forEach((field) => field.removeAttribute("aria-invalid"));
  }
}

function openLogin() {
  setLoginError("");
  openDialog("login-dialog");
  $("login-username").focus();
}

async function submitLogin(event) {
  event.preventDefault();

  const username = $("login-username").value.trim();
  const password = $("login-password").value;

  if (!/^[A-Za-z0-9]{4,16}$/.test(username)) {
    setLoginError("아이디는 영문과 숫자로 4~16자여야 해요.");
    $("login-username").focus();
    return;
  }
  if (password.length < 6) {
    setLoginError("비밀번호는 6자 이상이어야 해요.");
    $("login-password").focus();
    return;
  }

  const button = $("login-submit");
  setLoginError("");
  setLoading(button, true, "확인 중...");

  try {
    const data = await accountRequest("POST", "/api/auth/login", { username, password });

    $("login-form").reset();
    closeDialog("login-dialog");
    setAuth(true, data.username);
    showToast(data.created
      ? `새 계정이 만들어졌어요. ${data.username}님, 환영해요!`
      : `${data.username}님, 다시 만나서 반가워요.`);

    // 방금 본 결과가 아직 저장되지 않았다면 바로 저장
    if (currentLive && !currentLive.savedId) saveLiveResult();
  } catch (error) {
    setLoginError(error.message);
    $("login-password").value = "";
    $("login-password").focus();
  } finally {
    setLoading(button, false);
  }
}

async function logout() {
  try {
    await accountRequest("POST", "/api/auth/logout");
  } catch (error) {
    // 서버 오류여도 화면은 로그아웃 상태로 바꾼다
  }
  setAuth(false, null);
  showToast("로그아웃했어요.");
  if (!$("records-page").hidden || analysisMode === "saved") showPage(0);
}

/* ---------- 분석 결과 저장 ---------- */

function onAnalysisComplete(data, grade) {
  analysisMode = "live";
  viewingRecord = null;
  currentLive = {
    grade,
    subjects: collectSubjectNames(grade),
    result: data,
    savedId: null,
    saving: false,
    error: ""
  };

  if (auth.loggedIn) saveLiveResult();
  else renderResultExtra();
}

async function saveLiveResult() {
  if (!currentLive || currentLive.savedId || currentLive.saving) return;

  currentLive.saving = true;
  currentLive.error = "";
  renderResultExtra();

  try {
    const saved = await accountRequest("POST", "/api/records", {
      grade: currentLive.grade,
      subjects: currentLive.subjects,
      result: currentLive.result
    });
    currentLive.savedId = saved.id;
  } catch (error) {
    if (error.status === 401) setAuth(false, null);
    currentLive.error = error.message;
  } finally {
    currentLive.saving = false;
    renderResultExtra();
  }
}

function infoIcon() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("notice-icon");
  svg.innerHTML = '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.5h.01"/>';
  return svg;
}

function resultNotice(text, extraClass = "") {
  const box = el("div", `result-notice ${extraClass}`);
  box.append(infoIcon(), el("p", "", text));
  return box;
}

function renderResultExtra() {
  const area = $("result-extra");
  if (!area) return;
  area.replaceChildren();

  const back = $("result-back-button");
  const goPlan = $("go-to-plan");

  if (analysisMode === "sample") {
    area.append(resultNotice("예시 데이터로 만든 화면이에요. 실제 분석 결과가 아니에요."));
    if (back) { back.dataset.goPage = "0"; back.textContent = "← 홈으로"; }
    if (goPlan) goPlan.hidden = true;
    return;
  }

  if (analysisMode === "saved") {
    const when = viewingRecord ? formatDate(viewingRecord.createdAt) : "";
    area.append(resultNotice(`${when}에 저장한 기록이에요.`));
    if (back) { back.dataset.goPage = "4"; back.textContent = "← 내 기록으로"; }
    if (goPlan) goPlan.hidden = true;
    return;
  }

  // 방금 분석한 결과
  if (back) { back.dataset.goPage = "1"; back.textContent = "← 이전 단계로 돌아가기"; }
  if (goPlan) goPlan.hidden = false;
  if (!currentLive) return;

  if (!auth.loggedIn) {
    const banner = el("div", "save-banner");
    const text = el("div", "save-banner-text");
    text.append(
      el("p", "save-banner-title", "이 결과를 저장해 두고 싶나요?"),
      el("p", "save-banner-desc", "로그인하면 나중에도 내 기록에서 다시 볼 수 있어요.")
    );
    const button = el("button", "btn btn-primary", "로그인하고 저장하기");
    button.type = "button";
    button.addEventListener("click", openLogin);
    banner.append(text, button);
    area.append(banner);
    return;
  }

  if (currentLive.saving) {
    area.append(resultNotice("결과를 저장하는 중이에요..."));
    return;
  }

  if (currentLive.error) {
    const box = resultNotice(`저장하지 못했어요: ${currentLive.error}`, "is-error");
    const retry = el("button", "btn btn-secondary", "다시 저장하기");
    retry.type = "button";
    retry.addEventListener("click", saveLiveResult);
    box.append(retry);
    area.append(box);
    return;
  }

  if (currentLive.savedId) {
    const box = el("div", "saved-status");
    const text = el("div", "");
    text.append(
      el("p", "saved-status-title", "✓ 저장됨"),
      el("p", "saved-status-desc",
        "분석 결과(역량과 근거, 추천 학과, 강점·보완점)와 학년·과목명이 이 아이디에 저장됐어요. 입력한 세특 원문 전체는 저장하지 않아요.")
    );
    const link = el("button", "btn btn-secondary-dark", "내 기록 보기");
    link.type = "button";
    link.addEventListener("click", () => showPage(4));
    box.append(text, link);
    area.append(box);
  }
}

/* ---------- 예시 결과 ---------- */

function showSampleResult() {
  analysisMode = "sample";
  viewingRecord = null;
  renderDashboard(SAMPLE_ANALYSIS);
  renderResultExtra();
  showPage(2);
}

/* ---------- 내 기록 ---------- */

async function loadRecords() {
  const list = $("records-list");
  const status = $("records-status");
  const empty = $("records-empty");
  const deleteAll = $("delete-all-records");

  list.replaceChildren();
  empty.hidden = true;
  deleteAll.hidden = true;

  if (!auth.loggedIn) {
    status.textContent = "";
    showPage(0);
    openLogin();
    return;
  }

  status.textContent = "기록을 불러오는 중...";

  try {
    const data = await accountRequest("GET", "/api/records");
    status.textContent = "";

    if (data.records.length === 0) {
      empty.hidden = false;
      return;
    }

    deleteAll.hidden = false;
    data.records.forEach((record) => list.append(recordCard(record)));
  } catch (error) {
    if (error.status === 401) {
      setAuth(false, null);
      showPage(0);
      openLogin();
      return;
    }
    status.textContent = error.message;
  }
}

function recordCard(record) {
  const card = el("article", "record-card");
  const info = el("div", "record-info");

  const meta = [formatDate(record.createdAt), `${record.grade}학년`, subjectsLabel(record.subjects)]
    .filter(Boolean)
    .join(" · ");
  info.append(el("p", "record-meta", meta));

  const title = el("div", "record-title");
  title.append(
    el("h2", "", record.topMajor),
    el("span", "fit-pill", record.topFitLevel)
  );
  info.append(title);

  if (record.keywords.length > 0) {
    const chips = el("div", "record-chips");
    record.keywords.forEach((word) => chips.append(el("span", "chip", word)));
    info.append(chips);
  }

  const actions = el("div", "record-actions");
  const view = el("button", "btn btn-primary btn-small", "결과 보기");
  view.type = "button";
  view.addEventListener("click", () => openRecord(record, view));

  const remove = el("button", "btn btn-secondary btn-small", "삭제");
  remove.type = "button";
  remove.setAttribute("aria-label", `${meta} ${record.topMajor} 기록 삭제`);
  remove.addEventListener("click", () => deleteRecord(record, remove));

  actions.append(view, remove);
  card.append(info, actions);
  return card;
}

async function openRecord(record, button) {
  setLoading(button, true, "불러오는 중...");
  try {
    const data = await accountRequest("GET", `/api/records/${record.id}`);
    analysisMode = "saved";
    viewingRecord = record;
    renderDashboard(data.result);
    renderResultExtra();
    showPage(2);
  } catch (error) {
    alert(error.message);
  } finally {
    setLoading(button, false);
  }
}

async function deleteRecord(record, button) {
  if (!confirm("이 기록을 삭제할까요? 삭제하면 복구할 수 없어요.")) return;

  setLoading(button, true, "삭제 중...");
  try {
    await accountRequest("DELETE", `/api/records/${record.id}`);
    if (currentLive && currentLive.savedId === record.id) currentLive.savedId = null;
    showToast("기록을 삭제했어요.");
    loadRecords();
  } catch (error) {
    alert(error.message);
    setLoading(button, false);
  }
}

async function deleteAllRecords() {
  if (!confirm("모든 기록을 삭제할까요? 삭제하면 복구할 수 없어요.")) return;

  const button = $("delete-all-records");
  setLoading(button, true, "삭제 중...");
  try {
    await accountRequest("DELETE", "/api/records");
    if (currentLive) currentLive.savedId = null;
    showToast("모든 기록을 삭제했어요.");
    loadRecords();
  } catch (error) {
    alert(error.message);
  } finally {
    setLoading(button, false);
  }
}

/* ---------- 연결 ---------- */

function initAccounts() {
  document.querySelectorAll("[data-open-login]").forEach((button) =>
    button.addEventListener("click", openLogin)
  );

  $("login-form").addEventListener("submit", submitLogin);
  $("login-skip").addEventListener("click", () => {
    closeDialog("login-dialog", false);
    modalOpener = null;
    showPage(1);
  });

  $("guest-start-button").addEventListener("click", () => openDialog("guest-dialog"));
  $("guest-continue").addEventListener("click", () => {
    closeDialog("guest-dialog", false);
    modalOpener = null;
    showPage(1);
  });
  $("guest-login").addEventListener("click", () => {
    closeDialog("guest-dialog", false);
    openLogin();
  });

  // 닫기(×), Esc, 바깥 클릭
  document.querySelectorAll("dialog.modal").forEach((dialog) => {
    dialog.querySelectorAll("[data-close-dialog]").forEach((button) =>
      button.addEventListener("click", () => closeDialog(dialog.id))
    );
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeDialog(dialog.id);
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog(dialog.id);
    });
  });

  $("logout-button").addEventListener("click", logout);
  $("sample-result-button").addEventListener("click", showSampleResult);
  $("delete-all-records").addEventListener("click", deleteAllRecords);

  // 처음 열 때 로그인 상태 확인 (실패하면 비회원으로 계속)
  accountRequest("GET", "/api/auth/me")
    .then((data) => setAuth(Boolean(data && data.loggedIn), data && data.username))
    .catch(() => setAuth(false, null));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAccounts);
} else {
  initAccounts();
}
