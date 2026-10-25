/**
 * Animated organisation chart: a document travels through the five stations of the pipeline.
 *
 * Context: Loaded when the Organigramm tab opens for the first time. The four cases are the
 *          three demo documents of the live form plus a second submission of a booked invoice;
 *          their messages restate the outcomes described on the Projekt tab.
 * Input:   The tab panel with .fluss, its stations ([data-station]) and the case buttons.
 * Output:  Connector paths drawn between stations, a moving document marker and per-station
 *          messages. With reduced motion the chosen case is shown at once, without travel.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const TRAVEL_MS = 850;
const DWELL_MS = 1500;
const FINAL_DWELL_MS = 3200;

const EDGES = [
  ["formular", "jev"],
  ["jev", "haiku"],
  ["haiku", "regeln"],
  ["regeln", "gebucht"],
  ["regeln", "pruefung"],
  ["gebucht", "pruefung", "schleife"],
];

const CASES = {
  telekom: {
    name: "Telekom, sauber",
    good: true,
    steps: [
      ["formular", "Beispiel „Telekom – sauberer Durchlauf“, mit neuer Rechnungsnummer."],
      ["jev", "Rechnung, Lieferant Telekom, Pflichtangaben vollständig. Alle drei über der Schwelle von 85 %."],
      ["haiku", "Netto 152,15 €, Steuer 28,91 €, Brutto 181,06 €, Rechnungsnummer vorhanden."],
      ["regeln", "152,15 € plus 28,91 € ergibt 181,06 €, Steuersatz 19 %. Alles stimmt: Zweig A."],
      ["gebucht", "Gebucht."],
    ],
  },
  aws: {
    name: "AWS, Rechenfehler",
    good: false,
    steps: [
      ["formular", "Beispiel „AWS – Rechenfehler“."],
      ["jev", "Rechnung, Lieferant Amazon Web Services, Pflichtangaben vollständig. Jev ist sich sicher."],
      ["haiku", "Netto 760,55 €, Steuer 144,50 €, Brutto 914,05 €, so übernommen, wie gedruckt."],
      ["regeln", "760,55 € plus 144,50 € ergibt 905,05 €, nicht 914,05 €. Zweig B."],
      ["pruefung", "Zur Prüfung. Grund: Die Summen stimmen nicht."],
    ],
  },
  global: {
    name: "Unbekannter Absender",
    good: false,
    steps: [
      ["formular", "Beispiel „Global AI Shapers – unbekannter Absender“."],
      ["jev", "Scheinrechnung. Der Absender steht nicht unter den 15 Lieferanten."],
      ["haiku", "6.000,00 € ohne Steuer. Warnung: geänderte Bankverbindung."],
      ["regeln", "Keine Rechnung, kein bekannter Lieferant, 0 % ist kein deutscher Steuersatz. Zweig B."],
      ["pruefung", "Zur Prüfung, mit Betrugsverdacht."],
    ],
  },
  doppelt: {
    name: "Zweimal eingereicht",
    good: false,
    steps: [
      ["formular", "Eigener Text: eine Rechnung, die schon einmal gebucht wurde."],
      ["jev", "Rechnung, bekannter Lieferant, Pflichtangaben vollständig."],
      ["haiku", "Beträge und Rechnungsnummer ausgelesen."],
      ["regeln", "Alle Prüfungen bestanden: Zweig A."],
      ["gebucht", "Der Trigger findet dieselbe Rechnungsnummer unter den gebuchten Rechnungen."],
      ["pruefung", "Zur Prüfung. Grund: Rechnung ist bereits gebucht."],
    ],
  },
};
const ORDER = Object.keys(CASES);

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

/** Bezier from the side of one box to the facing side of the other, in container pixels. */
function connectorPath(from, to) {
  if (to.left >= from.right - 1) {
    const [x1, y1, x2, y2] = [from.right, from.cy, to.left, to.cy];
    const dx = (x2 - x1) / 2;
    return `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`;
  }
  if (to.top >= from.bottom - 1) {
    const [x1, y1, x2, y2] = [from.cx, from.bottom, to.cx, to.top];
    const dy = (y2 - y1) / 2;
    return `M${x1} ${y1} C${x1} ${y1 + dy} ${x2} ${y2 - dy} ${x2} ${y2}`;
  }
  return `M${from.cx} ${from.cy} L${to.cx} ${to.cy}`;
}

function boxOf(element, origin) {
  const rect = element.getBoundingClientRect();
  const left = rect.left - origin.left;
  const top = rect.top - origin.top;
  return {
    left, top, right: left + rect.width, bottom: top + rect.height,
    cx: left + rect.width / 2, cy: top + rect.height / 2,
  };
}

/** Create the connector layer once and return a function that redraws it for the current layout. */
function buildConnectors(flow, svg, stations) {
  const defs = svgElement("defs");
  const marker = svgElement("marker", {
    id: "pfeil", viewBox: "0 0 10 10", refX: "8", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M1 1L8 5L1 9", fill: "none", stroke: "#c9a96e", "stroke-width": "1.6" }));
  defs.append(marker);
  svg.append(defs);
  const paths = new Map();
  for (const [from, to, kind] of EDGES) {
    const path = svgElement("path", { class: kind ? `linie linie--${kind}` : "linie", "marker-end": "url(#pfeil)" });
    svg.append(path);
    paths.set(`${from}>${to}`, path);
  }
  const redraw = () => {
    const origin = flow.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${origin.width} ${origin.height}`);
    for (const [from, to] of EDGES) {
      const d = connectorPath(boxOf(stations.get(from), origin), boxOf(stations.get(to), origin));
      paths.get(`${from}>${to}`).setAttribute("d", d);
    }
  };
  return { paths, redraw };
}

/** Clock that only advances while the animation is playing and on screen. */
function createClock(state) {
  return function run(duration, onFrame) {
    const runId = state.runId;
    return new Promise((resolve) => {
      let elapsed = 0;
      let last = performance.now();
      const frame = (now) => {
        if (runId !== state.runId) return resolve(false);
        if (state.playing && state.visible) elapsed += now - last;
        last = now;
        const progress = Math.min(1, elapsed / duration);
        onFrame?.(progress);
        if (progress >= 1) return resolve(true);
        requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    });
  };
}

export function start(panel) {
  const flow = panel.querySelector("[data-fluss]");
  const svg = flow.querySelector(".fluss__linien");
  const stations = new Map([...flow.querySelectorAll("[data-station]")].map((el) => [el.dataset.station, el]));
  const caseButtons = [...panel.querySelectorAll("[data-fall]")];
  const playButton = panel.querySelector("[data-fluss-abspiel]");
  const log = panel.querySelector("[data-protokoll]");
  const { paths, redraw } = buildConnectors(flow, svg, stations);
  const token = svgElement("g", { class: "marke-dok" });
  token.append(
    svgElement("circle", { r: "11", fill: "rgba(201,169,110,0.25)" }),
    svgElement("rect", { x: "-5", y: "-6.5", width: "10", height: "13", rx: "1.5", fill: "#f6f1e4" }),
    svgElement("path", { d: "M-2.5 -2.5H2.5M-2.5 0.5H2.5M-2.5 3.5H1", stroke: "#13203a", "stroke-width": "1" }),
  );
  token.style.setProperty("opacity", "0");
  svg.append(token);

  const state = { playing: !reducedMotion.matches, visible: false, autoplay: !reducedMotion.matches, runId: 0, caseKey: "telekom" };
  const clock = createClock(state);

  function setPlaying(playing) {
    state.playing = playing;
    playButton.setAttribute("aria-pressed", String(playing));
    playButton.querySelector(".abspiel__text").textContent = playing ? "Anhalten" : "Abspielen";
    log.setAttribute("aria-live", state.autoplay && playing ? "off" : "polite");
  }

  function reset(caseKey) {
    state.caseKey = caseKey;
    for (const button of caseButtons) button.setAttribute("aria-pressed", String(button.dataset.fall === caseKey));
    for (const station of stations.values()) {
      station.classList.remove("ist-aktiv", "ist-erledigt", "ist-gut", "ist-schlecht");
      station.querySelector("[data-meldung]").textContent = "";
    }
    for (const path of paths.values()) path.classList.remove("ist-aktiv");
    token.style.setProperty("opacity", "0");
    log.textContent = "";
  }

  function arrive(caseData, key, message, isLast) {
    for (const station of stations.values()) {
      if (station.classList.contains("ist-aktiv")) station.classList.replace("ist-aktiv", "ist-erledigt");
    }
    const station = stations.get(key);
    station.classList.add("ist-aktiv");
    if (isLast) station.classList.add(caseData.good ? "ist-gut" : "ist-schlecht");
    station.querySelector("[data-meldung]").textContent = message;
    log.textContent = `${caseData.name}: ${message}`;
  }

  function placeToken(path, progress) {
    const length = path.getTotalLength();
    const point = path.getPointAtLength(length * progress);
    token.setAttribute("transform", `translate(${point.x} ${point.y})`);
  }

  function showStatic(caseKey) {
    reset(caseKey);
    const caseData = CASES[caseKey];
    caseData.steps.forEach(([key, message], index) => {
      if (index > 0) paths.get(`${caseData.steps[index - 1][0]}>${key}`).classList.add("ist-aktiv");
      arrive(caseData, key, message, index === caseData.steps.length - 1);
    });
  }

  async function play(caseKey) {
    state.runId += 1;
    const runId = state.runId;
    reset(caseKey);
    flow.classList.add("laeuft");
    const caseData = CASES[caseKey];
    const [firstKey, firstMessage] = caseData.steps[0];
    arrive(caseData, firstKey, firstMessage, false);
    if (!(await clock(DWELL_MS))) return;
    for (let index = 1; index < caseData.steps.length; index += 1) {
      const [key, message] = caseData.steps[index];
      const path = paths.get(`${caseData.steps[index - 1][0]}>${key}`);
      token.style.setProperty("opacity", "1");
      const travelled = await clock(TRAVEL_MS, (p) => placeToken(path, 1 - (1 - p) ** 3));
      if (!travelled) return;
      path.classList.add("ist-aktiv");
      const isLast = index === caseData.steps.length - 1;
      arrive(caseData, key, message, isLast);
      if (!(await clock(isLast ? FINAL_DWELL_MS : DWELL_MS))) return;
    }
    token.style.setProperty("opacity", "0");
    flow.classList.remove("laeuft");
    if (runId !== state.runId) return;
    if (state.autoplay) {
      play(ORDER[(ORDER.indexOf(caseKey) + 1) % ORDER.length]);
    } else {
      setPlaying(false);
    }
  }

  for (const button of caseButtons) {
    button.addEventListener("click", () => {
      state.autoplay = false;
      if (reducedMotion.matches) {
        showStatic(button.dataset.fall);
        return;
      }
      setPlaying(true);
      play(button.dataset.fall);
    });
  }

  playButton.addEventListener("click", () => {
    if (state.playing) {
      setPlaying(false);
      return;
    }
    state.autoplay = true;
    setPlaying(true);
    if (!flow.classList.contains("laeuft")) {
      const next = reducedMotion.matches ? state.caseKey : ORDER[(ORDER.indexOf(state.caseKey) + 1) % ORDER.length];
      if (reducedMotion.matches) showStatic(next); else play(next);
    }
  });

  new ResizeObserver(redraw).observe(flow);
  document.fonts?.ready.then(redraw);
  redraw();

  if (reducedMotion.matches) {
    playButton.hidden = true;
    showStatic("telekom");
  } else {
    setPlaying(true);
    play("telekom");
  }

  return {
    setVisible(visible) {
      state.visible = visible;
      if (visible) redraw();
    },
  };
}
