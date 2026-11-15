
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

// 화면에서 원문을 중간에 자르지 않고, 핵심 수행 행위를 완결된 문장으로 요약합니다.
// 원문은 세부 보기에서 별도로 확인할 수 있습니다.
function evidenceSummary(value) {
  const raw = String(value ?? '').replace(/\s+/g, ' ').trim();
  if (!raw) return '이 항목에서 확인된 활동 근거가 없습니다.';
  // The source can already be truncated by the backend or an old saved analysis.
  // Never display a dangling fragment as though it were a complete summary.
  const source = raw.replace(/[“”]/g, '"').replace(/[‘’]/g, "'");
  const label = source.match(/(?:^|\s)(?:\d학년\s+)?(?:과목:\s*)?((?:공통|통합|과학탐구|한국사|정보|체육|음악|미술|기술|가정|진로|자율)[가-힣A-Za-z0-9· ]{0,16})\s*[:：—]/);
  const prefix = label ? label[1].trim() + ': ' : '';
  const body = label ? source.slice(label.index + label[0].length) : source;
  const clean = body.replace(/^(?:확인된 활동|추천 근거)\s*[:：]\s*/, '').trim();
  const sentences = clean.split(/(?<=[.!?。])\s+/).map(s => s.trim());
  const action = /(조사|비교|분석|실험|측정|제작|발표|작성|탐구|검증|토론|해석|설계|정리|제안|수집|평가|활용|관찰|설명)/;
  const complete = sentences.find(s => s.length >= 18 && s.length <= 190 && /[.!?。]$/.test(s) && !/[.…]{2,}/.test(s) && action.test(s));
  if (complete) return prefix + complete;
  const title = clean.match(/["']([^"']{4,65})["']/)?.[1];
  const topics = [
    [/산성화|산성비|중화/, '산성비와 중화 방법'],
    [/지진|진원지|원의 방정식/, '원의 방정식을 이용한 지진 진원지 탐색'],
    [/중화열|혼합용액|중화점/, '중화 반응의 측정 결과'],
    [/탱자나무|로트레크|닉부이/, '문학 작품의 표현 방식과 작가의 의도'],
    [/영어 글쓰기|기억에 남는 경험/, '경험을 소재로 한 영어 글쓰기'],
  ];
  const topic = topics.find(([pattern]) => pattern.test(clean))?.[1] || title || '해당 교과 주제';
  const verbs = [...clean.matchAll(new RegExp(action.source, 'g'))].map(m=>m[0]);
  const verb = verbs.length ? verbs[verbs.length-1] : null;
  if (verb) return `${prefix}${topic}에 관한 ${verb} 활동이 기록되어 있습니다.`;
  return `${prefix}${topic}에 관한 학습 내용이 기록되어 있으나, 구체적인 수행 근거는 원문 확인이 필요합니다.`;
}
function conciseText(value) { return evidenceSummary(value); }
function compactEvidence(value) { return evidenceSummary(value); }
function seeduFeedbackSummary(value) { return evidenceSummary(value); }
function appendEvidencePreview(parent, raw, heading = "원문 근거 보기") {
  const source = String(raw || "").trim();
  if (!source) return;
  const details = el("details", "seedu-original-evidence");
  details.append(el("summary", "", heading), el("p", "", source));
  parent.append(details);
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
    heading.append(el("span", rated ? "seedu-skill-value" : "seedu-skill-ne", rated ? `${Math.round(item.score)}점` : "근거 부족"));
    box.append(heading);
    if (rated) {
      const track = el("div", "seedu-track");
      const fill = el("div", "seedu-fill");
      fill.style.width = `${Math.max(0, Math.min(100, item.score))}%`;
      track.append(fill);
      box.append(track);
    }
    if (item.evidence) {
      const detail = el("details", "seedu-skill-detail");
      detail.append(el("summary", "", "평가 근거 보기"));
      detail.append(el("p", "", evidenceSummary(item.evidence)));
      appendEvidencePreview(detail, item.evidence);
      box.append(detail);
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

  // Show only two key observations. No forced one-line clipping or horizontal overflow.
  const feedbackWrap = el("div", "seedu-feedback-grid span-full");
  [
    ["나의 강점", data.strengths, "strength-card", "확인된 강점이 없습니다."],
    ["보완할 점", data.improvements, "improve-card", "추가 탐색이 필요한 부분을 확인해 보세요."]
  ].forEach(([heading, values, className, emptyText]) => {
    const box = card(heading, `feedback-card ${className} seedu-brief-feedback`);
    const list = el("ul", "seedu-feedback-list");
    const items = values.filter(x => String(x || "").trim()).slice(0, 2);
    (items.length ? items : [emptyText]).forEach(value => {
      const li = el("li", "", seeduFeedbackSummary(value));
      if (String(value).length > 155) appendEvidencePreview(li, value);
      list.append(li);
    });
    box.append(list);
    feedbackWrap.append(box);
  });
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
    box.append(el("p", "major-rank", complete ? "종합 평가 완료" : "전공 탐색 후보 · 종합 평가 보류"));
    box.append(el("h3", "major-name", item.name));
    box.append(el("p", "evidence seedu-major-reason", evidenceSummary(item.reason) || "전공 관련 활동의 근거를 추가 확인해야 합니다."));
    appendEvidencePreview(box, item.reason, "추천 근거 원문 보기");

    const details = el("details", "major-fit-details seedu-major-details");
    details.open = true;
    details.append(el("summary", "", "5개 평가 지표 · 근거 확인"));
    if (complete) {
      details.append(el("p", "seedu-evaluation-note", `종합 루브릭 점수 ${item.fit.toFixed(1)} / 100 · 합격 확률이 아닙니다.`));
    } else {
      const part = Number.isFinite(item.partialScore) ? item.partialScore.toFixed(1) : "—";
      details.append(el("p", "seedu-evaluation-note", `종합 평가 보류 · 평가 가능한 배점 ${coverage}/100 · 확인된 부분 점수 ${part}/${coverage || '—'}`));
      details.append(el("p", "muted", "부분 점수는 전공 적합도나 학과 순위가 아닙니다. N/E는 0점이 아닙니다."));
    }
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
      heading.append(el("span", "score-number", rated ? `${value.toFixed(1)}점 · 근거 ${covered}/${maximum}` : "추가 근거 필요"));
      row.append(heading);
      if (rated) {
        const track = el("div", "bar-track");
        const fill = el("div", "bar-fill");
        fill.style.width = `${Math.max(0, Math.min(100, value / maximum * 100))}%`;
        track.append(fill);
        row.append(track);
      }
      if (!rated) row.append(el("p", "seedu-ne-guidance", `다음 탐색: ${nextAction[category]}`));
      details.append(row);
    });
    if (item.improvement) {
      details.append(el("p", "evidence seedu-brief-evidence", `보완 방향: ${evidenceSummary(item.improvement)}`));
      appendEvidencePreview(details, item.improvement, "보완 안내 원문 보기");
    }
    box.append(details);
    majorList.append(box);
  });

  majors.append(majorList);

  majors.append(
    el(
      "p",
      "disclaimer",
      "※ 근거가 부족한 학과는 종합 평가를 보류합니다. 부분 점수는 적합도 순위나 합격 확률이 아니며, N/E는 0점이 아닙니다."
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
      const summary = String(item.summary || '');
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
    ? { title: item, description: "", steps: [], expectedResult: "" }
    : { title: asText(item.title ?? item.name ?? item.activity, `탐구활동 ${i+1}`),
        description: asText(item.description ?? item.detail ?? item.reason, ""),
        steps: roadmapList(item.steps ?? item.process ?? item.actions ?? []).map(x => asText(x.name ?? x.action ?? x.step ?? x)),
        expectedResult: asText(item.expected_result ?? item.expectedResult ?? item.output, "") }
  );
  const gradePlan = roadmapList(gradeRaw).map((item, i) => {
    if (typeof item === "string") return {grade:i+1, goal:item, actions:[]};
    return { grade:Number(item.grade) || Number(String(item.name ?? "").replace(/\D/g,"")) || i+1,
      goal:asText(item.goal ?? item.title ?? item.summary ?? item.name,""),
      actions:roadmapList(item.actions ?? item.tasks ?? item.steps ?? []).map(x => asText(x.name ?? x.action ?? x.task ?? x)) };
  });
  const advice = asText(data.advice ?? data.summary ?? data.final_advice ?? data.guidance, "");
  if (!subjects.length && !activities.length && !gradePlan.length && !advice) {
    throw new Error("서버에서 로드맵 내용이 전달되지 않았습니다. 백엔드 /roadmap 응답 형식을 확인해 주세요.");
  }
  return {major:asText(data.major ?? data.target_major,""),subjects,activities,gradePlan,advice};
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

/* 로드맵 화면 출력 */

function renderRoadmap(data) {
  planResults.replaceChildren();

  const intro = el("div", "result-intro");
  intro.append(
    el("p", "eyebrow", "SEEDU:ON · PERSONAL ROADMAP"),
    el("h2", "result-title", `${data.major || selectedMajor} 진로 로드맵`),
    el("p", "muted", "나의 세특과 희망 학과를 바탕으로 만든 맞춤 진로 계획입니다.")
  );

  planResults.append(intro);

  // 1. 추천 선택과목
  const subjectCard = card("추천 선택과목");

  if (data.subjects.length === 0) {
    subjectCard.append(
      el("p", "muted", "추천 과목 정보가 없습니다.")
    );
  }

  const subjectList = el("div", "subject-list");

  data.subjects.forEach((item) => {
    const box = el("div", "subject-item");
    box.append(
      el("h3", "", item.name),
      el("p", "evidence", item.reason)
    );
    subjectList.append(box);
  });

  if (data.subjects.length > 0) subjectCard.append(subjectList);

  planResults.append(subjectCard);

  // 2. 탐구활동 3개
  const activityCard = card("추천 심화 탐구활동 TOP 3");
  const activityList = el("div", "activity-list");

  data.activities.slice(0, 3).forEach((item, i) => {
    const box = el("div", "activity-item");

    box.append(
      el("span", "activity-number", `PROJECT 0${i + 1}`),
      el("h3", "", item.title),
      el("p", "evidence", item.description)
    );

    if (item.steps.length > 0) {
      const list = el("ol", "activity-steps");

      item.steps.forEach((step) => {
        list.append(el("li", "", step));
      });

      box.append(list);
    }

    if (item.expectedResult) {
      box.append(
        el("p", "expected-result", `예상 산출물: ${item.expectedResult}`)
      );
    }

    activityList.append(box);
  });

  if (data.activities.length > 0) activityCard.append(activityList);

  if (data.activities.length === 0) {
    activityCard.append(
      el("p", "muted", "추천 탐구활동 정보가 없습니다.")
    );
  }

  planResults.append(activityCard);

  // 3. 학년별 성장 로드맵
  const gradeCard = card("학년별 성장 로드맵");

  if (!data.gradePlan.length) gradeCard.append(el("p", "muted", "학년별 계획 정보는 응답에 포함되지 않았습니다."));
  data.gradePlan.forEach((item) => {
    const box = el("div", "grade-plan-item");

    box.append(
      el("h3", "", `${item.grade}학년 · ${item.goal}`)
    );

    const list = el("ul", "grade-actions");

    item.actions.forEach((action) => {
      list.append(el("li", "", action));
    });

    box.append(list);
    gradeCard.append(box);
  });

  planResults.append(gradeCard);

  // 4. 종합 조언
  if (data.advice) {
    const adviceCard = card("AI 진로 코칭");
    adviceCard.append(
      el("p", "advice-text", data.advice)
    );
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
