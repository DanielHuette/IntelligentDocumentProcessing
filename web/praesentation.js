/**
 * Self-running presentation in seven scenes with chapters and play/pause.
 *
 * Context: Loaded when the Präsentation tab opens for the first time. Scenes are HTML with CSS
 *          animations that start when a scene receives the class "spielt"; this module only
 *          decides which scene is on screen and for how long.
 * Input:   The tab panel with [data-film], its scenes ([data-szene]), chapter buttons and play button.
 * Output:  The active scene, chapter progress bars and the play state; once the last scene has
 *          played out, the Projekt tab. With reduced motion nothing plays or switches tabs by
 *          itself; chapters still switch scenes.
 */

const SCENE_MS = [6000, 6500, 6500, 6500, 7000, 6500, 9000];

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

export function start(panel) {
  const film = panel.querySelector("[data-film]");
  const scenes = [...film.querySelectorAll("[data-szene]")];
  const chapters = [...film.querySelectorAll("[data-kapitel]")];
  const playButton = film.querySelector("[data-film-abspiel]");
  const label = playButton.querySelector(".abspiel__text");
  const state = { index: 0, elapsed: 0, playing: false, visible: false, finished: false, last: 0, looping: false };

  function setProgress(index, value) {
    chapters[index].querySelector("i").style.setProperty("--fortschritt", String(value));
  }

  function setPlaying(playing) {
    state.playing = playing;
    film.classList.toggle("ist-pausiert", !playing);
    playButton.setAttribute("aria-pressed", String(playing));
    label.textContent = playing ? "Anhalten" : state.finished ? "Nochmal abspielen" : "Abspielen";
    ensureLoop();
  }

  function goTo(index) {
    state.index = index;
    state.elapsed = 0;
    state.finished = false;
    scenes.forEach((scene, i) => {
      const active = i === index;
      scene.classList.toggle("ist-aktiv", active);
      scene.classList.remove("spielt");
      scene.inert = !active;
      scene.setAttribute("aria-hidden", String(!active));
    });
    if (!reducedMotion.matches) {
      void scenes[index].offsetWidth;
      scenes[index].classList.add("spielt");
    }
    chapters.forEach((button, i) => {
      if (i === index) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
      setProgress(i, i < index ? 1 : 0);
    });
  }

  function tick(now) {
    if (!(state.playing && state.visible)) {
      state.looping = false;
      return;
    }
    state.elapsed += now - state.last;
    state.last = now;
    const duration = SCENE_MS[state.index];
    setProgress(state.index, Math.min(1, state.elapsed / duration));
    if (state.elapsed >= duration) {
      if (state.index < scenes.length - 1) {
        goTo(state.index + 1);
      } else if (openProject()) {
        state.looping = false;
        return;
      } else {
        state.finished = true;
        setPlaying(false);
      }
    }
    requestAnimationFrame(tick);
  }

  // A film that has played to the end hands over to the project tab through its tab button, so
  // address, history and tab bar follow; it waits on its first scene for the next visit.
  function openProject() {
    const tab = document.querySelector("[data-reiter='projekt']");
    if (!tab || reducedMotion.matches) return false;
    goTo(0);
    tab.click();
    return true;
  }

  function ensureLoop() {
    if (state.looping || !(state.playing && state.visible)) return;
    state.looping = true;
    state.last = performance.now();
    requestAnimationFrame(tick);
  }

  chapters.forEach((button, index) => {
    button.addEventListener("click", () => goTo(index));
  });

  playButton.addEventListener("click", () => {
    if (state.playing) {
      setPlaying(false);
      return;
    }
    if (state.finished) goTo(0);
    setPlaying(true);
  });

  goTo(0);
  setPlaying(!reducedMotion.matches);

  return {
    setVisible(visible) {
      state.visible = visible;
      film.classList.toggle("ist-pausiert", !(visible && state.playing));
      ensureLoop();
    },
  };
}
