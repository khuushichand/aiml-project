(function () {
  var Reveal = {};
  var currentIndex = 0;
  var slides = [];
  var settings = {};

  function collectSlides() {
    slides = Array.prototype.slice.call(document.querySelectorAll(".reveal .slides > section"));
  }

  function clamp(index) {
    if (index < 0) {
      return 0;
    }
    if (index >= slides.length) {
      return Math.max(0, slides.length - 1);
    }
    return index;
  }

  function updateHash() {
    if (!settings.hash) {
      return;
    }
    var target = "#/" + String(currentIndex + 1);
    if (window.location.hash !== target) {
      window.location.hash = target;
    }
  }

  function show(index) {
    if (!slides.length) {
      return;
    }
    currentIndex = clamp(index);
    slides.forEach(function (slide, idx) {
      if (idx === currentIndex) {
        slide.classList.add("active");
      } else {
        slide.classList.remove("active");
      }
    });
    updateHash();
  }

  function parseHash() {
    if (!settings.hash) {
      return;
    }
    var match = window.location.hash.match(/#\/(\d+)/);
    if (match) {
      var parsed = parseInt(match[1], 10);
      if (!isNaN(parsed)) {
        show(parsed - 1);
      }
    }
  }

  function handleKey(event) {
    switch (event.key) {
      case "ArrowRight":
      case "PageDown":
      case " ":
        show(currentIndex + 1);
        break;
      case "ArrowLeft":
      case "PageUp":
        show(currentIndex - 1);
        break;
      case "Home":
        show(0);
        break;
      case "End":
        show(slides.length - 1);
        break;
      default:
        break;
    }
  }

  Reveal.initialize = function (options) {
    settings = options || {};
    collectSlides();
    show(currentIndex);
    if (settings.hash) {
      parseHash();
      window.addEventListener("hashchange", parseHash);
    }
    document.addEventListener("keydown", handleKey);
  };

  Reveal.slide = function (index) {
    show(index);
  };

  window.Reveal = Reveal;
})();
