/* tema.js — alterna claro/oscuro. */
(function () {
  "use strict";

  var CLAVE = "adaptivo-tema";

  function temaActual() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function sincronizarBoton(tema) {
    var boton = document.getElementById("boton-tema");
    if (!boton) return;
    var oscuro = tema === "dark";
    boton.setAttribute("aria-pressed", oscuro ? "true" : "false");
    var icono = boton.querySelector(".boton-tema__icono");
    var texto = boton.querySelector(".boton-tema__texto");
    if (icono) icono.textContent = oscuro ? "☾" : "☼";
    if (texto) texto.textContent = oscuro ? "Oscuro" : "Claro";
  }

  function aplicarTema(tema) {
    document.documentElement.setAttribute("data-theme", tema);
    try {
      window.localStorage.setItem(CLAVE, tema);
    } catch (error) {
      /* almacenamiento no disponible: el tema sigue activo en esta carga */
    }
    sincronizarBoton(tema);
  }

  document.addEventListener("DOMContentLoaded", function () {
    sincronizarBoton(temaActual());
    var boton = document.getElementById("boton-tema");
    if (!boton) return;
    boton.addEventListener("click", function () {
      aplicarTema(temaActual() === "dark" ? "light" : "dark");
    });
  });
})();
