// Fight Night Analyzer front end (FNA-3).
// Plain JavaScript, no framework. Every piece of AI text is inserted with
// textContent, never innerHTML, so a strange reply can't inject markup.

const form = document.getElementById("matchup-form");
const analyzeBtn = document.getElementById("analyze-btn");
const loadingNote = document.getElementById("loading-note");
const apiKeyInput = document.getElementById("api-key");
const errorBanner = document.getElementById("error-banner");
const errorText = document.getElementById("error-text");
const results = document.getElementById("results");

const fighterA = document.getElementById("fighter-a");
const fighterB = document.getElementById("fighter-b");

// Readable names for the stat keys the pipeline cites.
const STAT_LABELS = {
  wins: "Wins", losses: "Losses", height_in: "Height (in)", reach_in: "Reach (in)", age: "Age",
  slpm: "Strikes landed / min", str_acc_pct: "Striking accuracy %", sapm: "Strikes absorbed / min",
  str_def_pct: "Striking defense %", td_avg_per15: "Takedowns / 15 min", td_acc_pct: "Takedown accuracy %",
  td_def_pct: "Takedown defense %", sub_avg_per15: "Submission attempts / 15 min",
};


// ---- FNA-18: autocomplete ------------------------------------------------------

function setupAutocomplete(input) {
  const list = document.getElementById(input.id + "-list");
  let matches = [];
  let active = -1;   // which suggestion the arrow keys are on
  let timer = null;

  input.addEventListener("input", () => {
    delete input.dataset.id;  // typing again un-picks the fighter
    clearTimeout(timer);
    timer = setTimeout(() => search(input.value), 150);  // wait for a pause in typing
  });

  input.addEventListener("keydown", (e) => {
    if (list.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = (active + step + matches.length) % matches.length;
      highlight();
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(matches[active]);
    } else if (e.key === "Escape") {
      close();
    }
  });

  // Close when clicking anywhere else on the page.
  document.addEventListener("click", (e) => {
    if (!input.parentElement.contains(e.target)) close();
  });

  async function search(text) {
    if (!text.trim()) return close();
    try {
      const resp = await fetch("/api/fighters?q=" + encodeURIComponent(text));
      matches = (await resp.json()).results || [];
    } catch {
      matches = [];
    }
    render();
  }

  function render() {
    list.replaceChildren();
    active = -1;
    if (matches.length === 0) {
      list.append(el("li", "no-match", "No fighters found"));
    }
    matches.forEach((f, i) => {
      const item = el("li", "suggestion");
      item.setAttribute("role", "option");
      item.append(el("span", "name", f.name));
      const extra = [f.nickname ? `"${f.nickname}"` : null, f.division].filter(Boolean).join(" · ");
      item.append(el("span", "meta", extra));
      // mousedown fires before the input loses focus, so the click isn't lost
      item.addEventListener("mousedown", (e) => { e.preventDefault(); choose(matches[i]); });
      list.append(item);
    });
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function highlight() {
    [...list.children].forEach((item, i) => item.classList.toggle("active", i === active));
  }

  function choose(fighter) {
    input.value = fighter.name;
    input.dataset.id = fighter.id;
    close();
  }

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
  }
}

setupAutocomplete(fighterA);
setupAutocomplete(fighterB);


// ---- Submitting a matchup --------------------------------------------------------

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  const idA = fighterA.dataset.id;
  const idB = fighterB.dataset.id;
  if (!idA || !idB) return showError("Pick both fighters from the suggestions list.");
  if (idA === idB) return showError("Choose two different fighters.");

  const body = { fighter_a: idA, fighter_b: idB };
  if (apiKeyInput.value.trim()) body.api_key = apiKeyInput.value.trim();

  setLoading(true);
  try {
    const resp = await fetch("/api/matchup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      showError(data.error || "Something went wrong. Please try again.");
    } else {
      renderResults(data);
    }
  } catch {
    showError("Couldn't reach the server. Check that it's running and try again.");
  } finally {
    setLoading(false);
  }
});


// ---- FNA-20: loading and disabled states -----------------------------------------

function setLoading(on) {
  analyzeBtn.disabled = on;
  analyzeBtn.textContent = on ? "Analyzing…" : "Analyze";
  fighterA.disabled = on;
  fighterB.disabled = on;
  apiKeyInput.disabled = on;
  loadingNote.hidden = !on;
  form.setAttribute("aria-busy", on ? "true" : "false");
}


// ---- FNA-21: error banner ------------------------------------------------------------

function showError(message) {
  errorText.textContent = message;
  errorBanner.hidden = false;
}

function hideError() {
  errorBanner.hidden = true;
}

document.getElementById("error-close").addEventListener("click", hideError);


// ---- FNA-19: rendering the results ---------------------------------------------------

function renderResults(data) {
  const a = data.analysis;
  const names = { [data.fighter_a.id]: data.fighter_a.name, [data.fighter_b.id]: data.fighter_b.name };
  const nameOf = (id) => names[id] || "Even";

  results.replaceChildren();

  // The verdict comes first, since it's what people look for.
  const verdict = el("div", "verdict");
  verdict.append(el("p", "label", "Predicted winner"));
  verdict.append(el("p", "winner", nameOf(a.predicted_winner_id)));
  verdict.append(el("p", "method", `by ${a.method} · ${a.confidence} confidence`));
  results.append(verdict);

  if (data.cross_division) {
    results.append(el("p", "cross-note",
      `Cross-division matchup: ${data.fighter_a.name} fights at ${data.fighter_a.division}, ` +
      `${data.fighter_b.name} at ${data.fighter_b.division}.`));
  }

  results.append(el("p", "summary", a.summary));

  // Key factors, each tagged with who it favors.
  const factors = el("div", "factors");
  factors.append(el("h2", null, "Key factors"));
  for (const kf of a.key_factors) {
    const item = el("div", "factor");
    const head = el("div", "factor-head");
    head.append(el("span", "factor-name", kf.factor));
    head.append(el("span", kf.favors === "even" ? "tag even" : "tag", "Favors " + nameOf(kf.favors)));
    item.append(head);
    item.append(el("p", null, kf.reasoning));
    if (kf.evidence && kf.evidence.length) {  // v4 only
      const cited = kf.evidence.map((ev) => `${nameOf(ev.fighter_id)} ${STAT_LABELS[ev.stat] || ev.stat}: ${ev.value}`);
      item.append(el("p", "evidence", "Evidence: " + cited.join(" · ")));
    }
    factors.append(item);
  }
  results.append(factors);

  // One card per fighter, with their path to victory.
  const cards = el("div", "cards");
  cards.append(profileCard(data.profiles.fighter_a, data.fighter_a, a.fighter_a_path_to_victory));
  cards.append(profileCard(data.profiles.fighter_b, data.fighter_b, a.fighter_b_path_to_victory));
  results.append(cards);

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function profileCard(profile, fighter, path) {
  const card = el("article", "card");
  card.append(el("h3", null, profile.name));
  card.append(el("p", "card-meta", `${fighter.division} · ${profile.style}`));

  card.append(el("h4", null, "Strengths"));
  card.append(list(profile.strengths));
  card.append(el("h4", null, "Weaknesses"));
  card.append(list(profile.weaknesses));

  card.append(el("h4", null, "Striking"));
  card.append(el("p", null, profile.striking_summary));
  card.append(el("h4", null, "Grappling"));
  card.append(el("p", null, profile.grappling_summary));

  card.append(el("h4", null, "Key stats"));
  const table = el("table", "stats");
  for (const ks of profile.key_stats) {
    const row = el("tr");
    row.append(el("th", null, STAT_LABELS[ks.stat] || ks.stat));
    row.append(el("td", "value", String(ks.value)));
    row.append(el("td", "meaning", ks.meaning));
    table.append(row);
  }
  card.append(table);

  card.append(el("h4", null, "Path to victory"));
  card.append(el("p", null, path));
  return card;
}


// ---- Footer: warn when the stats are still placeholders ------------------------------

fetch("/api/health")
  .then((resp) => resp.json())
  .then((health) => {
    if (health.data && !health.data.verified) {
      const note = document.getElementById("data-note");
      note.textContent = "Note: fighter stats are placeholder values until they're verified against ufcstats.com.";
      note.hidden = false;
    }
  })
  .catch(() => {});


// ---- Small helpers ------------------------------------------------------------------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function list(items) {
  const ul = el("ul");
  for (const item of items) ul.append(el("li", null, item));
  return ul;
}
