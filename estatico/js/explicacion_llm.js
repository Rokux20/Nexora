/* Solicita teoría generada por Ollama. El navegador nunca envía dominio,
 * nivel ni texto de prompt: solo el identificador del concepto visible. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var boton = document.getElementById("solicitar-explicacion");
    var panel = document.querySelector(".explanation[data-concepto-id]");
    var estado = document.getElementById("explicacion-llm-estado");
    var destino = document.getElementById("explicacion-llm");
    if (!boton || !panel || !estado || !destino) return;

    boton.addEventListener("click", async function () {
      var conceptoId = Number(panel.dataset.conceptoId);
      if (!Number.isInteger(conceptoId) || conceptoId < 1) return;

      boton.disabled = true;
      estado.textContent = "Generando explicación con el tutor local…";
      destino.hidden = true;
      try {
        var respuesta = await fetch("/api/explicacion", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ concepto_id: conceptoId }),
        });
        var datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(datos.detail || "No fue posible generar la explicación.");
        destino.textContent = datos.explicacion;
        destino.hidden = false;
        estado.textContent = "Explicación adaptada a tu estado actual.";
      } catch (error) {
        estado.textContent = error.message || "El servicio local no está disponible.";
      } finally {
        boton.disabled = false;
      }
    });
  });
})();
