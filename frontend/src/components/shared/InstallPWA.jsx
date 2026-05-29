import React, { useEffect, useState } from "react";
import { DownloadSimple, X } from "@phosphor-icons/react";
import { onInstallPromptChange, triggerInstallPrompt, isStandalone } from "../../lib/pwa";

const DISMISS_KEY = "kt_pwa_install_dismissed_at";
const DISMISS_TTL_MS = 1000 * 60 * 60 * 24 * 7; // 7 days

export default function InstallPWA() {
  const [available, setAvailable] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (isStandalone()) return undefined;
    try {
      const ts = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
      if (ts && Date.now() - ts < DISMISS_TTL_MS) setDismissed(true);
    } catch (e) { /* noop */ }
    return onInstallPromptChange((p) => setAvailable(!!p));
  }, []);

  if (!available || dismissed) return null;

  const handleInstall = async () => {
    const res = await triggerInstallPrompt();
    if (res?.outcome !== "accepted") {
      try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (e) {}
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (e) {}
  };

  return (
    <div
      className="fixed bottom-4 right-4 z-50 max-w-xs flex items-center gap-3 px-3 py-2.5 rounded-lg shadow-lg border border-[var(--k-border)] bg-[var(--k-bg-elev)] text-foreground"
      role="dialog"
      aria-label="Install Kautilya AI"
    >
      <button
        onClick={handleInstall}
        className="flex items-center gap-2 text-sm font-medium px-3 py-1.5 rounded-md bg-[var(--k-brand)] text-white hover:opacity-90 transition"
      >
        <DownloadSimple weight="bold" className="w-4 h-4" />
        Install app
      </button>
      <button
        onClick={handleDismiss}
        className="text-muted-foreground hover:text-foreground"
        aria-label="Dismiss"
      >
        <X weight="bold" className="w-4 h-4" />
      </button>
    </div>
  );
}
