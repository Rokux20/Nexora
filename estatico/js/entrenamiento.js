/* entrenamiento.js — dispara POST /api/entrenamiento y muestra el
 * resultado real que devuelve el backend. No entrena nada aquí */
(function () {
  "use strict";

  var METRICAS = [
    ["accuracy", "Accuracy", function (v) { return v.toFixed(2); }],
    ["precision", "Precision", function (v) { return v.toFixed(2); }],
    ["recall", "Recall", function (v) { return v.toFixed(2); }],
    ["f1", "F1", function (v) { return v.toFixed(2); }],
    ["roc_auc", "ROC-AUC", function (v) { return v.toFixed(3); }],
    ["tamano_train", "Registros de entrenamiento", function (v) { return String(v); }],
    ["tamano_validacion", "Registros de validación", function (v) { return String(v); }],
    ["regularizacion.c_elegido", "C elegido (validación cruzada)", function (v) { return String(v); }],
    ["sobreajuste.brecha", "Brecha AUC entrenamiento − validación", function (v) { return (v >= 0 ? "+" : "") + v.toFixed(3); }],
    ["semilla_datos", "Semilla de los datos", function (v) { return String(v); }],
  ];

  function leer(objeto, ruta) {
    return ruta.split(".").reduce(function (valor, clave) {
      return valor === undefined || valor === null ? undefined : valor[clave];
    }, objeto);
  }

  function pintarMetricas(metricas) {
    var panel = document.getElementById("entrenamiento-metricas-panel");
    var grid = document.getElementById("entrenamiento-metricas-grid");
    if (!panel || !grid || !metricas) return;

    grid.innerHTML = "";
    METRICAS.forEach(function (fila) {
      var clave = fila[0], etiqueta = fila[1], formatear = fila[2];
      var dato = leer(metricas, clave);
      if (dato === undefined || dato === null) return;

      var celda = document.createElement("div");
      celda.className = "metric";
      var valor = document.createElement("span");
      valor.className = "metric__valor numerico";
      valor.textContent = formatear(dato);
      var etq = document.createElement("span");
      etq.className = "metric__etiqueta";
      etq.textContent = etiqueta;
      if (clave === "sobreajuste.brecha" && metricas.sobreajuste.detectado) etq.textContent += " · sobreajuste";
      celda.appendChild(valor);
      celda.appendChild(etq);
      grid.appendChild(celda);
    });
    panel.hidden = false;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var boton = document.getElementById("boton-entrenar");
    var badge = document.getElementById("entrenamiento-estado-badge");
    var detalle = document.getElementById("entrenamiento-estado-detalle");
    var titulo = document.getElementById("entrenamiento-estado-titulo");
    if (!boton) return;

    boton.addEventListener("click", async function () {
      boton.disabled = true;
      badge.textContent = "Entrenando modelo...";
      badge.className = "status status--en_curso";
      if (detalle) detalle.textContent = "Simulando datos nuevos, eligiendo la regularización y entrenando. Tarda alrededor de un minuto.";

      try {
        var respuesta = await fetch("/api/entrenamiento", {
          method: "POST",
          credentials: "same-origin",
        });
        var datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(datos.detail || "Error durante el entrenamiento.");

        badge.textContent = "Entrenamiento completado";
        badge.className = "status status--dominado";
        if (detalle) detalle.textContent = "Modelo reentrenado con datos nuevos y guardado en ml/artefactos/. La práctica ya usa este modelo.";
        if (titulo) titulo.textContent = "Modelo entrenado";
        pintarMetricas(datos.metricas);
      } catch (error) {
        badge.textContent = "Error durante el entrenamiento";
        badge.className = "status status--incorrecto";
        if (detalle) detalle.textContent = error.message || "No fue posible completar el entrenamiento.";
      } finally {
        boton.disabled = false;
      }
    });
  });
})();
