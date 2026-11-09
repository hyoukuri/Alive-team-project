
/* SEEDU:ON - 학년별 세특 입력과 AI 대시보드 */
const studentRecords = { 1: "", 2: "", 3: "" };
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
  if (grade < 1 || grade > Number(gradeSelect.value)) return;

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
  $("input-page").hidden = page !== 1;
  $("analysis-page").hidden = page !== 2;
  $("plan-page").hidden = page !== 3;

  steps.forEach((step, i) =>
    step.classList.toggle("active", i === page - 1)
  );

  window.scrollTo(0, 0);
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

function radarChart(items) {
  const wrap = el("div", "radar-wrap");
  const canvas = document.createElement("canvas");

  canvas.width = 620;
  canvas.height = 360;
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    "5대 역량 레이더 차트. 아래 역량별 점수와 근거를 함께 확인하세요."
  );

  wrap.append(canvas);

  const ctx = canvas.getContext("2d");
  const cx = 310;
  const cy = 177;
  const radius = 112;

  const angle = (i) =>
    -Math.PI / 2 + (i * Math.PI * 2) / 5;

  const point = (i, r) => [
    cx + Math.cos(angle(i)) * r,
    cy + Math.sin(angle(i)) * r
  ];

  function polygon(scale, fill, stroke, width = 1) {
    ctx.beginPath();

    items.forEach((item, i) => {
      const scoreScale =
        fill === "rgba(68,215,187,0.25)"
          ? Number(item.score) / 100
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

  [0.25, 0.5, 0.75, 1].forEach((r) =>
    polygon(r, null, "#DDE6EE")
  );

  items.forEach((_, i) => {
    const [x, y] = point(i, radius);

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(x, y);
    ctx.strokeStyle = "#E2E8F0";
    ctx.stroke();
  });

  polygon(
    1,
    "rgba(68,215,187,0.25)",
    "#159E9C",
    3
  );

  ctx.font = "15px Malgun Gothic, sans-serif";
  ctx.fillStyle = "#233D53";
  ctx.textAlign = "center";

  items.forEach((item, i) => {
    const [x, y] = point(i, radius + 49);
    ctx.fillText(item.name, x, y + 5);
  });

  return wrap;
}

function renderDashboard(data) {
  analysisResults.replaceChildren();

  const title = el("div", "result-intro");
  title.append(
    el("p", "eyebrow", "SEEDU:ON · AI ANALYSIS")
  );
  title.append(
    el("h2", "result-title", "나의 역량 분석 리포트")
  );
  title.append(
    el(
      "p",
      "muted",
      "입력한 세특을 바탕으로 생성한 참고용 분석입니다."
    )
  );

  analysisResults.append(title);

  const competencies = card("5대 핵심 역량");
  competencies.append(radarChart(data.competencies));

  const scores = el("div", "score-grid");

  data.competencies.forEach((item) => {
    const box = el("div", "score-item");
    const heading = el("div", "score-heading");

    heading.append(el("strong", "", item.name));
    heading.append(
      el("span", "score-number", `${Math.round(item.score)} / 100`)
    );

    box.append(heading);

    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");

    fill.style.width =
      `${Math.max(0, Math.min(100, item.score))}%`;

    track.append(fill);

    box.append(
      track,
      el("p", "evidence", item.evidence)
    );

    scores.append(box);
  });

  competencies.append(scores);
  analysisResults.append(competencies);

  
  const majors = card("추천 학과 TOP 3");

  const categoryMax = {
    "전공 관련 활동": 30,
    "학업 역량": 25,
    "관심의 지속성": 20,
    "탐구 심화도": 15,
    "융합 역량": 10
  };

  data.majors.forEach((item, i) => {
    const box = el("div", "major-item");
    const top = el("div", "major-top");

    top.append(
      el("strong", "", `${i + 1}. ${item.name}`)
    );

    const hasScore = item.fit !== null;

    top.append(
      el(
        "span",
        "fit-number",
        hasScore
          ? `${item.fit.toFixed(1)} / 100`
          : "평가 점수 없음"
      )
    );

    box.append(top);

    if (hasScore) {
      const track = el("div", "bar-track");
      const fill = el("div", "bar-fill major-fill");

      fill.style.width = `${item.fit}%`;
      track.append(fill);
      box.append(track);
    }

    box.append(
      el("p", "evidence", item.reason)
    );

    if (hasScore) {
      const details = el("div", "major-fit-details");

      details.style.marginTop = "16px";

      Object.entries(categoryMax).forEach(
        ([category, maximum]) => {
          const value = Number(
            item.categoryScores[category]
          );

          if (!Number.isFinite(value)) return;

          const row = el("div", "score-item");
          const heading = el("div", "score-heading");

          heading.append(
            el("strong", "", category),
            el(
              "span",
              "score-number",
              `${value.toFixed(1)} / ${maximum}`
            )
          );

          const track = el("div", "bar-track");
          const fill = el("div", "bar-fill");

          fill.style.width =
            `${Math.max(0, Math.min(100, value / maximum * 100))}%`;

          track.append(fill);
          row.append(heading, track);
          details.append(row);
        }
      );

      if (item.evidence) {
        details.append(
          el("p", "evidence", `평가 근거: ${item.evidence}`)
        );
      }

      if (item.improvement) {
        details.append(
          el("p", "evidence", `보완 방향: ${item.improvement}`)
        );
      }

      box.append(details);
    }

    majors.append(box);
  });

  majors.append(
    el(
      "p",
      "disclaimer",
      "※ 전공 적합성은 학생부 기록에 근거한 자체 평가 지표이며, 대학 합격 확률이나 공식 입학 평가 점수가 아닙니다."
    )
  );

  analysisResults.append(majors);



  const growth = card("학년별 성장 과정");
  const timeline = el("div", "growth-timeline");

  [...data.growth]
    .sort((a, b) => Number(a.grade) - Number(b.grade))
    .forEach((item) => {
      const row = el("div", "growth-item");

      row.append(
        el("span", "growth-year", `${item.grade}학년`)
      );
      row.append(el("p", "", item.summary));

      timeline.append(row);
    });

  growth.append(timeline);
  analysisResults.append(growth);

  const feedback = card("강점과 보완할 역량");
  const columns = el("div", "feedback-grid");

  [
    ["강점", data.strengths, "strength-box"],
    ["보완점", data.improvements, "improve-box"]
  ].forEach(([title, values, className]) => {
    const box = el(
      "div",
      `feedback-box ${className}`
    );

    box.append(el("h3", "", title));

    const list = el("ul", "");

    values.forEach((value) =>
      list.append(el("li", "", value))
    );

    box.append(list);
    columns.append(box);
  });

  feedback.append(columns);
  analysisResults.append(feedback);
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

function toScore(value, fallback = 70) {
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
        score: toScore(item.score ?? item.value),
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
      score: toScore(value?.score ?? value?.value),
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
      categoryScores: evaluation?.category_scores ?? {},
      evidence: asText(evaluation?.evidence, ""),
      improvement: asText(evaluation?.improvement, "")
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

  if (majors.length === 0) {
    throw new Error(
      "추천 학과 정보가 없습니다. AI 분석을 다시 시도해 주세요."
    );
  }

  return {
    competencies,
    majors,
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

function normalizeRoadmap(raw) {
  if (!raw || typeof raw !== "object") {
    throw new Error("로드맵 응답이 비어 있습니다.");
  }

  const data = raw.data ?? raw.result ?? raw;

  const subjects = asArray(
    data.recommended_subjects ??
    data.subjects ??
    data.electives ??
    []
  ).map((item) => {
    if (typeof item === "string") {
      return { name: item, reason: "" };
    }

    return {
      name: asText(
        item.subject ?? item.name ?? item.title,
        "추천 과목"
      ),
      reason: asText(
        item.reason ?? item.description,
        ""
      )
    };
  });

  const activities = asArray(
    data.research_activities ??
    data.activities ??
    data.projects ??
    []
  ).map((item, i) => {
    if (typeof item === "string") {
      return {
        title: item,
        description: "",
        steps: [],
        expectedResult: ""
      };
    }

    return {
      title: asText(
        item.title ?? item.name,
        `탐구활동 ${i + 1}`
      ),
      description: asText(
        item.description ?? item.detail,
        ""
      ),
      steps: asArray(
        item.steps ?? item.process ?? []
      ).map((step) => asText(step)),
      expectedResult: asText(
        item.expected_result ??
        item.expectedResult ??
        item.output,
        ""
      )
    };
  });

  const gradePlan = asArray(
    data.grade_plan ??
    data.gradePlan ??
    data.yearly_plan ??
    []
  ).map((item, i) => ({
    grade: Number(item.grade) || i + 1,
    goal: asText(item.goal ?? item.title, ""),
    actions: asArray(
      item.actions ?? item.tasks ?? []
    ).map((action) => asText(action))
  }));

  return {
    major: asText(data.major ?? data.target_major, ""),
    subjects,
    activities,
    gradePlan,
    advice: asText(
      data.advice ?? data.summary ?? data.final_advice,
      ""
    )
  };
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

  data.subjects.forEach((item) => {
    const box = el("div", "subject-item");
    box.append(
      el("h3", "", item.name),
      el("p", "evidence", item.reason)
    );
    subjectCard.append(box);
  });

  planResults.append(subjectCard);

  // 2. 탐구활동 3개
  const activityCard = card("추천 심화 탐구활동 TOP 3");

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

    activityCard.append(box);
  });

  if (data.activities.length === 0) {
    activityCard.append(
      el("p", "muted", "추천 탐구활동 정보가 없습니다.")
    );
  }

  planResults.append(activityCard);

  // 3. 학년별 성장 로드맵
  const gradeCard = card("학년별 성장 로드맵");

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

  setLoading(analyzeButton, true, "AI 분석 중...");

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
    renderDashboard(data);
    showPage(2);

    // 추천 학과 선택 버튼 생성
    setupMajorSelection(data.majors);

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

async function runRoadmap() {
  const majorInput =
    $("custom-major") ||
    $("major-input");

  const customMajor = majorInput?.value.trim() || "";
  const major = customMajor || selectedMajor;

  if (!major) {
    alert("희망 학과를 선택하거나 직접 입력해 주세요.");
    return;
  }

  const button =
    $("roadmap-button") ||
    $("generate-roadmap");

  setLoading(button, true, "맞춤 로드맵 생성 중...");

  try {
    const records = collectRecords();

    const text = Object.entries(records)
      .map(([grade, content]) =>
        `[${grade}학년]\n${content}`
      )
      .join("\n\n");

    const response = await apiRequest("/roadmap", {
      grade: Number(gradeSelect.value),
      major,
      records,
      text,
      analysis: latestAnalysis
    });

    const data = normalizeRoadmap(response);

    renderRoadmap(data);
    showPage(3);

  } catch (error) {
    console.error("로드맵 생성 오류:", error);
    alert(error.message);
  } finally {
    setLoading(button, false);
  }
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
    showPage(3);
  });
}

  const backButtons =
    document.querySelectorAll("[data-go-page]");

  backButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const page = Number(button.dataset.goPage);
      if ([1, 2, 3].includes(page)) {
        showPage(page);
      }
    });
  });

  updateVisibleGrades();
  updateCount();
  showPage(1);

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

    3: [
      "독서와 작문", "영어독해와 작문",
      "확률과 통계", "미적분Ⅱ",
      "스포츠문화", "스포츠과학",
      "논술", "세계시민",
      "심화일본어", "일본문화",
      "중국문화", "중국문학읽기1",
      "데이터과학", "소프트웨어와 생활",
      "교육의 이해", "인간과 경제활동",
      "문학과 매체", "문학감상과 비평",
      "언어생활탐구", "독서토론과 글쓰기",
      "실용통계", "수학과 문화",
      "심화영어", "미디어영어",
      "한국지리탐구", "국제관계의 이해",
      "법과 사회", "인문학과 윤리",
      "전자기와 양자", "화학반응의 세계",
      "생물의 유전", "행성우주과학",
      "고급물리학", "고급화학",
      "고급생명과학", "고급지구과학",
      "지구시스템과학",
      "여행지리", "사회문제탐구",
      "기후변화와 환경생태",
      "과학의 역사와 문화",
      "윤리문제탐구", "역사로 탐구하는 현대 세계",
      "과학교양", "운동과 건강",
      "음악연주와 창작", "음악감상과 비평",
      "미술창작", "미술감상과 비평",
      "융합과학탐구"
    ]
  };

  // 과목별 세특 보관
  const registeredRecords = {
    1: {},
    2: {},
    3: {}
  };

  let editingSubject = null;

  function initSubjectInput() {
    const subjectSelect =
      document.getElementById("subject-select");

    const subjectRecord =
      document.getElementById("subject-record");

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

    if (
      !subjectSelect ||
      !subjectRecord ||
      !addButton ||
      !registeredBox ||
      !hiddenRecord
    ) {
      console.error("과목 입력 HTML 요소를 찾을 수 없습니다.");
      return;
    }

    // 학년별 선택 과목 표시
    function updateSubjectOptions() {
      const grade = activeGrade;

      subjectSelect.replaceChildren();

      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "과목을 선택하세요";
      subjectSelect.append(placeholder);

      SUBJECT_LIST[grade].forEach((name) => {
        const option = document.createElement("option");

        option.value = name;
        option.textContent = name;

        subjectSelect.append(option);
      });

      subjectSelect.value = "";
      subjectRecord.value = "";
      editingSubject = null;
      addButton.textContent = "+ 과목 등록하기";

      renderRegisteredSubjects();
      syncRecords();
    }

    // 등록 과목을 기존 분석용 텍스트로 변환
    function createGradeText(grade) {
      return Object.entries(registeredRecords[grade])
        .map(([name, content]) => {
          return `[과목: ${name}]\n${content}`;
        })
        .join("\n\n");
    }

    // 기존 백엔드와 호환
    function syncRecords() {
      for (let grade = 1; grade <= 3; grade++) {
        studentRecords[grade] = createGradeText(grade);
      }

      hiddenRecord.value = studentRecords[activeGrade];

      const currentGrade = Number(currentGradeSelect.value);

      const total = [1, 2, 3]
        .filter((grade) => grade <= currentGrade)
        .reduce(
          (sum, grade) => sum + studentRecords[grade].length,
          0
        );

      characterCount.textContent =
        `${activeGrade}학년: ` +
        `${studentRecords[activeGrade].length.toLocaleString()}자` +
        ` / 전체: ${total.toLocaleString()}자`;
    }

    // 등록 과목 목록 표시
    function renderRegisteredSubjects() {
      registeredBox.replaceChildren();

      const records = registeredRecords[activeGrade];
      const entries = Object.entries(records);

      if (entries.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "아직 등록한 과목이 없습니다.";
        registeredBox.append(empty);
        return;
      }

      entries.forEach(([name, content]) => {
        const item = document.createElement("div");
        item.className = "registered-subject-item";

        const info = document.createElement("div");
        info.className = "registered-subject-info";

        const title = document.createElement("strong");
        title.textContent = name;

        const detail = document.createElement("p");
        detail.textContent = `${content.length}자 등록됨`;

        info.append(title, detail);

        const buttons = document.createElement("div");
        buttons.className = "registered-subject-actions";

        // 수정 버튼
        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.textContent = "수정";
        editButton.className = "subject-edit-button";

        editButton.addEventListener("click", () => {
          subjectSelect.value = name;
          subjectRecord.value = content;
          editingSubject = name;

          addButton.textContent = "변경 내용 저장하기";

          subjectRecord.focus();
          subjectRecord.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
        });

        // 삭제 버튼
        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.textContent = "삭제";
        deleteButton.className = "subject-delete-button";

        deleteButton.addEventListener("click", () => {
          if (!confirm(`${name} 과목의 세특을 삭제할까요?`)) {
            return;
          }

          delete registeredRecords[activeGrade][name];

          if (subjectSelect.value === name) {
            subjectSelect.value = "";
            subjectRecord.value = "";
            editingSubject = null;
            addButton.textContent = "+ 과목 등록하기";
          }

          renderRegisteredSubjects();
          syncRecords();
        });

        buttons.append(editButton, deleteButton);
        item.append(info, buttons);

        registeredBox.append(item);
      });
    }

    // 과목 등록 및 수정
    addButton.addEventListener("click", () => {
      const name = subjectSelect.value;
      const content = subjectRecord.value.trim();

      if (!name) {
        alert("과목을 먼저 선택해 주세요.");
        return;
      }

      if (!content) {
        alert("세특 내용을 입력해 주세요.");
        return;
      }

      const records = registeredRecords[activeGrade];

      // 수정 과정에서 과목이 변경된 경우
      if (editingSubject && editingSubject !== name) {
        if (records[name] !== undefined) {
          alert("이미 등록된 과목입니다.");
          return;
        }
        delete records[editingSubject];
      }

      if (
        !editingSubject &&
        records[name] !== undefined &&
        !confirm("이미 등록된 과목입니다. 내용을 덮어쓸까요?")
      ) {
        return;
      }

      records[name] = content;

      editingSubject = null;
      subjectSelect.value = "";
      subjectRecord.value = "";

      addButton.textContent = "+ 과목 등록하기";

      renderRegisteredSubjects();
      syncRecords();
    });

    // 선택한 과목의 세특을 수정할 때
    subjectSelect.addEventListener("change", () => {
      if (editingSubject && subjectSelect.value !== editingSubject) {
        editingSubject = null;
        addButton.textContent = "+ 과목 등록하기";
      }
    });

    // 학년 탭 변경 후 과목 목록 갱신
    document.querySelectorAll(".grade-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        updateSubjectOptions();
      });
    });

    // 현재 학년 변경
    currentGradeSelect.addEventListener("change", () => {
      updateSubjectOptions();
    });

    // 분석 직전 입력 데이터 동기화
    const analyzeButton =
      document.getElementById("analyze-button");

    analyzeButton.addEventListener(
      "click",
      (event) => {
        syncRecords();

        const hasAnyRecords = [1, 2, 3].some(
          (grade) =>
            grade <= Number(currentGradeSelect.value) &&
            Object.keys(registeredRecords[grade]).length > 0
        );

        if (!hasAnyRecords) {
          event.stopImmediatePropagation();
          alert("과목과 세특을 먼저 등록해 주세요.");
          return;
        }

        if (subjectRecord.value.trim()) {
          event.stopImmediatePropagation();
          alert(
            "작성 중인 세특이 있습니다. " +
            "'과목 등록하기'를 먼저 눌러 주세요."
          );
        }
      },
      true
    );

    updateSubjectOptions();

    console.log("SEEDU:ON 과목 선택 기능 초기화 완료");
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
