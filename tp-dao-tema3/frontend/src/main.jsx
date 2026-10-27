// Punto de entrada del front: monta la App en el <div id="root"> de index.html.
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App.jsx";
import "@fontsource-variable/nunito-sans";
import "./estilos.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
