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
