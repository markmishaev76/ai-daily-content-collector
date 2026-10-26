// GitHub Pages serves 404.html for any unknown path; a /brief/YYYY-MM-DD/ path means the brief has aged out.
(function () {
  if (!/^\/brief\/\d{4}-\d{2}-\d{2}\/?$/.test(location.pathname)) return;
  var other = document.querySelector('[data-case="other"]');
  var brief = document.querySelector('[data-case="brief"]');
  if (!other || !brief) return;
  other.hidden = true;
  brief.hidden = false;
  document.title = "Brief not available · Mark Mishaev";
})();
