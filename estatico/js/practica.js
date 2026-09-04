
(function () {
  "use strict";

  function iniciarCronometro() {
    var etiqueta = document.getElementById("cronometro");
    var campoTiempo = document.getElementById("tiempo_respuesta_ms");
    var formulario = document.getElementById("formulario-respuesta");
    if (!etiqueta || !campoTiempo || !formulario) return;

    var inicio = Date.now();

    function formatear(segundosTotales) {
      var m = Math.floor(segundosTotales / 60);
      var s = segundosTotales % 60;
      return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    var intervalo = window.setInterval(function () {
      etiqueta.textContent = formatear(Math.floor((Date.now() - inicio) / 1000));
    }, 1000);

    formulario.addEventListener("submit", function () {
      campoTiempo.value = String(Date.now() - inicio);
      window.clearInterval(intervalo);
    });
  }

  function inicializarParsons() {
    var lista = document.getElementById("parsons-lista");
    var campoRespuesta = document.getElementById("respuesta");
    if (!lista || !campoRespuesta) return;

    function actualizarRespuesta() {
      var fragmentos = lista.querySelectorAll(".parsons__fragmento");
      var indices = Array.prototype.map.call(fragmentos, function (el) {
        return el.getAttribute("data-indice");
      });
      campoRespuesta.value = "[" + indices.join(",") + "]";

      Array.prototype.forEach.call(fragmentos, function (el, posicion) {
        var etiquetaPosicion = el.querySelector(".parsons__posicion");
        if (etiquetaPosicion) {
          var numero = posicion + 1;
          etiquetaPosicion.textContent = (numero < 10 ? "0" : "") + numero;
        }
      });
    }

    var elementoArrastrado = null;

    function moverSegunPosicion(arrastrado, clienteX, clienteY) {
      var elementoDebajo = document.elementFromPoint(clienteX, clienteY);
      var sobre = elementoDebajo && elementoDebajo.closest(".parsons__fragmento");
      if (!sobre || sobre === arrastrado) return;
      var rectangulo = sobre.getBoundingClientRect();
      var mitad = rectangulo.top + rectangulo.height / 2;
      if (clienteY < mitad) {
        lista.insertBefore(arrastrado, sobre);
      } else {
        lista.insertBefore(arrastrado, sobre.nextSibling);
      }
    }

    lista.addEventListener("dragstart", function (evento) {
      var fragmento = evento.target.closest(".parsons__fragmento");
      if (!fragmento) return;
      elementoArrastrado = fragmento;
      fragmento.classList.add("parsons__fragmento--arrastrando");
    });

    lista.addEventListener("dragend", function (evento) {
      var fragmento = evento.target.closest(".parsons__fragmento");
      if (fragmento) fragmento.classList.remove("parsons__fragmento--arrastrando");
      elementoArrastrado = null;
      actualizarRespuesta();
    });

    lista.addEventListener("dragover", function (evento) {
      evento.preventDefault();
      if (!elementoArrastrado) return;
      moverSegunPosicion(elementoArrastrado, evento.clientX, evento.clientY);
    });

   
    var tocado = null;

    lista.addEventListener("touchstart", function (evento) {
      if (evento.target.closest(".parsons__mover")) return;
      var fragmento = evento.target.closest(".parsons__fragmento");
      if (!fragmento) return;
      tocado = fragmento;
      fragmento.classList.add("parsons__fragmento--arrastrando");
    }, { passive: true });

    lista.addEventListener("touchmove", function (evento) {
      if (!tocado) return;
      evento.preventDefault();
      var toque = evento.touches[0];
      moverSegunPosicion(tocado, toque.clientX, toque.clientY);
    }, { passive: false });

    function soltarToque() {
      if (!tocado) return;
      tocado.classList.remove("parsons__fragmento--arrastrando");
      tocado = null;
      actualizarRespuesta();
    }

    lista.addEventListener("touchend", soltarToque);
    lista.addEventListener("touchcancel", soltarToque);

    lista.addEventListener("click", function (evento) {
      var boton = evento.target.closest(".parsons__mover");
      if (!boton) return;
      var fragmento = boton.closest(".parsons__fragmento");
      var direccion = boton.getAttribute("data-direccion");
      if (direccion === "arriba" && fragmento.previousElementSibling) {
        lista.insertBefore(fragmento, fragmento.previousElementSibling);
      } else if (direccion === "abajo" && fragmento.nextElementSibling) {
        lista.insertBefore(fragmento.nextElementSibling, fragmento);
      }
      fragmento.focus();
      actualizarRespuesta();
    });

    actualizarRespuesta();
  }

  document.addEventListener("DOMContentLoaded", function () {
    iniciarCronometro();
    inicializarParsons();
  });
})();
