(() => {
  const selects = document.querySelectorAll(".js-lang-switch");
  if (!selects.length) return;

  const currentUrl = () =>
    `${window.location.pathname}${window.location.search}${window.location.hash}`;

  selects.forEach((select) => {
    select.addEventListener("change", () => {
      const code = select.value;
      const template = select.dataset.langUrl;
      if (!code || !template) return;
      const next = encodeURIComponent(currentUrl());
      const url = `${template.replace("__code__", code)}?next=${next}`;
      window.location.href = url;
    });
  });
})();
