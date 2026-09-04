/* estado_vivo.js — mejora progresiva de frontend: consume el endpoint
 * JSON YA EXISTENTE `/api/estado` (no se modificó ningún archivo de
 * backend) para poblar, en practica.html, el stepper de trayectoria y
 * el panel adaptativo (dominio estimado + estado del concepto actual).
 * Si la petición falla o no hay datos todavía, cada bloque cae a un
 * estado neutro — nunca deja un hueco roto.
 *
 * Nota de datos (ver informe de diagnóstico): /api/estado no expone el
 * nombre real de cada concepto, solo `concepto_id`. Por eso el stepper
 * muestra el número de concepto en vez de su nombre — no es un valor
 * inventado, es el dato real disponible sin tocar el backend.
 */
(function () {
  "use strict";

  var NUM_CONCEPTOS = 12;

  function obtenerEstado() {
    return fetch("/api/estado", { credentials: "same-origin" })
      .then(function (resp) {
        if (!resp.ok) return null;
        return resp.json();
      })
      .catch(function () {
        return null;
      });
  }

  function porConcepto(estados) {
    var mapa = {};
    (estados || []).forEach(function (e) {
      mapa[e.concepto_id] = e;
    });
    return mapa;
  }

  function conceptoActualDe(estados) {
    var mapa = porConcepto(estados);
    for (var c = 1; c <= NUM_CONCEPTOS; c++) {
      if (!mapa[c] || mapa[c].estado !== "dominado") {
        return mapa[c] || { concepto_id: c, estado: "pendiente", p_dominio_previo: null };
      }
    }
    return mapa[NUM_CONCEPTOS] || null;
  }

  function pintarStepper(estados) {
    var contenedor = document.getElementById("stepper-trayectoria");
    if (!contenedor) return;

    var mapa = porConcepto(estados);
    var actual = conceptoActualDe(estados);
    var idActual = actual ? actual.concepto_id : null;
    var dominados = 0;

    contenedor.innerHTML = "";
    for (var c = 1; c <= NUM_CONCEPTOS; c++) {
      var estado = mapa[c];
      var estadoTexto = estado ? estado.estado : "pendiente";
      if (estadoTexto === "dominado") dominados++;

      var nodo = document.createElement("div");
      nodo.className = "stepper__nodo stepper__nodo--" + estadoTexto;
      if (c === idActual) nodo.classList.add("stepper__nodo--actual");

      var circulo = document.createElement("span");
      circulo.className = "stepper__circulo";
      circulo.textContent = estadoTexto === "dominado" ? "✓" : String(c);

      var nombre = document.createElement("span");
      nombre.className = "stepper__nombre";
      nombre.textContent = "Concepto " + c;

      nodo.title = "Concepto " + c + ": " + estadoTexto.replace("_", " ");
      nodo.appendChild(circulo);
      nodo.appendChild(nombre);
      contenedor.appendChild(nodo);

      if (c < NUM_CONCEPTOS) {
        var linea = document.createElement("div");
        linea.className = "stepper__linea" + (estadoTexto === "dominado" ? " stepper__linea--activa" : "");
        contenedor.appendChild(linea);
      }
    }

    var resumen = document.getElementById("trayectoria-resumen");
    if (resumen) resumen.textContent = dominados + " de " + NUM_CONCEPTOS + " conceptos dominados";
    var barra = document.getElementById("trayectoria-barra");
    if (barra) barra.style.width = Math.round((dominados / NUM_CONCEPTOS) * 100) + "%";
  }

  function pintarPanelAdaptativo(estados) {
    var elValor = document.getElementById("panel-dominio-valor");
    var elBarra = document.getElementById("panel-dominio-barra");
    var elBadge = document.getElementById("panel-estado-badge");
    if (!elValor && !elBadge) return;

    var actual = conceptoActualDe(estados || []);
    var dominio = actual && actual.p_dominio_previo != null ? actual.p_dominio_previo : null;

    if (elValor) elValor.textContent = dominio != null ? Math.round(dominio * 100) + "%" : "—";
    if (elBarra) elBarra.style.width = (dominio != null ? Math.round(dominio * 100) : 0) + "%";

    if (elBadge) {
      var estadoTexto = actual ? actual.estado : "pendiente";
      var etiquetas = { pendiente: "Pendiente", en_curso: "En progreso", dominado: "Dominado" };
      elBadge.textContent = etiquetas[estadoTexto] || estadoTexto;
      elBadge.className = "insignia insignia--" + estadoTexto;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    obtenerEstado().then(function (datos) {
      var estados = datos ? datos.estados : [];
      pintarStepper(estados);
      pintarPanelAdaptativo(estados);
    });
  });
})();
