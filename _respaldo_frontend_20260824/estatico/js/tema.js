/* tema.js — selector de tema claro/oscuro con persistencia en
 * localStorage. La aplicación INICIAL del tema (antes del primer pintado,
 * para evitar parpadeo) ocurre en un script bloqueante e inline dentro
 * de <head> en base.html; este archivo solo maneja el botón y su estado
 * visual una vez que el DOM está listo. */
(function () {
  "use strict";

  var CLAVE_ALMACENAMIENTO = "tema-prototipo";

  function temaActual() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function actualizarBoton(tema) {
    var boton = document.getElementById("boton-tema");
    if (!boton) return;
    var esOscuro = tema === "dark";
    boton.setAttribute("aria-pressed", esOscuro ? "true" : "false");
    boton.querySelector(".boton-tema__icono").textContent = esOscuro ? "🌙" : "☀️";
    boton.querySelector(".boton-tema__texto").textContent = esOscuro ? "Oscuro" : "Claro";
  }

  function aplicarTema(tema) {
    document.documentElement.setAttribute("data-theme", tema);
    try {
      window.localStorage.setItem(CLAVE_ALMACENAMIENTO, tema);
    } catch (e) {
      /* almacenamiento no disponible (modo privado, etc.): el tema sigue
       * funcionando para esta carga de página, solo no persiste. */
    }
    actualizarBoton(tema);
  }

  document.addEventListener("DOMContentLoaded", function () {
    actualizarBoton(temaActual());
    var boton = document.getElementById("boton-tema");
    if (!boton) return;
    boton.addEventListener("click", function () {
      aplicarTema(temaActual() === "dark" ? "light" : "dark");
    });
  });
})();
