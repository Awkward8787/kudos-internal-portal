(function () {
  var field = document.getElementById("message");
  var count = document.getElementById("char-count");
  if (!field || !count) return;
  function update() {
    count.textContent = String(field.value.length);
  }
  field.addEventListener("input", update);
  update();
})();
