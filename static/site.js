// Liberty Freedom Gun: tiny page helpers
(function () {
  // Show today's date in the masthead.
  var today = document.querySelector("[data-today]");
  if (today) {
    try {
      today.textContent = new Date().toLocaleDateString("en-US", {
        weekday: "long", year: "numeric", month: "long", day: "numeric"
      });
    } catch (e) { /* keep the built-in date */ }
  }

  // Breaking news ticker. Scrolls with JavaScript so it works in every
  // browser. Hover over it, or tab into it, to pause.
  var track = document.querySelector(".ticker-track");
  var mover = document.querySelector(".ticker-move");
  if (track && mover && mover.firstElementChild) {
    var speed = 70; // pixels per second
    var x = 0;
    var last = null;
    var paused = false;
    var pause = function () { paused = true; };
    var play = function () { paused = false; };
    track.addEventListener("mouseenter", pause);
    track.addEventListener("mouseleave", play);
    track.addEventListener("focusin", pause);
    track.addEventListener("focusout", play);
    var step = function (now) {
      if (last !== null && !paused) {
        var seconds = Math.min((now - last) / 1000, 0.1);
        var loop = mover.firstElementChild.offsetWidth;
        x -= speed * seconds;
        if (loop > 0 && -x >= loop) x += loop;
        mover.style.transform = "translate3d(" + x + "px, 0, 0)";
      }
      last = now;
      window.requestAnimationFrame(step);
    };
    window.requestAnimationFrame(step);
  }

  // Share button on story pages.
  var button = document.querySelector("[data-share]");
  if (!button) return;
  var status = document.querySelector("[data-share-status]");
  var url = location.href.split("#")[0];

  function say(text) {
    if (!status) return;
    status.textContent = text;
    clearTimeout(say.timer);
    say.timer = setTimeout(function () { status.textContent = ""; }, 3000);
  }

  // Phones get the normal share sheet (Messages, WhatsApp, and so on).
  if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
    button.textContent = "Share this story";
    button.addEventListener("click", function () {
      navigator.share({ title: document.title, url: url }).catch(function () {});
    });
    return;
  }

  function oldSchoolCopy() {
    var box = document.createElement("textarea");
    box.value = url;
    box.setAttribute("readonly", "");
    box.style.position = "absolute";
    box.style.left = "-9999px";
    document.body.appendChild(box);
    box.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(box);
    say(ok ? "Link copied" : "Copy this link: " + url);
  }

  button.addEventListener("click", function () {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(function () { say("Link copied"); }, oldSchoolCopy);
    } else {
      oldSchoolCopy();
    }
  });
})();
