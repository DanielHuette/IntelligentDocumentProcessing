/**
 * Benchmark charts drawn from the measurement file.
 *
 * Context: Loaded when the Benchmarks tab opens for the first time. messung.json is a byte-for-byte
 *          copy of results/summary.json (a test keeps both equal), so every mark on this tab comes
 *          from the measurement of 8 October 2026. The full table below the charts is static HTML.
 * Input:   The tab panel with four figures ([data-diagramm]) and web/messung.json.
 * Output:  Inline SVG charts with hover and keyboard tooltips, redrawn when their width changes.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const COLORS = {
  ours: "#c9a96e",
  rest: "#6b7a94",
  needless: "#5a86d0",
  wrong: "#e0695c",
  ring: "#0b1a33",
  jev: "#ead7ae",
};

const percent = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat("de-DE");
const dollars = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtPercent = (value) => `${percent.format(value)} %`;
const fmtMs = (value) => `${integer.format(value)} ms`;
const fmtCost = (value) => `${dollars.format(value)} $`;

function svgElement(name, attributes = {}, text) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== undefined) element.textContent = text;
  return element;
}

function displayName(system) {
  return system.label.replace(" (hybrid)", "");
}

function logScale(domainMin, domainMax, rangeMin, rangeMax) {
  const a = Math.log10(domainMin);
  const b = Math.log10(domainMax);
  return (value) => rangeMin + ((Math.log10(value) - a) / (b - a)) * (rangeMax - rangeMin);
}

function linearScale(domainMin, domainMax, rangeMin, rangeMax) {
  return (value) => rangeMin + ((value - domainMin) / (domainMax - domainMin)) * (rangeMax - rangeMin);
}

/** Bar from a baseline with a 4px rounded data end and a square end at the baseline. */
function barPath(x0, x1, y, height) {
  const radius = Math.min(4, Math.abs(x1 - x0), height / 2);
  if (Math.abs(x1 - x0) < 0.5) return "";
  const dir = x1 > x0 ? 1 : -1;
  const xr = x1 - dir * radius;
  const sweep = dir > 0 ? 1 : 0;
  return [
    `M${x0} ${y}`, `H${xr}`, `A${radius} ${radius} 0 0 ${sweep} ${x1} ${y + radius}`,
    `V${y + height - radius}`, `A${radius} ${radius} 0 0 ${sweep} ${xr} ${y + height}`, `H${x0}`, "Z",
  ].join(" ");
}

function tooltipRows(system) {
  return [
    ["Weiche richtig", fmtPercent(system.route_accuracy)],
    ["Fälschlich freigegeben", integer.format(system.wrongly_approved)],
    ["Unnötig zur Prüfung", integer.format(system.needless_reviews)],
    ["Formprüfung", fmtPercent(system.completeness_accuracy)],
    ["Antwortzeit Median", fmtMs(system.latency_p50_ms)],
    ["Kosten je 1.000", fmtCost(system.cost_per_1000_usd)],
  ];
}

/** Shared tooltip of one figure, positioned next to the hovered or focused target. */
function createTooltip(figure) {
  const tip = document.createElement("div");
  tip.className = "tipp";
  tip.setAttribute("aria-hidden", "true");
  figure.append(tip);
  return {
    show(target, title, rows) {
      tip.replaceChildren();
      const heading = document.createElement("b");
      heading.textContent = title;
      const list = document.createElement("dl");
      for (const [term, value] of rows) {
        const dt = document.createElement("dt");
        dt.textContent = term;
        const dd = document.createElement("dd");
        dd.textContent = value;
        list.append(dt, dd);
      }
      tip.append(heading, list);
      const box = figure.getBoundingClientRect();
      const anchor = target.getBoundingClientRect();
      const width = tip.offsetWidth;
      let left = anchor.left - box.left + anchor.width / 2 - width / 2;
      left = Math.max(8, Math.min(left, box.width - width - 8));
      let top = anchor.top - box.top - tip.offsetHeight - 10;
      if (top < 8) top = anchor.bottom - box.top + 10;
      tip.style.setProperty("left", `${left}px`);
      tip.style.setProperty("top", `${top}px`);
      tip.classList.add("ist-sichtbar");
    },
    hide() {
      tip.classList.remove("ist-sichtbar");
    },
  };
}

/** Transparent hit area bigger than the mark, reachable by pointer and keyboard. */
function addTarget(svg, tooltip, shape, title, rows) {
  const group = svgElement("g", { class: "ziel", tabindex: 0, role: "img", "aria-label": `${title}: ${rows.map((r) => r.join(" ")).join(", ")}` });
  const hit = svgElement(shape.kind, { ...shape.attributes, class: "treffer" });
  group.append(hit);
  svg.append(group);
  const show = () => tooltip.show(hit, title, rows);
  group.addEventListener("pointerenter", show);
  group.addEventListener("focus", show);
  group.addEventListener("pointerleave", tooltip.hide);
  group.addEventListener("blur", tooltip.hide);
  return group;
}

function overlaps(a, b) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

/** Put each label at the first candidate position that collides with nothing placed so far. */
function placeLabels(labels, obstacles, width) {
  const placed = [...obstacles];
  for (const { element, x, y, r } of labels) {
    const candidates = [
      [x + r + 6, y + 4, "start"], [x - r - 6, y + 4, "end"], [x, y - r - 6, "middle"],
      [x, y + r + 14, "middle"], [x + r + 4, y - r - 4, "start"], [x - r - 4, y - r - 4, "end"],
      [x + r + 4, y + r + 12, "start"], [x - r - 4, y + r + 12, "end"],
    ];
    for (const [cx, cy, anchor] of candidates) {
      element.setAttribute("x", cx);
      element.setAttribute("y", cy);
      element.setAttribute("text-anchor", anchor);
      const box = element.getBBox();
      const inside = box.x >= 0 && box.x + box.width <= width;
      if (inside && !placed.some((other) => overlaps(box, other))) break;
    }
    placed.push(element.getBBox());
  }
}

function drawSafetyChart(figure, data, width, tooltip) {
  const narrow = width < 520;
  const height = narrow ? 320 : 380;
  const m = { left: 34, right: 10, top: 26, bottom: 46 };
  const x = logScale(0.3, 14, m.left, width - m.right);
  const y = linearScale(-1, 14, height - m.bottom, m.top);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": "Fälschlich freigegebene Rechnungen gegen Kosten je 1.000 Dokumente" });
  const axis = svgElement("g", { class: "achse" });
  for (const tick of [0, 5, 10]) {
    axis.append(svgElement("line", { class: tick === 0 ? "nulllinie" : "gitter", x1: m.left, x2: width - m.right, y1: y(tick), y2: y(tick) }));
    axis.append(svgElement("text", { x: m.left - 8, y: y(tick) + 4, "text-anchor": "end" }, integer.format(tick)));
  }
  const costTicks = narrow ? [0.5, 1, 2, 5, 10] : [0.3, 0.5, 1, 2, 5, 10];
  for (const tick of costTicks) {
    axis.append(svgElement("line", { class: "gitter", x1: x(tick), x2: x(tick), y1: m.top, y2: height - m.bottom }));
    axis.append(svgElement("text", { x: x(tick), y: height - m.bottom + 18, "text-anchor": "middle" }, tick < 1 ? fmtCost(tick) : `${integer.format(tick)} $`));
  }
  axis.append(svgElement("text", { x: m.left - 30, y: 12 }, "Fälschlich freigegeben (Anzahl)"));
  axis.append(svgElement("text", { x: width - m.right, y: height - 6, "text-anchor": "end" }, "Kosten je 1.000 Dokumente, Achse in Zehnerschritten"));
  svg.append(axis);
  figure.querySelector("[data-flaeche]").replaceChildren(svg);

  const ordered = [...data.systems].sort((a, b) => (a.system === "hybrid") - (b.system === "hybrid"));
  const labels = [];
  const obstacles = [];
  for (const system of ordered) {
    const ours = system.system === "hybrid";
    const cx = x(system.cost_per_1000_usd);
    const cy = y(system.wrongly_approved);
    const r = ours ? 7 : 5;
    svg.append(svgElement("circle", { cx, cy, r: r + 2, fill: COLORS.ring }));
    svg.append(svgElement("circle", { cx, cy, r, fill: ours ? COLORS.ours : COLORS.rest }));
    obstacles.push({ x: cx - r - 2, y: cy - r - 2, width: 2 * r + 4, height: 2 * r + 4 });
    const label = svgElement("text", { class: ours ? "name name--unser" : "name" }, displayName(system));
    svg.append(label);
    labels.push({ element: label, x: cx, y: cy, r, ours });
    addTarget(svg, tooltip, { kind: "circle", attributes: { cx, cy, r: 16 } }, displayName(system), tooltipRows(system));
  }
  labels.sort((a, b) => b.ours - a.ours);
  placeLabels(labels, obstacles, width);
}

function drawErrorChart(figure, data, width, tooltip) {
  const rows = [...data.systems].sort((a, b) =>
    (a.wrongly_approved + a.needless_reviews) - (b.wrongly_approved + b.needless_reviews) || a.wrongly_approved - b.wrongly_approved);
  const rowHeight = 44;
  const top = 6;
  const height = top + rows.length * rowHeight + 22;
  const center = width / 2;
  const half = center - 30;
  const scale = (value) => (value / 14) * half;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": "Fehler der Weiche je System" });
  const axis = svgElement("g", { class: "achse" });
  for (const tick of [5, 10]) {
    for (const side of [-1, 1]) {
      const gx = center + side * scale(tick);
      axis.append(svgElement("line", { class: "gitter", x1: gx, x2: gx, y1: top, y2: height - 22 }));
      axis.append(svgElement("text", { x: gx, y: height - 6, "text-anchor": "middle" }, integer.format(tick)));
    }
  }
  axis.append(svgElement("line", { class: "nulllinie", x1: center, x2: center, y1: top, y2: height - 22 }));
  axis.append(svgElement("text", { x: center, y: height - 6, "text-anchor": "middle" }, "0"));
  svg.append(axis);
  rows.forEach((system, index) => {
    const ours = system.system === "hybrid";
    const rowTop = top + index * rowHeight;
    const barY = rowTop + 22;
    svg.append(svgElement("text", { class: ours ? "name name--unser" : "name", x: 0, y: rowTop + 14 }, displayName(system)));
    const left = barPath(center - 1, center - 1 - scale(system.needless_reviews), barY, 14);
    const right = barPath(center + 1, center + 1 + scale(system.wrongly_approved), barY, 14);
    if (left) svg.append(svgElement("path", { d: left, fill: COLORS.needless }));
    if (right) svg.append(svgElement("path", { d: right, fill: COLORS.wrong }));
    if (system.needless_reviews > 0) {
      svg.append(svgElement("text", { class: "wert wert--stark", x: center - 6 - scale(system.needless_reviews), y: barY + 11, "text-anchor": "end" }, integer.format(system.needless_reviews)));
    }
    if (system.wrongly_approved > 0) {
      svg.append(svgElement("text", { class: "wert wert--stark", x: center + 6 + scale(system.wrongly_approved), y: barY + 11 }, integer.format(system.wrongly_approved)));
    }
    if (system.needless_reviews + system.wrongly_approved === 0) {
      svg.append(svgElement("text", { class: "wert", x: center + 8, y: barY + 11 }, "kein Fehler"));
    }
    addTarget(svg, tooltip, { kind: "rect", attributes: { x: 0, y: rowTop, width, height: rowHeight } }, displayName(system), tooltipRows(system));
  });
  const legend = document.createElement("p");
  legend.className = "legende";
  legend.innerHTML = '<span><i class="legende__needless"></i>Unnötig zur Prüfung, kostet eine Minute</span><span><i class="legende__wrong"></i>Fälschlich freigegeben, kostet Geld</span>';
  legend.querySelector(".legende__needless").style.setProperty("background", COLORS.needless);
  legend.querySelector(".legende__wrong").style.setProperty("background", COLORS.wrong);
  figure.querySelector("[data-flaeche]").replaceChildren(legend, svg);
}

function drawLatencyChart(figure, data, width, tooltip) {
  const jev = { system: "jev", label: "Nur Jev, Entscheidung", latency_p50_ms: data.jev_call_latency.p50_ms, latency_p95_ms: data.jev_call_latency.p95_ms };
  const rows = [jev, ...[...data.systems].sort((a, b) => a.latency_p50_ms - b.latency_p50_ms)];
  const rowHeight = 40;
  const top = 6;
  const height = top + rows.length * rowHeight + 24;
  const x = logScale(250, 60000, 6, width - 12);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": "Antwortzeit je System, Median und 95 Prozent" });
  const axis = svgElement("g", { class: "achse" });
  for (const [tick, text] of [[300, "300 ms"], [1000, "1 s"], [3000, "3 s"], [10000, "10 s"], [30000, "30 s"]]) {
    axis.append(svgElement("line", { class: "gitter", x1: x(tick), x2: x(tick), y1: top, y2: height - 24 }));
    axis.append(svgElement("text", { x: x(tick), y: height - 6, "text-anchor": "middle" }, text));
  }
  svg.append(axis);
  rows.forEach((system, index) => {
    const ours = system.system === "hybrid" || system.system === "jev";
    const color = system.system === "jev" ? COLORS.jev : ours ? COLORS.ours : COLORS.rest;
    const rowTop = top + index * rowHeight;
    const cy = rowTop + 28;
    const x50 = x(system.latency_p50_ms);
    const x95 = x(system.latency_p95_ms);
    svg.append(svgElement("text", { class: ours ? "name name--unser" : "name", x: 0, y: rowTop + 13 }, displayName(system)));
    svg.append(svgElement("line", { x1: x50, x2: x95, y1: cy, y2: cy, stroke: color, "stroke-width": 2, "stroke-linecap": "round" }));
    svg.append(svgElement("circle", { cx: x95, cy, r: 4, fill: COLORS.ring, stroke: color, "stroke-width": 2 }));
    svg.append(svgElement("circle", { cx: x50, cy, r: 7, fill: COLORS.ring }));
    svg.append(svgElement("circle", { cx: x50, cy, r: 5, fill: color }));
    if (["jev", "hybrid", "deepseek"].includes(system.system)) {
      const right = x95 + 10 + 60 < width;
      svg.append(svgElement("text", { class: "wert wert--stark", x: right ? x95 + 10 : x50 - 12, y: cy + 4, "text-anchor": right ? "start" : "end" }, fmtMs(system.latency_p50_ms)));
    }
    const rowsForTip = [["Median", fmtMs(system.latency_p50_ms)], ["95 % schneller als", fmtMs(system.latency_p95_ms)]];
    if (system.system === "jev") rowsForTip.push(["Aufrufe", integer.format(data.jev_call_latency.count)]);
    addTarget(svg, tooltip, { kind: "rect", attributes: { x: 0, y: rowTop, width, height: rowHeight } }, displayName(system), rowsForTip);
  });
  const legend = document.createElement("p");
  legend.className = "legende";
  legend.innerHTML = '<span><i class="legende__voll"></i>Median</span><span><i class="legende__ring"></i>95 % der Anfragen waren schneller</span>';
  legend.querySelector(".legende__voll").style.setProperty("background", COLORS.rest);
  legend.querySelector(".legende__voll").style.setProperty("border-radius", "50%");
  const ring = legend.querySelector(".legende__ring");
  ring.style.setProperty("border", `2px solid ${COLORS.rest}`);
  ring.style.setProperty("border-radius", "50%");
  const note = document.createElement("p");
  note.className = "hinweis-achse";
  note.textContent = "Die Achse wächst in Zehnerschritten, damit auch die schnellen Systeme lesbar bleiben.";
  figure.querySelector("[data-flaeche]").replaceChildren(legend, svg, note);
}

function drawFormChart(figure, data, width, tooltip) {
  const rows = [...data.systems].sort((a, b) => b.completeness_accuracy - a.completeness_accuracy);
  const rowHeight = 38;
  const top = 6;
  const height = top + rows.length * rowHeight + 24;
  const x = linearScale(85, 100, 6, width - 14);
  const highest = rows[0].system;
  const lowest = rows[rows.length - 1].system;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": "Formprüfung richtig je System" });
  const axis = svgElement("g", { class: "achse" });
  for (const tick of [85, 90, 95, 100]) {
    axis.append(svgElement("line", { class: "gitter", x1: x(tick), x2: x(tick), y1: top, y2: height - 24 }));
    axis.append(svgElement("text", { x: x(tick), y: height - 6, "text-anchor": "middle" }, `${tick} %`));
  }
  svg.append(axis);
  rows.forEach((system, index) => {
    const ours = system.system === "hybrid";
    const rowTop = top + index * rowHeight;
    const cy = rowTop + 26;
    const cx = x(system.completeness_accuracy);
    svg.append(svgElement("text", { class: ours ? "name name--unser" : "name", x: 0, y: rowTop + 13 }, displayName(system)));
    svg.append(svgElement("line", { class: "gitter", x1: x(85), x2: cx, y1: cy, y2: cy }));
    svg.append(svgElement("circle", { cx, cy, r: 7, fill: COLORS.ring }));
    svg.append(svgElement("circle", { cx, cy, r: 5, fill: ours ? COLORS.ours : COLORS.rest }));
    if (ours || system.system === highest || system.system === lowest) {
      const right = cx + 60 < width;
      svg.append(svgElement("text", { class: "wert wert--stark", x: right ? cx + 12 : cx - 12, y: cy + 4, "text-anchor": right ? "start" : "end" }, fmtPercent(system.completeness_accuracy)));
    }
    addTarget(svg, tooltip, { kind: "rect", attributes: { x: 0, y: rowTop, width, height: rowHeight } }, displayName(system), [
      ["Formprüfung", fmtPercent(system.completeness_accuracy)],
      ["Dokumentart", fmtPercent(system.document_type_accuracy)],
      ["Lieferant", fmtPercent(system.vendor_accuracy)],
      ["Bruttobetrag", fmtPercent(system.gross_accuracy)],
    ]);
  });
  figure.querySelector("[data-flaeche]").replaceChildren(svg);
}

const DRAWERS = { sicherheit: drawSafetyChart, fehler: drawErrorChart, zeit: drawLatencyChart, form: drawFormChart };

export async function start(panel) {
  const response = await fetch("messung.json", { cache: "no-cache" });
  if (!response.ok) return { setVisible() {} };
  const data = await response.json();
  for (const figure of panel.querySelectorAll("[data-diagramm]")) {
    const draw = DRAWERS[figure.dataset.diagramm];
    const area = figure.querySelector("[data-flaeche]");
    const tooltip = createTooltip(figure);
    let lastWidth = 0;
    const render = () => {
      const width = Math.round(area.getBoundingClientRect().width || figure.clientWidth - 44);
      if (width < 120 || width === lastWidth) return;
      lastWidth = width;
      tooltip.hide();
      draw(figure, data, width, tooltip);
    };
    new ResizeObserver(() => requestAnimationFrame(render)).observe(figure);
    render();
  }
  return { setVisible() {} };
}
