// Week in review: copy the plain-text version (the <pre> in .week-text) to the clipboard.
(function () {
  var button = document.querySelector(".copy-week");
  var pre = document.querySelector(".week-text pre");
  var status = document.querySelector(".copy-status");
  if (!button || !pre || !navigator.clipboard) return;
  button.hidden = false;
  button.addEventListener("click", function () {
    navigator.clipboard.writeText(pre.textContent).then(function () {
      if (status) status.textContent = "Copied. Paste it into your post.";
    }, function () {
      if (status) status.textContent = "Couldn't copy; open the text below and copy it.";
    });
  });
})();
