window.addEventListener("DOMContentLoaded", () => {
  window.SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    displayRequestDuration: true,
    persistAuthorization: false,
    presets: [window.SwaggerUIBundle.presets.apis],
    layout: "BaseLayout",
  });
});
