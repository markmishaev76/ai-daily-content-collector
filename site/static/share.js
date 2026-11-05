// Brief pages: copy the day's LinkedIn text (the <pre> in .share-text) to the clipboard.
(function () {
  var button = document.querySelector(".copy-share");
  var pre = document.querySelector(".share-text pre");
  var status = document.querySelector(".share-status");
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
