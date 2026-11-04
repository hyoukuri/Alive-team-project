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

function saveRecord() { studentRecords[activeGrade] = textarea.value; }

function updateCount() {
  saveRecord();
  const current = Number(gradeSelect.value);
  const total = Array.from({ length: current }, (_, i) => studentRecords[i + 1].length)
    .reduce((a, b) => a + b, 0);
  $("character-count").textContent =
    `${activeGrade}학년: ${studentRecords[activeGrade].length.toLocaleString()}자 / 전체: ${total.toLocaleString()}자`;
}

function switchGrade(grade) {
  if (grade < 1 || grade > Number(gradeSelect.value)) return;
  saveRecord();
  activeGrade = grade;
  textarea.value = studentRecords[grade];
  gradeTabs.forEach((tab) => tab.classList.toggle("active", Number(tab.dataset.grade) === grade));
  updateCount();
}

function updateVisibleGrades() {
  const current = Number(gradeSelect.value);
  gradeTabs.forEach((tab) => { tab.hidden = Number(tab.dataset.grade) > current; });
  if (activeGrade > current) switchGrade(current);
  updateCount();
}

function showPage(page) {
  $("input-page").hidden = page !== 1;
  $("analysis-page").hidden = page !== 2;
  $("plan-page").hidden = page !== 3;
  steps.forEach((step, i) => step.classList.toggle("active", i === page - 1));
  window.scrollTo(0, 0);
}

function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = String(content);
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
  canvas.setAttribute("aria-label", "5대 역량 레이더 차트. 아래 역량별 점수와 근거를 함께 확인하세요.");
  wrap.append(canvas);
  const ctx = canvas.getContext("2d");
  const cx = 310, cy = 177, radius = 112;
  const angle = (i) => -Math.PI / 2 + (i * Math.PI * 2) / 5;
  const point = (i, r) => [cx + Math.cos(angle(i)) * r, cy + Math.sin(angle(i)) * r];

  function polygon(scale, fill, stroke, width = 1) {
    ctx.beginPath();
    items.forEach((item, i) => {
      const [x, y] = point(i, radius * scale * (fill === "rgba(68,215,187,0.25)" ? Number(item.score) / 100 : 1));
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.stroke();
  }
  [0.25, 0.5, 0.75, 1].forEach((r) => polygon(r, null, "#DDE6EE"));
  items.forEach((_, i) => {
    const [x, y] = point(i, radius);
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y);
    ctx.strokeStyle = "#E2E8F0"; ctx.stroke();
  });
  polygon(1, "rgba(68,215,187,0.25)", "#159E9C", 3);
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
  title.append(el("p", "eyebrow", "SEEDU:ON · AI ANALYSIS"));
  title.append(el("h2", "result-title", "나의 역량 분석 리포트"));
  title.append(el("p", "muted", "입력한 세특을 바탕으로 생성한 참고용 분석입니다."));
  analysisResults.append(title);

  const competencies = card("5대 핵심 역량");
  competencies.append(radarChart(data.competencies));
  const scores = el("div", "score-grid");
  data.competencies.forEach((item) => {
    const box = el("div", "score-item");
    const heading = el("div", "score-heading");
    heading.append(el("strong", "", item.name));
    heading.append(el("span", "score-number", `${Math.round(item.score)} / 100`));
    box.append(heading);
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    fill.style.width = `${Math.max(0, Math.min(100, item.score))}%`;
    track.append(fill);
    box.append(track, el("p", "evidence", item.evidence));
    scores.append(box);
  });
  competencies.append(scores);
  analysisResults.append(competencies);

  const majors = card("추천 학과 TOP 3");
  data.majors.forEach((item, i) => {
    const box = el("div", "major-item");
    const top = el("div", "major-top");
    top.append(el("strong", "", `${i + 1}. ${item.name}`));
    top.append(el("span", "fit-number", `${Math.round(item.fit)}%`));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill major-fill");
    fill.style.width = `${Math.max(0, Math.min(100, item.fit))}%`;
    track.append(fill);
    box.append(top, track, el("p", "evidence", item.reason));
    majors.append(box);
  });
  majors.append(el("p", "disclaimer", "※ 적합도는 AI가 추정한 참고 지표이며, 대학 합격 확률이 아닙니다."));
  analysisResults.append(majors);

  const growth = card("학년별 성장 과정");
  const timeline = el("div", "growth-timeline");
  [...data.growth].sort((a, b) => Number(a.grade) - Number(b.grade)).forEach((item) => {
    const row = el("div", "growth-item");
    row.append(el("span", "growth-year", `${item.grade}학년`));
    row.append(el("p", "", item.summary));
    timeline.append(row);
  });
  growth.append(timeline);
  analysisResults.append(growth);

  const feedback = card("강점과 보완할 역량");
  const columns = el("div", "feedback-grid");
  [["강점", data.strengths, "strength-box"], ["보완점", data.improvements, "improve-box"]].forEach(([title, values, className]) => {
    const box = el("div", `feedback-box ${className}`);
    box.append(el("h3", "", title));
    const list = el("ul", "");
    values.forEach((value) => list.append(el("li", "", value)));
    box.append(list);
    columns.append(box);
  });
  feedback.append(columns);
  analysisResults.append(feedback);
}

textarea.addEventListener("input", updateCount);
gradeTabs.forEach((tab) => tab.addEventListener("click", () => switchGrade(Number(tab.dataset.grade))));
gradeSelect.addEventListener("change", updateVisibleGrades);

analyzeButton.addEventListener("click", async () => {
  saveRecord();
  const currentGrade = Number(gradeSelect.value);
  const records = {};
  for (let grade = 1; grade <= currentGrade; grade++) records[grade] = studentRecords[grade];
  if (!Object.values(records).some((text) => text.trim())) {
    alert("최소 한 학년의 세특을 입력해 주세요.");
    return;
  }
  analyzeButton.disabled = true;
  analyzeButton.textContent = "AI 분석 중입니다...";
  try {
    const response = await fetch("http://127.0.0.1:8000/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_grade: currentGrade,
        records,
        completed_subjects: $("completed-subjects").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "AI 분석 요청 실패");
    if (!data.analysis || !Array.isArray(data.analysis.competencies)) throw new Error("분석 결과 형식이 올바르지 않습니다.");
    latestAnalysis = data.analysis;
    renderDashboard(latestAnalysis);
    showPage(2);
  } catch (error) {
    console.error(error);
    alert(`AI 분석 오류: ${error.message}\nFastAPI 서버 터미널도 확인해 주세요.`);
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "AI 분석 시작하기";
  }
});

function renderPlanSelector() {
  planResults.replaceChildren();
  const intro = el("div", "result-intro");
  intro.append(el("p", "eyebrow", "SEEDU:ON · CAREER ROADMAP"));
  intro.append(el("h2", "result-title", "나만의 진로 로드맵"));
  intro.append(el("p", "muted", "추천 학과를 선택하거나 다른 희망 학과를 직접 입력하세요."));
  planResults.append(intro);

  const selectorCard = card("희망 학과 선택");
  const select = el("select", "major-select");
  select.id = "major-select";
  latestAnalysis.majors.forEach((major) => {
    const option = document.createElement("option");
    option.value = major.name;
    option.textContent = major.name;
    select.append(option);
  });
  const customOption = document.createElement("option");
  customOption.value = "__custom__";
  customOption.textContent = "다른 학과 직접 입력";
  select.append(customOption);
  const customInput = el("input", "custom-major");
  customInput.placeholder = "예: 해양공학과";
  customInput.maxLength = 80;
  customInput.hidden = true;
  select.addEventListener("change", () => {
    customInput.hidden = select.value !== "__custom__";
  });
  const generate = el("button", "plan-generate", "AI 맞춤 로드맵 생성하기");
  const output = el("div", "plan-output");
  selectorCard.append(select, customInput, generate);
  planResults.append(selectorCard, output);

  generate.addEventListener("click", async () => {
    const major = select.value === "__custom__" ? customInput.value.trim() : select.value;
    if (major.length < 2) { alert("희망 학과를 두 글자 이상 입력해 주세요."); return; }
    saveRecord();
    const currentGrade = Number(gradeSelect.value);
    const records = {};
    for (let grade = 1; grade <= currentGrade; grade++) records[grade] = studentRecords[grade];
    generate.disabled = true;
    generate.textContent = "AI가 로드맵을 설계하고 있습니다...";
    output.replaceChildren();
    try {
      const response = await fetch("http://127.0.0.1:8000/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_grade: currentGrade,
          records,
          completed_subjects: $("completed-subjects").value,
          selected_major: major,
          analysis: latestAnalysis,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "로드맵 생성 실패");
      if (!data.plan || !Array.isArray(data.plan.activities)) throw new Error("로드맵 데이터 형식 오류");
      renderPlan(data.plan, major, output);
    } catch (error) {
      console.error(error);
      alert(`로드맵 생성 오류: ${error.message}`);
    } finally {
      generate.disabled = false;
      generate.textContent = "AI 맞춤 로드맵 생성하기";
    }
  });
}

function labeledText(label, value) {
  const box = el("div", "plan-field");
  box.append(el("strong", "", label), el("p", "", value));
  return box;
}

function renderPlan(plan, major, output) {
  output.replaceChildren();
  const overview = card(`${major} · 맞춤 진로 방향`);
  overview.append(el("p", "plan-overview", plan.overview));
  output.append(overview);

  const courses = card("추천 선택과목");
  const courseList = el("div", "course-list");
  plan.courses.forEach((course) => {
    const item = el("div", "course-item");
    item.append(el("h3", "", course.name));
    item.append(labeledText("추천 이유", course.reason));
    item.append(labeledText("권장 시기", course.timing));
    courseList.append(item);
  });
  courses.append(courseList);
  courses.append(el("p", "disclaimer", "※ 실제 과목 개설, 이수 시기와 선수과목은 학교 교육과정 편제표에서 반드시 확인하세요."));
  output.append(courses);

  const activities = card("세특 연계 탐구활동 3가지");
  plan.activities.forEach((activity, i) => {
    const item = el("article", "activity-item");
    item.append(el("p", "eyebrow", `추천 탐구 ${i + 1}`));
    item.append(el("h3", "", activity.title));
    item.append(labeledText("기존 세특과 연결", activity.connection));
    item.append(labeledText("핵심 탐구 질문", activity.question));
    item.append(labeledText("진행 방법", activity.process));
    item.append(labeledText("예상 결과물", activity.deliverable));
    item.append(labeledText("심화·확장", activity.extension));
    activities.append(item);
  });
  output.append(activities);

  const next = card("앞으로의 실행 계획");
  next.append(el("p", "plan-overview", plan.next_steps));
  output.append(next);
}

$("go-to-plan").addEventListener("click", () => {
  if (!latestAnalysis) { alert("먼저 AI 역량 분석을 진행해 주세요."); return; }
  renderPlanSelector();
  showPage(3);
});

updateVisibleGrades();
updateCount();
showPage(1);
