// placeholder until the runtime milestone lands: the runtime script
window.explorable = (function () {
  const noop = function () {};
  return {
    ready: noop, onChange: noop, values: function () { return {}; }, defaults: function () { return {}; },
    show: noop, chart: noop, diagram: noop, timeline: noop,
    threshold: function () { return null; }, expect: noop,
    theme: function () { return {}; }, onTheme: noop
  };
})();
