import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { initFirebase } from "./lib/firebase";

function Root() {
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    initFirebase().then(() => setInitialized(true));
  }, []);

  if (!initialized) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#050505] text-white font-medium">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-[var(--k-brand)] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm tracking-widest uppercase opacity-50">Initializing Kautilya...</p>
        </div>
      </div>
    );
  }

  return <App />;
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
