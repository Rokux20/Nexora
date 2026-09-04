(function () {
  "use strict";

  var NOMBRES_CONCEPTO = [
    "Variables y tipos de datos", "Entrada y salida básica", "Operadores y expresiones",
    "Estructuras condicionales", "Bucle while", "Bucle for", "Listas", "Cadenas de texto",
    "Diccionarios", "Funciones", "Manejo de excepciones", "Integración",
  ];
  var NUM_CONCEPTOS = NOMBRES_CONCEPTO.length;
  var ETIQUETAS_ESTADO = { pendiente: "Pendiente", en_curso: "En progreso", dominado: "Dominado" };

  function fijarRelleno(elemento, porcentajeEntero) {
    if (elemento) elemento.style.transform = "scaleX(" + (porcentajeEntero / 100) + ")";
  }

  function obtenerEstado() {
    return fetch("/api/estado", { credentials: "same-origin" })
      .then(function (resp) { return resp.ok ? resp.json() : null; })
      .catch(function () { return null; });
  }

  function porConcepto(estados) {
    var mapa = {};
    (estados || []).forEach(function (e) { mapa[e.concepto_id] = e; });
    return mapa;
  }

  function conceptoActualDe(mapa) {
    for (var c = 1; c <= NUM_CONCEPTOS; c++) {
      if (!mapa[c] || mapa[c].estado !== "dominado") {
        return mapa[c] || { concepto_id: c, estado: "pendiente", p_dominio_previo: null };
      }
    }
    return mapa[NUM_CONCEPTOS] || null;
  }

  function pintarTrayectoria(mapa, actualId) {
    var pista = document.getElementById("trayectoria-pista");
    if (pista) {
      pista.innerHTML = "";
      for (var c = 1; c <= NUM_CONCEPTOS; c++) {
        var estado = mapa[c] ? mapa[c].estado : "pendiente";

        var nodo = document.createElement("div");
        nodo.className = "trajectory__nodo" + (c === actualId ? " trajectory__nodo--actual" : "");

        var hex = document.createElement("div");
        hex.className = "hex hex--sm hex--" + estado + (c === actualId ? " hex--actual" : "");
        hex.textContent = estado === "dominado" ? "✓" : String(c);
        hex.title = NOMBRES_CONCEPTO[c - 1] + " — " + (ETIQUETAS_ESTADO[estado] || estado);

        var nombre = document.createElement("span");
        nombre.className = "trajectory__nombre";
        nombre.textContent = NOMBRES_CONCEPTO[c - 1];

        nodo.appendChild(hex);
        nodo.appendChild(nombre);
        pista.appendChild(nodo);

        if (c < NUM_CONCEPTOS) {
          var linea = document.createElement("div");
          linea.className = "trajectory__linea" + (estado === "dominado" ? " trajectory__linea--activa" : "");
          pista.appendChild(linea);
        }
      }
    }
  }

  function pintarMapaConceptos(mapa, actualId) {
    var contenedor = document.getElementById("mapa-conceptos");
    if (!contenedor) return;
    contenedor.innerHTML = "";
    for (var c = 1; c <= NUM_CONCEPTOS; c++) {
      var estado = mapa[c] ? mapa[c].estado : "pendiente";
      var dominio = mapa[c] && mapa[c].p_dominio_previo != null ? mapa[c].p_dominio_previo : null;

      var item = document.createElement("div");
      item.className = "concept-map__item" + (c === actualId ? " concept-map__item--actual" : "");

      var hex = document.createElement("div");
      hex.className = "hex hex--" + estado + (c === actualId ? " hex--actual" : "");
      hex.textContent = estado === "dominado" ? "✓" : String(c);

      var nombre = document.createElement("span");
      nombre.className = "concept-map__nombre";
      nombre.textContent = NOMBRES_CONCEPTO[c - 1];

      var estadoContenedor = document.createElement("span");
      estadoContenedor.className = "concept-map__estado";

      var etiquetaEstado = document.createElement("span");
      etiquetaEstado.className = "concept-map__label";
      etiquetaEstado.textContent = ETIQUETAS_ESTADO[estado] || estado;
      estadoContenedor.appendChild(etiquetaEstado);

      if (dominio != null) {
        var dominioSpan = document.createElement("span");
        dominioSpan.className = "concept-map__dominio";
        dominioSpan.textContent = Math.round(dominio * 100) + "%";
        estadoContenedor.insertBefore(dominioSpan, etiquetaEstado);
      }

      item.appendChild(hex);
      item.appendChild(nombre);
      item.appendChild(estadoContenedor);
      contenedor.appendChild(item);
    }
  }

  function pintarResumenYBarra(dominados) {
    var resumen = document.getElementById("trayectoria-resumen");
    if (resumen) resumen.textContent = dominados + " de " + NUM_CONCEPTOS + " conceptos dominados";
    var barra = document.getElementById("trayectoria-barra");
    fijarRelleno(barra, Math.round((dominados / NUM_CONCEPTOS) * 100));
  }

  function pintarPanelAdaptativo(mapa, actual) {
    var elValor = document.getElementById("panel-dominio-valor");
    var elBarra = document.getElementById("panel-dominio-barra");
    var elBadge = document.getElementById("panel-estado-badge");
    var elConcepto = document.getElementById("panel-concepto-nombre");
    if (!elValor && !elBadge && !elConcepto) return;

    var dominio = actual && actual.p_dominio_previo != null ? actual.p_dominio_previo : null;
    var estadoTexto = actual ? actual.estado : "pendiente";

    if (elValor) elValor.textContent = dominio != null ? Math.round(dominio * 100) + "%" : "—";
    fijarRelleno(elBarra, dominio != null ? Math.round(dominio * 100) : 0);
    if (elBadge) {
      elBadge.textContent = ETIQUETAS_ESTADO[estadoTexto] || estadoTexto;
      elBadge.className = "status status--" + estadoTexto;
    }
    if (elConcepto && actual) elConcepto.textContent = NOMBRES_CONCEPTO[actual.concepto_id - 1] || ("Concepto " + actual.concepto_id);
  }

  function pintarProgresoGeneral(mapa) {
    var elPorcentaje = document.getElementById("progreso-general-porcentaje");
    var elBarra = document.getElementById("progreso-general-barra");
    if (!elPorcentaje && !elBarra) return;

    var dominados = 0, enCurso = 0, pendientes = 0;
    for (var c = 1; c <= NUM_CONCEPTOS; c++) {
      var estado = mapa[c] ? mapa[c].estado : "pendiente";
      if (estado === "dominado") dominados++;
      else if (estado === "en_curso") enCurso++;
      else pendientes++;
    }
    var porcentaje = Math.round((dominados / NUM_CONCEPTOS) * 100);

    if (elPorcentaje) elPorcentaje.textContent = porcentaje + "%";
    fijarRelleno(elBarra, porcentaje);
    var elDominados = document.getElementById("progreso-general-dominados");
    var elEnCurso = document.getElementById("progreso-general-encurso");
    var elPendientes = document.getElementById("progreso-general-pendientes");
    if (elDominados) elDominados.textContent = dominados + " de " + NUM_CONCEPTOS + " conceptos dominados";
    if (elEnCurso) elEnCurso.textContent = enCurso + " en progreso";
    if (elPendientes) elPendientes.textContent = pendientes + " pendientes";
  }


  function intentar(fn) {
    try { fn(); } catch (error) { /* un bloque falla sin arrastrar al resto */ }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var necesitaEstado = document.getElementById("trayectoria-pista") ||
      document.getElementById("mapa-conceptos") ||
      document.getElementById("panel-dominio-valor") ||
      document.getElementById("progreso-general-porcentaje");
    if (!necesitaEstado) return;

    obtenerEstado().then(function (datos) {
      var estados = datos ? datos.estados : [];
      var mapa = porConcepto(estados);
      var actual = conceptoActualDe(mapa);
      var actualId = actual ? actual.concepto_id : null;
      var dominados = 0;
      for (var c = 1; c <= NUM_CONCEPTOS; c++) {
        if (mapa[c] && mapa[c].estado === "dominado") dominados++;
      }

      intentar(function () { pintarTrayectoria(mapa, actualId); });
      intentar(function () { pintarMapaConceptos(mapa, actualId); });
      intentar(function () { pintarResumenYBarra(dominados); });
      intentar(function () { pintarPanelAdaptativo(mapa, actual); });
      intentar(function () { pintarProgresoGeneral(mapa); });
    });
  });
})();
