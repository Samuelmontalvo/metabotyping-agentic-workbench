const STORAGE_KEY = "metaboDietTrainerState";

const statusLabels = {
  accepted: "Accepted",
  review: "Human review",
  rejected: "Rejected",
  direct: "Direct",
  partial: "Partial",
  not: "Not comparable"
};

const state = loadState();
const app = document.querySelector("#app");

function defaultState() {
  return {
    activeLesson: "cohorts",
    activeTab: "practice",
    completedLessons: [],
    selectedCrosswalk: "vo2peak",
    comparisonAnswers: {},
    crosswalkAnswers: {},
    quizAnswers: {},
    postQuizAnswers: {},
    checklist: {},
    notes: ""
  };
}

function loadState() {
  try {
    return { ...defaultState(), ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") };
  } catch (_error) {
    return defaultState();
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function icon(name) {
  const paths = {
    export:
      '<path d="M12 3v11"/><path d="m8 10 4 4 4-4"/><path d="M5 21h14"/><path d="M7 17v4"/><path d="M17 17v4"/>',
    check:
      '<path d="m4 12 5 5L20 6"/>',
    reset:
      '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v7h7"/>',
    flag:
      '<path d="M5 21V4"/><path d="M5 4h12l-2 5 2 5H5"/>',
    table:
      '<path d="M3 5h18v14H3z"/><path d="M3 10h18"/><path d="M9 5v14"/><path d="M15 5v14"/>'
  };
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.check}</svg>`;
}

function render() {
  const activeLesson = TRAINING_DATA.lessons.find((lesson) => lesson.id === state.activeLesson);
  const progress = calculateProgress();

  app.innerHTML = `
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">${icon("table")}</div>
        <div>
          <h1>${TRAINING_DATA.module.title}</h1>
          <p>${TRAINING_DATA.module.subtitle}</p>
        </div>
      </div>
      <div class="progress-block" aria-label="Module progress">
        <div class="progress-label"><span>Module progress</span><span>${progress}%</span></div>
        <div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div>
      </div>
      <div class="top-actions">
        <button class="btn primary" data-action="export">${icon("export")}Export artifact</button>
        <button class="btn" data-action="mark-complete">${icon("check")}Mark section</button>
      </div>
    </header>

    <div class="layout">
      <aside class="sidebar" aria-label="Lesson navigation">
        <h2 class="side-heading">Training path</h2>
        <div class="lesson-list">
          ${TRAINING_DATA.lessons.map((lesson, index) => lessonButton(lesson, index)).join("")}
        </div>
        <div class="module-note">
          <strong>${TRAINING_DATA.module.estimatedTime}</strong><br>
          Deliverable target: ${TRAINING_DATA.module.deliverableDate}<br><br>
          ${TRAINING_DATA.module.sourceNote}
        </div>
      </aside>

      <main class="workspace">
        <section class="workspace-card lesson-hero">
          <div>
            <h2>${activeLesson.label}</h2>
            <p>${activeLesson.focus}</p>
          </div>
          <span class="status direct">${activeLesson.time}</span>
        </section>

        <section class="summary-grid" aria-label="Learner status">
          ${summaryTile("Lessons", `${state.completedLessons.length}/5`, "Marked complete")}
          ${summaryTile("Comparison", `${scoreComparison().correct}/${TRAINING_DATA.comparisonRows.length}`, "Cohort decisions")}
          ${summaryTile("Crosswalk", `${scoreCrosswalk().correct}/${TRAINING_DATA.crosswalkRows.length}`, "Mapping decisions")}
          ${summaryTile("Checks", `${scoreQuiz(state.quizAnswers).correct + scoreQuiz(state.postQuizAnswers).correct}/8`, "Pre and post")}
        </section>

        <nav class="tabbar" aria-label="Workspace tabs">
          ${tabButton("learn", "Learn")}
          ${tabButton("practice", "Practice")}
          ${tabButton("review", "Review")}
          ${tabButton("transfer", "Transfer")}
        </nav>

        ${renderActiveTab()}
      </main>

      ${renderReviewPanel()}
    </div>
    <div class="screen-reader-status" aria-live="polite" id="status"></div>
  `;
}

function lessonButton(lesson, index) {
  const active = lesson.id === state.activeLesson ? " is-active" : "";
  const complete = state.completedLessons.includes(lesson.id) ? " is-complete" : "";
  return `
    <button class="lesson-button${active}${complete}" data-action="set-lesson" data-lesson="${lesson.id}">
      <span class="lesson-index">${complete ? icon("check") : index + 1}</span>
      <span>
        <span class="lesson-title">${lesson.label}</span>
        <span class="lesson-meta">${lesson.time}</span>
      </span>
    </button>
  `;
}

function summaryTile(label, value, caption) {
  return `
    <div class="summary-tile">
      <span class="summary-value">${value}</span>
      <span class="summary-label">${label} - ${caption}</span>
    </div>
  `;
}

function tabButton(id, label) {
  const active = id === state.activeTab ? " is-active" : "";
  return `<button class="tab-button${active}" data-action="set-tab" data-tab="${id}">${label}</button>`;
}

function renderActiveTab() {
  if (state.activeTab === "learn") return renderLearn();
  if (state.activeTab === "review") return renderReview();
  if (state.activeTab === "transfer") return renderTransfer();
  return renderPractice();
}

function renderLearn() {
  const activeLesson = TRAINING_DATA.lessons.find((lesson) => lesson.id === state.activeLesson);
  return `
    <section class="grid-two">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Learning objective</h3>
            <p class="panel-caption">${activeLesson.outcome}</p>
          </div>
          <span class="status direct">${activeLesson.time}</span>
        </div>
        <div class="panel-body">
          <div class="cohort-strip">
            ${TRAINING_DATA.cohorts.map(cohortCard).join("")}
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Pre-test</h3>
            <p class="panel-caption">Baseline check before the hands-on workflow.</p>
          </div>
          <span class="status ${scoreQuiz(state.quizAnswers).correct >= 3 ? "accepted" : "review"}">${scoreQuiz(state.quizAnswers).correct}/4</span>
        </div>
        <div class="panel-body">
          ${renderQuiz("quizAnswers")}
        </div>
      </div>
    </section>
  `;
}

function cohortCard(cohort) {
  return `
    <article class="cohort-card">
      <h4>${cohort.name}</h4>
      <p>${cohort.anchor}</p>
      <div class="tag-row">
        ${cohort.strengths.map((item) => `<span class="tag">${item}</span>`).join("")}
      </div>
    </article>
  `;
}

function renderPractice() {
  return `
    <section class="grid-two">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Cohort comparison matrix</h3>
            <p class="panel-caption">Classify each domain before harmonization.</p>
          </div>
          <span class="status ${scoreComparison().correct >= 4 ? "accepted" : "review"}">${scoreComparison().correct}/${TRAINING_DATA.comparisonRows.length}</span>
        </div>
        <div class="panel-body">
          ${renderComparisonTable()}
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Crosswalk builder</h3>
            <p class="panel-caption">Select the review status for each proposed mapping.</p>
          </div>
          <span class="status ${scoreCrosswalk().correct >= 5 ? "accepted" : "review"}">${scoreCrosswalk().correct}/${TRAINING_DATA.crosswalkRows.length}</span>
        </div>
        <div class="panel-body">
          ${renderCrosswalkTable()}
        </div>
      </div>
    </section>
  `;
}

function renderComparisonTable() {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Domain</th>
            <th>NPH proxy</th>
            <th>MoTrPAC proxy</th>
            <th>Your decision</th>
          </tr>
        </thead>
        <tbody>
          ${TRAINING_DATA.comparisonRows.map((row) => {
            const answer = state.comparisonAnswers[row.id] || "";
            const feedback = answer ? answer === row.expected : null;
            return `
              <tr>
                <td><span class="cell-title">${row.domain}</span><span class="cell-subtitle">${row.evidence}</span></td>
                <td>${row.nph}</td>
                <td>${row.motrpac}</td>
                <td>
                  <select class="select-control" data-action="comparison-answer" data-row="${row.id}" aria-label="Decision for ${row.domain}">
                    ${option("", "Choose", answer)}
                    ${option("direct", "Directly comparable", answer)}
                    ${option("partial", "Partially comparable", answer)}
                    ${option("not", "Not comparable", answer)}
                  </select>
                  <div class="feedback ${feedback === true ? "good" : feedback === false ? "bad" : ""}">
                    ${feedback === null ? "Awaiting decision." : feedback ? "Matches the expected review logic." : "Recheck the evidence before mapping."}
                  </div>
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderCrosswalkTable() {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Source variable</th>
            <th>Candidate common variable</th>
            <th>Context</th>
            <th>Your status</th>
          </tr>
        </thead>
        <tbody>
          ${TRAINING_DATA.crosswalkRows.map((row) => {
            const answer = state.crosswalkAnswers[row.id] || "";
            const feedback = answer ? answer === row.correctStatus : null;
            const selected = row.id === state.selectedCrosswalk ? " is-selected" : "";
            return `
              <tr class="${selected}">
                <td>
                  <button class="row-button" data-action="select-crosswalk" data-row="${row.id}">
                    <span class="cell-title mono">${row.sourceVariable}</span>
                    <span class="cell-subtitle">${row.label} - ${row.study}</span>
                  </button>
                </td>
                <td><span class="mono">${row.candidate}</span></td>
                <td>${row.unit}, ${row.timing}, ${row.modality}</td>
                <td>
                  <select class="select-control" data-action="crosswalk-answer" data-row="${row.id}" aria-label="Review status for ${row.sourceVariable}">
                    ${option("", "Choose", answer)}
                    ${option("accepted", "Accepted", answer)}
                    ${option("review", "Requires human review", answer)}
                    ${option("rejected", "Rejected", answer)}
                  </select>
                  <div class="feedback ${feedback === true ? "good" : feedback === false ? "bad" : ""}">
                    ${feedback === null ? "Select a status." : feedback ? "Decision preserves the review gate." : "This would create a harmonization risk."}
                  </div>
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderReview() {
  return `
    <section class="grid-two">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Guided interpretation</h3>
            <p class="panel-caption">Use these outputs to discuss what can and cannot be inferred.</p>
          </div>
        </div>
        <div class="panel-body">
          <div class="bars">
            ${TRAINING_DATA.interpretationSignals.map((signal) => `
              <div class="bar-row">
                <div class="bar-top"><span>${signal.label}</span><span>${signal.value}%</span></div>
                <div class="bar-track"><div class="bar-fill" style="width:${signal.value}%"></div></div>
                <span class="cell-subtitle">${signal.detail}</span>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Reflection notes</h3>
            <p class="panel-caption">Document unresolved assumptions before export.</p>
          </div>
        </div>
        <div class="panel-body">
          <textarea class="notes-box" data-action="notes" placeholder="Example: VO2peak remains review-required until endpoint criteria are documented.">${escapeHtml(state.notes)}</textarea>
        </div>
      </div>
    </section>
  `;
}

function renderTransfer() {
  return `
    <section class="grid-two">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Transfer checklist</h3>
            <p class="panel-caption">Apply this before using another CFDE-style resource.</p>
          </div>
          <span class="status ${scoreChecklist() === TRAINING_DATA.transferChecklist.length ? "accepted" : "review"}">${scoreChecklist()}/${TRAINING_DATA.transferChecklist.length}</span>
        </div>
        <div class="panel-body">
          <div class="checklist">
            ${TRAINING_DATA.transferChecklist.map((item, index) => `
              <label class="check-item">
                <input type="checkbox" data-action="checklist" data-index="${index}" ${state.checklist[index] ? "checked" : ""}>
                <span>${item}</span>
              </label>
            `).join("")}
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">
          <div>
            <h3 class="panel-title">Post-test</h3>
            <p class="panel-caption">Use the same questions to document learner gains.</p>
          </div>
          <span class="status ${scoreQuiz(state.postQuizAnswers).correct >= 3 ? "accepted" : "review"}">${scoreQuiz(state.postQuizAnswers).correct}/4</span>
        </div>
        <div class="panel-body">
          ${renderQuiz("postQuizAnswers")}
        </div>
      </div>
    </section>
  `;
}

function renderQuiz(stateKey) {
  return `
    <div class="quiz-list">
      ${TRAINING_DATA.quizQuestions.map((question) => {
        const answer = state[stateKey][question.id];
        const hasAnswer = answer !== undefined;
        const correct = hasAnswer && Number(answer) === question.answer;
        return `
          <fieldset class="quiz-item">
            <legend>${question.question}</legend>
            <div class="radio-list">
              ${question.options.map((choice, index) => `
                <label class="radio-option">
                  <input type="radio" name="${stateKey}-${question.id}" data-action="quiz-answer" data-state-key="${stateKey}" data-question="${question.id}" value="${index}" ${Number(answer) === index ? "checked" : ""}>
                  <span>${choice}</span>
                </label>
              `).join("")}
            </div>
            <div class="feedback ${!hasAnswer ? "" : correct ? "good" : "bad"}">
              ${!hasAnswer ? "No response yet." : correct ? "Correct." : "Review the module guardrails."}
            </div>
          </fieldset>
        `;
      }).join("")}
    </div>
  `;
}

function renderReviewPanel() {
  const row = TRAINING_DATA.crosswalkRows.find((item) => item.id === state.selectedCrosswalk);
  if (!row) {
    return `<aside class="review-panel"><div class="empty-state">Select a crosswalk row.</div></aside>`;
  }
  const score = Math.round(row.confidence * 100);
  return `
    <aside class="review-panel" aria-label="Review panel">
      <div class="panel-header">
        <div>
          <h3 class="panel-title">Review gate</h3>
          <p class="panel-caption">Selected mapping evidence and provenance.</p>
        </div>
        <span class="status ${row.correctStatus}">${statusLabels[row.correctStatus]}</span>
      </div>
      <div class="panel-body">
        <div class="review-metric">
          <div>
            <strong>Confidence score</strong>
            <span>Training answer key</span>
          </div>
          <div class="confidence-ring" style="--score:${score}%">${score}</div>
        </div>
        <div class="detail-list">
          ${detail("Source", `<span class="mono">${row.sourceVariable}</span> from ${row.study}`)}
          ${detail("Candidate", `<span class="mono">${row.candidate}</span>`)}
          ${detail("Context", `${row.unit}; ${row.timing}; ${row.modality}`)}
          ${detail("Rationale", row.rationale)}
          ${detail("Provenance", row.provenance)}
        </div>
        <button class="btn danger" data-action="reset">${icon("reset")}Reset session</button>
      </div>
    </aside>
  `;
}

function detail(label, value) {
  return `
    <div class="detail-row">
      <span class="detail-label">${label}</span>
      <span class="detail-value">${value}</span>
    </div>
  `;
}

function option(value, label, current) {
  return `<option value="${value}" ${current === value ? "selected" : ""}>${label}</option>`;
}

function calculateProgress() {
  const lessonPoints = state.completedLessons.length * 12;
  const comparisonPoints = scoreComparison().correct * 4;
  const crosswalkPoints = scoreCrosswalk().correct * 4;
  const quizPoints = (scoreQuiz(state.quizAnswers).correct + scoreQuiz(state.postQuizAnswers).correct) * 3;
  const checklistPoints = scoreChecklist() * 2;
  return Math.min(100, Math.round(lessonPoints + comparisonPoints + crosswalkPoints + quizPoints + checklistPoints));
}

function scoreComparison() {
  let correct = 0;
  TRAINING_DATA.comparisonRows.forEach((row) => {
    if (state.comparisonAnswers[row.id] === row.expected) correct += 1;
  });
  return { correct };
}

function scoreCrosswalk() {
  let correct = 0;
  TRAINING_DATA.crosswalkRows.forEach((row) => {
    if (state.crosswalkAnswers[row.id] === row.correctStatus) correct += 1;
  });
  return { correct };
}

function scoreQuiz(answerSet) {
  let correct = 0;
  TRAINING_DATA.quizQuestions.forEach((question) => {
    if (Number(answerSet[question.id]) === question.answer) correct += 1;
  });
  return { correct };
}

function scoreChecklist() {
  return TRAINING_DATA.transferChecklist.reduce((sum, _item, index) => sum + (state.checklist[index] ? 1 : 0), 0);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setStatus(message) {
  const status = document.querySelector("#status");
  if (status) status.textContent = message;
}

function exportArtifact() {
  const comparisonLines = TRAINING_DATA.comparisonRows.map((row) => {
    const answer = state.comparisonAnswers[row.id] || "not answered";
    return `- ${row.domain}: ${answer} (expected: ${row.expected})`;
  }).join("\n");
  const crosswalkLines = TRAINING_DATA.crosswalkRows.map((row) => {
    const answer = state.crosswalkAnswers[row.id] || "not answered";
    return `- ${row.sourceVariable} -> ${row.candidate}: ${answer} (expected: ${row.correctStatus}); provenance: ${row.provenance}`;
  }).join("\n");
  const checklistLines = TRAINING_DATA.transferChecklist.map((item, index) => `- [${state.checklist[index] ? "x" : " "}] ${item}`).join("\n");
  const body = `# Metabo-Diet learner artifact

Generated from ${TRAINING_DATA.module.title}

## Scores

- Cohort comparison: ${scoreComparison().correct}/${TRAINING_DATA.comparisonRows.length}
- Crosswalk decisions: ${scoreCrosswalk().correct}/${TRAINING_DATA.crosswalkRows.length}
- Pre-test: ${scoreQuiz(state.quizAnswers).correct}/4
- Post-test: ${scoreQuiz(state.postQuizAnswers).correct}/4
- Transfer checklist: ${scoreChecklist()}/${TRAINING_DATA.transferChecklist.length}

## Cohort Comparison

${comparisonLines}

## Crosswalk Decisions

${crosswalkLines}

## Transfer Checklist

${checklistLines}

## Reflection Notes

${state.notes || "No notes entered."}
`;
  const blob = new Blob([body], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "metabo-diet-learner-artifact.md";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setStatus("Learner artifact exported.");
}

app.addEventListener("click", (event) => {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  const action = control.dataset.action;

  if (action === "set-lesson") {
    state.activeLesson = control.dataset.lesson;
  }

  if (action === "set-tab") {
    state.activeTab = control.dataset.tab;
  }

  if (action === "mark-complete") {
    if (!state.completedLessons.includes(state.activeLesson)) {
      state.completedLessons.push(state.activeLesson);
      setStatus("Section marked complete.");
    }
  }

  if (action === "select-crosswalk") {
    state.selectedCrosswalk = control.dataset.row;
  }

  if (action === "export") {
    exportArtifact();
    return;
  }

  if (action === "reset") {
    localStorage.removeItem(STORAGE_KEY);
    Object.assign(state, defaultState());
    setStatus("Session reset.");
  }

  saveState();
  render();
});

app.addEventListener("change", (event) => {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  const action = control.dataset.action;

  if (action === "comparison-answer") {
    state.comparisonAnswers[control.dataset.row] = control.value;
  }

  if (action === "crosswalk-answer") {
    state.crosswalkAnswers[control.dataset.row] = control.value;
    state.selectedCrosswalk = control.dataset.row;
  }

  if (action === "quiz-answer") {
    state[control.dataset.stateKey][control.dataset.question] = Number(control.value);
  }

  if (action === "checklist") {
    state.checklist[control.dataset.index] = control.checked;
  }

  saveState();
  render();
});

app.addEventListener("input", (event) => {
  const control = event.target.closest("[data-action='notes']");
  if (!control) return;
  state.notes = control.value;
  saveState();
});

render();
