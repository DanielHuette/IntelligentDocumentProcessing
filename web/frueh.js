/**
 * Pick the visible tab before the first paint.
 *
 * Context: Runs synchronously in the head, so a deep link such as #benchmarks never flashes
 *          the project tab first. app.js takes over once the page has loaded.
 * Input:   location.hash.
 * Output:  class "js" and data-tab on the html element.
 */
(function () {
  var tabs = ["projekt", "organigramm", "benchmarks", "praesentation"];
  var root = document.documentElement;
  var hash = location.hash.slice(1);
  root.classList.add("js");
  root.setAttribute("data-tab", tabs.indexOf(hash) >= 0 ? hash : "projekt");
})();
