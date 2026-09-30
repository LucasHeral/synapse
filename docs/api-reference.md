# 📄 Spécification OpenAPI & Swagger API Interactive

Explorez et testez la documentation interactive des endpoints REST de l'API **SYNAPSE**.

---

<link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<style>
  .swagger-ui {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 16px;
  }
</style>

<div id="swagger-ui"></div>

<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  document.addEventListener("DOMContentLoaded", function() {
    if (typeof SwaggerUIBundle !== "undefined") {
      SwaggerUIBundle({
        url: "../openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis
        ]
      });
    }
  });
</script>
