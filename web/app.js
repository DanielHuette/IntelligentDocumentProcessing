/**
 * Tab navigation for the project page.
 *
 * Context: Four tabs (Projekt, Organigramm, Benchmarks, Präsentation) share one page. Each tab is
 *          deep-linkable through its hash, browser back and forward switch tabs, and the scripts
 *          of the heavier tabs load only when their tab opens for the first time.
 * Input:   location.hash, clicks and arrow keys on the tab bar, links to #ids inside the page.
 * Output:  data-tab on the html element, ARIA state on the tab buttons, lazily started tab modules.
 */

const TABS = ["projekt", "organigramm", "benchmarks", "praesentation"];
const DEFAULT_TAB = "projekt";
const MODULES = {
  organigramm: () => import("./organigramm.js"),
  benchmarks: () => import("./benchmarks.js"),
  praesentation: () => import("./praesentation.js"),
};

const root = document.documentElement;
const buttons = [...document.querySelectorAll("[data-reiter]")];
const started = new Map();
const scrollByTab = new Map();
let current = null;

/** Return the tab that owns the element with this id, or null. */
function tabForId(id) {
  if (TABS.includes(id)) return id;
  const target = id ? document.getElementById(id) : null;
  const panel = target?.closest("[role='tabpanel']");
  return panel ? panel.id : null;
}

/** Load and start a tab module once; later calls only report visibility. */
async function notifyModule(tab, visible) {
  const load = MODULES[tab];
  if (!load) return;
  if (!started.has(tab)) {
    if (!visible) return;
    started.set(tab, load().then((module) => module.start(document.getElementById(tab))));
  }
  const controller = await started.get(tab);
  controller?.setVisible(visible);
}

/** Show one tab, update the tab bar and remember where the previous tab was scrolled. */
function activate(tab, { focusPanel = false, scrollTo = null } = {}) {
  if (current && current !== tab) scrollByTab.set(current, window.scrollY);
  const changed = current !== tab;
  const previous = current;
  current = tab;
  root.setAttribute("data-tab", tab);
  for (const button of buttons) {
    const selected = button.dataset.reiter === tab;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  }
  const panel = document.getElementById(tab);
  if (changed && previous) {
    panel.classList.remove("ist-neu");
    void panel.offsetWidth;
    panel.classList.add("ist-neu");
  }
  if (scrollTo) {
    scrollTo.scrollIntoView({ block: "start" });
  } else if (changed && previous) {
    window.scrollTo(0, scrollByTab.get(tab) ?? 0);
  }
  if (focusPanel) panel.focus({ preventScroll: true });
  if (previous && previous !== tab) notifyModule(previous, false);
  notifyModule(tab, true);
}

/** Apply the current hash: a tab name, an id inside a tab, or nothing. */
function applyHash({ focusPanel = false } = {}) {
  const id = decodeURIComponent(location.hash.slice(1));
  const tab = tabForId(id) ?? DEFAULT_TAB;
  const target = id && !TABS.includes(id) ? document.getElementById(id) : null;
  activate(tab, { focusPanel, scrollTo: target });
}

/** Switch tab from the tab bar and record it in the browser history. */
function selectFromBar(tab, { focus = false } = {}) {
  if (tab !== current) history.pushState(null, "", `#${tab}`);
  activate(tab);
  if (focus) buttons.find((button) => button.dataset.reiter === tab)?.focus();
}

function onTabKey(event) {
  const index = buttons.indexOf(event.currentTarget);
  const moves = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: buttons.length - 1 - index };
  if (!(event.key in moves)) return;
  event.preventDefault();
  const next = (index + moves[event.key] + buttons.length) % buttons.length;
  selectFromBar(buttons[next].dataset.reiter, { focus: true });
}

/** In-page links to a tab or to an id inside another tab switch the tab instead of jumping. */
function onDocumentClick(event) {
  const link = event.target.closest("a[href^='#']");
  if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey) return;
  const id = decodeURIComponent(link.getAttribute("href").slice(1));
  const tab = tabForId(id);
  if (!tab) return;
  event.preventDefault();
  history.pushState(null, "", `#${id}`);
  const target = TABS.includes(id) ? null : document.getElementById(id);
  activate(tab, { focusPanel: TABS.includes(id), scrollTo: target });
  if (TABS.includes(id)) window.scrollTo(0, 0);
}

for (const button of buttons) {
  button.addEventListener("click", () => selectFromBar(button.dataset.reiter));
  button.addEventListener("keydown", onTabKey);
}
document.addEventListener("click", onDocumentClick);
window.addEventListener("hashchange", () => applyHash());
document.addEventListener("visibilitychange", () => {
  if (current) notifyModule(current, document.visibilityState === "visible");
});

applyHash();
