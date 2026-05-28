import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { initFirebase } from "./lib/firebase.js";
import { registerPWA } from "./lib/pwa.js";

registerPWA();
// Synchronous — no network. Safe to call before render so getAuthInstance()
// returns a ready handle immediately from App's first effect.
initFirebase();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
