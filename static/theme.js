(function () {
  "use strict";

  var storageKey = "studysprint-theme";

  function getTheme() {
    return document.documentElement.dataset.theme === "light" ? "light" : "dark";
  }

  function updateToggle(theme) {
    var toggle = document.getElementById("theme-toggle");
    if (!toggle) return;

    var isLight = theme === "light";
    toggle.setAttribute("aria-pressed", String(isLight));
    toggle.setAttribute("aria-label", isLight ? "Switch to dark theme" : "Switch to light theme");
    toggle.querySelector(".theme-toggle-label").textContent = isLight ? "Dark mode" : "Light mode";
    toggle.querySelector(".theme-toggle-icon").textContent = isLight ? "☾" : "☼";
  }

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    updateToggle(theme);
    try {
      localStorage.setItem(storageKey, theme);
    } catch (error) {
      // The theme still works for this page when storage is unavailable.
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    updateToggle(getTheme());
    var toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        setTheme(getTheme() === "light" ? "dark" : "light");
      });
    }
  });
}());
