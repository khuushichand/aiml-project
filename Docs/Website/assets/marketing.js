const yearTargets = document.querySelectorAll("[data-current-year]");
for (const target of yearTargets) {
  target.textContent = String(new Date().getFullYear());
}

for (const button of document.querySelectorAll("[data-copy-target]")) {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy-target");
    if (!targetId) return;

    const source = document.getElementById(targetId);
    if (!source) return;

    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(source.textContent ?? "");
      button.textContent = "Copied";
      button.classList.add("is-copied");
      window.setTimeout(() => {
        button.textContent = original;
        button.classList.remove("is-copied");
      }, 1600);
    } catch {
      button.textContent = "Copy failed";
      window.setTimeout(() => {
        button.textContent = original;
      }, 1600);
    }
  });
}
