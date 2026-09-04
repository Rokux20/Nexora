
(function () {
  "use strict";

  var CLAVE = "adaptivo-sidebar-oculto";

  function guardarEstado(oculto) {
    try {
      window.localStorage.setItem(CLAVE, oculto ? "1" : "0");
    } catch (error) {
      /* almacenamiento no disponible: el estado sigue activo en esta carga */
    }
  }

  function aplicarEstado(oculto) {
    document.body.classList.toggle("sidebar-oculto", oculto);
    var botonOcultar = document.getElementById("toggle-sidebar");
    if (botonOcultar) botonOcultar.setAttribute("aria-pressed", oculto ? "true" : "false");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var botonOcultar = document.getElementById("toggle-sidebar");
    var botonMostrar = document.getElementById("mostrar-sidebar");

    var oculto = false;
    try {
      oculto = window.localStorage.getItem(CLAVE) === "1";
    } catch (error) {
      /* almacenamiento no disponible: se asume la barra visible */
    }
    aplicarEstado(oculto);

    if (botonOcultar) {
      botonOcultar.addEventListener("click", function () {
        var nuevoOculto = !document.body.classList.contains("sidebar-oculto");
        aplicarEstado(nuevoOculto);
        guardarEstado(nuevoOculto);
      });
    }
    if (botonMostrar) {
      botonMostrar.addEventListener("click", function () {
        aplicarEstado(false);
        guardarEstado(false);
      });
    }
  });
})();
