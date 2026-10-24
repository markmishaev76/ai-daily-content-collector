// Learn videos: nothing loads from YouTube but the thumbnail until a click swaps in the privacy-enhanced player.
(function () {
  var VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

  document.querySelectorAll(".player[data-video-id]").forEach(function (player) {
    var button = player.querySelector("button.play");
    var id = player.getAttribute("data-video-id");
    if (!button || !VIDEO_ID.test(id)) return;
    button.addEventListener("click", function () {
      var frame = document.createElement("iframe");
      frame.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1";
      frame.title = player.getAttribute("data-title") || "YouTube video";
      frame.allow = "autoplay; encrypted-media; picture-in-picture";
      frame.setAttribute("allowfullscreen", "");
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      player.replaceChildren(frame);
      frame.focus();
    });
  });
})();
