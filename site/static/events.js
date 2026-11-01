// Events page filter chips: show only rows whose data-cats has the chosen category.
(function () {
  var bar = document.querySelector(".event-filters");
  if (!bar) return;
  var buttons = bar.querySelectorAll("button[data-filter]");
  var rows = document.querySelectorAll(".event-row[data-cats]");

  function apply(filter) {
    rows.forEach(function (row) {
      var cats = (row.getAttribute("data-cats") || "").split(" ");
      row.hidden = filter !== "all" && cats.indexOf(filter) === -1;
    });
    buttons.forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-filter") === filter ? "true" : "false");
    });
  }

  buttons.forEach(function (b) {
    b.addEventListener("click", function () { apply(b.getAttribute("data-filter")); });
  });
  bar.hidden = false;
})();
