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
  ];

  function pintarMetricas(metricas) {
    var panel = document.getElementById("entrenamiento-metricas-panel");
    var grid = document.getElementById("entrenamiento-metricas-grid");
    if (!panel || !grid || !metricas) return;

    grid.innerHTML = "";
    METRICAS.forEach(function (fila) {
      var clave = fila[0], etiqueta = fila[1], formatear = fila[2];
      if (metricas[clave] === undefined || metricas[clave] === null) return;

      var celda = document.createElement("div");
      celda.className = "metric";
      var valor = document.createElement("span");
      valor.className = "metric__valor numerico";
      valor.textContent = formatear(metricas[clave]);
      var etq = document.createElement("span");
      etq.className = "metric__etiqueta";
      etq.textContent = etiqueta;
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
      if (detalle) detalle.textContent = "Ejecutando el entrenamiento existente. Esto puede tardar unos segundos.";

      try {
        var respuesta = await fetch("/api/entrenamiento", {
          method: "POST",
          credentials: "same-origin",
        });
        var datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(datos.detail || "Error durante el entrenamiento.");

        badge.textContent = "Entrenamiento completado";
        badge.className = "status status--dominado";
        if (detalle) detalle.textContent = "Modelo reentrenado y guardado en ml/artefactos/.";
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
