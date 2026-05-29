import { useState, useEffect, lazy, Suspense } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { getAuthInstance } from "./lib/firebase.js";
import { onAuthStateChanged, getRedirectResult } from "firebase/auth";

import InstallPWA from "./components/shared/InstallPWA";
import { getAuthHeaders } from "./lib/api";

// Lazy load route components
const ChatPage = lazy(() => import("./pages/ChatPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));

/* ── Age Gate + Consent Modal (first login, DPDP Act 2023) ─────────────── */
function ConsentModal({ user, onDone }) {
  const [marketing, setMarketing] = useState(true);
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (!ageConfirmed) { setError("Please confirm you are 18 or older to continue."); return; }
    setSubmitting(true);
    setError(null);
    try {
      const resp = await fetch('/api/user/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ age_confirmed: true, marketing_opt_in: marketing }),
      });
      if (!resp.ok) throw new Error('Failed to save consent');
      localStorage.setItem('kautilya_consent_done', '1');
      onDone();
    } catch (e) {
      setError('Could not save your preferences. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[10000] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#0f0f18] border border-[#2a2a3a] rounded-3xl shadow-2xl p-8">
        <div className="text-center mb-6">
          <div className="text-2xl font-bold text-[#FF6D3F] mb-1">Welcome to Kautilya AI</div>
          <div className="text-gray-400 text-sm">A few quick things before you start</div>
        </div>

        <div className="space-y-4 mb-6">
          {/* Age confirmation — mandatory */}
          <label className="flex items-start gap-3 cursor-pointer group">
            <div
              onClick={() => setAgeConfirmed(!ageConfirmed)}
              className={`mt-0.5 w-5 h-5 flex-shrink-0 rounded border-2 flex items-center justify-center transition-all cursor-pointer ${
                ageConfirmed ? 'bg-indigo-600 border-indigo-600' : 'border-[#3a3a50] group-hover:border-indigo-500'
              }`}
            >
              {ageConfirmed && (
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
                </svg>
              )}
            </div>
            <div onClick={() => setAgeConfirmed(!ageConfirmed)} className="text-sm text-gray-300 leading-snug">
              <strong className="text-white">I confirm I am 18 years of age or older.</strong>
              <span className="text-red-400 ml-1">*</span>
              <div className="text-xs text-gray-500 mt-0.5">Required — Kautilya AI is not available to minors under 18.</div>
            </div>
          </label>

          {/* Marketing emails — optional */}
          <label className="flex items-start gap-3 cursor-pointer group">
            <div
              onClick={() => setMarketing(!marketing)}
              className={`mt-0.5 w-5 h-5 flex-shrink-0 rounded border-2 flex items-center justify-center transition-all cursor-pointer ${
                marketing ? 'bg-indigo-600 border-indigo-600' : 'border-[#3a3a50] group-hover:border-indigo-500'
              }`}
            >
              {marketing && (
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
                </svg>
              )}
            </div>
            <div onClick={() => setMarketing(!marketing)} className="text-sm text-gray-300 leading-snug">
              Send me occasional emails about new features and tips. <span className="text-gray-500">(Optional)</span>
              <div className="text-xs text-gray-500 mt-0.5">You can unsubscribe any time from Account Settings.</div>
            </div>
          </label>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white font-semibold py-3.5 rounded-2xl transition-colors text-sm"
        >
          {submitting ? 'Saving…' : 'Continue to Kautilya AI'}
        </button>

        <p className="mt-4 text-center text-[10px] text-gray-600 leading-relaxed">
          By continuing you agree to our{" "}
          <a href="/terms" className="text-gray-500 hover:text-gray-400 underline">Terms</a>,{" "}
          <a href="/privacy" className="text-gray-500 hover:text-gray-400 underline">Privacy Policy</a>
          {" "}and{" "}
          <a href="/refund" className="text-gray-500 hover:text-gray-400 underline">Refund Policy</a>.
          Operated by Harsh Vardhan (RevealIQ, India).
        </p>
      </div>
    </div>
  );
}

/* ── Privacy Notice Banner (first visit) ────────────────────────────────── */
function PrivacyBanner() {
  const [visible, setVisible] = useState(() => {
    try { return !localStorage.getItem('kautilya_privacy_ack'); } catch { return false; }
  });
  if (!visible) return null;
  const accept = () => {
    try { localStorage.setItem('kautilya_privacy_ack', '1'); } catch {}
    setVisible(false);
  };
  return (
    <div className="fixed bottom-0 left-0 right-0 z-[9999] p-3 sm:p-4">
      <div className="max-w-3xl mx-auto bg-[#0f0f15] border border-[#2a2a3a] rounded-2xl shadow-2xl px-4 py-3 sm:px-6 sm:py-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <div className="flex-1 text-xs text-gray-400 leading-relaxed">
          We use cookies and store your chat history to deliver the service. By using Kautilya AI you confirm you are <strong className="text-white">18+ years old</strong> and agree to our{" "}
          <a href="/privacy" className="text-indigo-400 hover:underline">Privacy Policy</a>,{" "}
          <a href="/terms" className="text-indigo-400 hover:underline">Terms</a>, and{" "}
          <a href="/refund" className="text-indigo-400 hover:underline">Refund Policy</a>.
          {" "}Operated by <strong className="text-white">Harsh Vardhan</strong> (RevealIQ, India).
          Questions? <a href="mailto:hello@revealiq.in" className="text-indigo-400 hover:underline">hello@revealiq.in</a>
        </div>
        <button
          onClick={accept}
          className="flex-shrink-0 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-colors whitespace-nowrap"
        >
          I understand, continue
        </button>
      </div>
    </div>
  );
}

const LoadingScreen = () => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-[#020202] text-white">
    <div className="w-12 h-12 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
    <div className="text-sm text-gray-500 font-medium tracking-widest uppercase">Kautilya AI</div>
  </div>
);

// Browsers throttle setInterval in background tabs (often suspending it for
// minutes at a time). Firebase ID tokens expire at 60min, so we refresh at
// 50min via timer AND on every visibilitychange when the token is older than
// 50min — this is the case where the user reopens the tab after an hour and
// their first message would otherwise 401.
const TOKEN_REFRESH_BEFORE_EXPIRY_MS = 50 * 60 * 1000;
const TOKEN_STALE_THRESHOLD_MS = 50 * 60 * 1000;

const _readCachedUser = () => {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.uid) return null;
    // Only treat as logged-in if a token is still in storage. If the token
    // was wiped by an explicit logout, don't show a stale identity.
    if (!localStorage.getItem('firebase_token')) return null;
    return parsed;
  } catch { return null; }
};

function App() {
  const [theme, setTheme] = useState('dark');
  const cachedUser = _readCachedUser();
  const [user, setUser] = useState(cachedUser);
  const [loading, setLoading] = useState(!cachedUser);
  // Show consent modal for logged-in users who haven't confirmed age/consent yet
  const [showConsent, setShowConsent] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    const auth = getAuthInstance();
    if (!auth) {
      console.warn("[Auth] Firebase Auth instance is not initialized yet.");
      setLoading(false);
      return;
    }
    let refreshInterval = null;
    let currentAuthUser = null;

    const refreshToken = async (authUser, force = false) => {
      if (!authUser) return;
      try {
        const token = await authUser.getIdToken(force);
        localStorage.setItem('firebase_token', token);
        localStorage.setItem('firebase_token_issued_at', String(Date.now()));
      } catch (e) {
        console.warn('[Auth] Token refresh failed:', e);
      }
    };

    const refreshIfStale = async () => {
      if (!currentAuthUser) return;
      const issuedAt = parseInt(localStorage.getItem('firebase_token_issued_at') || '0', 10);
      const age = Date.now() - issuedAt;
      if (!issuedAt || age >= TOKEN_STALE_THRESHOLD_MS) {
        await refreshToken(currentAuthUser, true);
      }
    };

    // Refresh proactively whenever the user comes back to the tab. setInterval
    // alone is unreliable in background — this catches the "reopened after an
    // hour" case before the user's first action fails with 401.
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        refreshIfStale();
      }
    };
    const onFocus = () => refreshIfStale();
    const onOnline = () => refreshIfStale();
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', onFocus);
    window.addEventListener('online', onOnline);

    // BLANK-SCREEN FIX: On a Google redirect sign-in (mobile browsers,
    // Android WebView, some desktop flows), Firebase processes the OAuth
    // code AFTER the page loads. onAuthStateChanged fires BEFORE the
    // redirect result is consumed — it sees "null" first, sets loading=false,
    // and the user gets the login screen. They must manually refresh.
    //
    // Fix: resolve getRedirectResult FIRST, then register onAuthStateChanged.
    // If it was a redirect flow, the user is already set by the time the
    // listener fires, so it sees "logged in" on the very first emission.
    // If it was not a redirect (normal page load), getRedirectResult returns
    // null immediately and we fall straight through.
    let redirectHandled = false;
    const redirectPromise = getRedirectResult(auth)
      .then(async (result) => {
        if (result?.user) {
          console.log("[Auth] Redirect sign-in resolved:", result.user.email);
          redirectHandled = true;
          try {
            const token = await result.user.getIdToken();
            localStorage.setItem('firebase_token', token);
            localStorage.setItem('firebase_token_issued_at', String(Date.now()));
            localStorage.setItem('user', JSON.stringify({
              uid: result.user.uid,
              email: result.user.email,
              displayName: result.user.displayName,
              photoURL: result.user.photoURL,
            }));
          } catch (e) {
            console.warn('[Auth] Redirect token retrieval failed:', e);
          }
          // Fire welcome check for new users
          try {
            const { userAPI } = await import('./lib/api');
            userAPI.welcomeCheck().catch(() => {});
          } catch {}
        }
      })
      .catch((e) => console.warn("[Auth] Redirect sign-in error:", e));

    // Register the listener only after the redirect promise settles so the
    // first emission sees the post-redirect state.
    redirectPromise.finally(() => {
      const unsubscribe = onAuthStateChanged(auth, async (authUser) => {
        if (refreshInterval) clearInterval(refreshInterval);
        currentAuthUser = authUser;
        if (authUser) {
          try {
            const token = await authUser.getIdToken();
            localStorage.setItem('firebase_token', token);
            localStorage.setItem('firebase_token_issued_at', String(Date.now()));
            localStorage.setItem('user', JSON.stringify({
              uid: authUser.uid,
              email: authUser.email,
              displayName: authUser.displayName,
              photoURL: authUser.photoURL
            }));
            setUser(authUser);
            // Show age gate/consent modal for users who haven't confirmed yet
            if (!localStorage.getItem('kautilya_consent_done')) {
              setShowConsent(true);
            }
          } catch (e) {
            console.warn('[Auth] Initial token retrieval failed, using fallback:', e);
            setUser(authUser);
          }
          refreshInterval = setInterval(() => refreshToken(authUser, true), TOKEN_REFRESH_BEFORE_EXPIRY_MS);
        } else {
          localStorage.removeItem('firebase_token');
          localStorage.removeItem('firebase_token_issued_at');
          localStorage.removeItem('user');
          setUser(null);
        }
        setLoading(false);
      });

      // Store unsubscribe in the closure so the cleanup can reach it
      cleanupRef.current = unsubscribe;
    });

    // Dummy — real cleanup stored via redirectPromise.finally above
    const cleanupRef = { current: () => {} };

    return () => {
      cleanupRef.current?.();
      if (refreshInterval) clearInterval(refreshInterval);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('online', onOnline);
    };
  }, []);

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#020202] text-white">
        <div className="w-12 h-12 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
        <div className="text-sm text-gray-500 font-medium tracking-widest uppercase">Initializing Kautilya</div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <InstallPWA />
      {showConsent && user && <ConsentModal user={user} onDone={() => setShowConsent(false)} />}
      <PrivacyBanner />
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/login" element={!user ? <LoginPage /> : <Navigate to="/" />} />
          <Route path="/" element={user ? <ChatPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
          <Route path="/dashboard/*" element={user ? <DashboardPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/refund" element={<RefundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

/* ── Shared legal page shell ─────────────────────────────────────────────── */
function LegalShell({ title, subtitle, children }) {
  return (
    <div className="min-h-screen bg-[#07070a] text-[#f5f5f7] font-sans">
      {/* Minimal nav */}
      <div className="border-b border-[#1f2029] px-6 py-4 flex items-center justify-between max-w-5xl mx-auto">
        <a href="/" className="text-[#FF6D3F] font-bold text-lg tracking-tight">Kautilya AI</a>
        <div className="flex gap-4 text-xs text-gray-500">
          <a href="/privacy" className="hover:text-white transition-colors">Privacy</a>
          <a href="/terms" className="hover:text-white transition-colors">Terms</a>
          <a href="/refund" className="hover:text-white transition-colors">Refund Policy</a>
        </div>
      </div>
      {/* Content */}
      <div className="max-w-4xl mx-auto px-6 py-10 md:py-14">
        <div className="mb-10">
          <h1 className="text-3xl md:text-4xl font-bold text-white tracking-tight mb-2">{title}</h1>
          {subtitle && <p className="text-gray-400 text-sm">{subtitle}</p>}
        </div>
        <div className="space-y-10 text-sm text-gray-400 leading-relaxed">{children}</div>
      </div>
      {/* Footer */}
      <div className="border-t border-[#1f2029] mt-16 py-8 text-center text-xs text-gray-600">
        <div className="max-w-4xl mx-auto px-6 space-y-2">
          <div>
            Kautilya AI &mdash; operated by <strong className="text-gray-500">Harsh Vardhan</strong>, an independent developer based in India
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            <a href="/privacy" className="hover:text-gray-400 transition-colors">Privacy Policy</a>
            <span>&middot;</span>
            <a href="/terms" className="hover:text-gray-400 transition-colors">Terms of Service</a>
            <span>&middot;</span>
            <a href="/refund" className="hover:text-gray-400 transition-colors">Refund Policy</a>
            <span>&middot;</span>
            <a href="mailto:hello@revealiq.in" className="hover:text-gray-400 transition-colors">Contact</a>
          </div>
          <div>&copy; {new Date().getFullYear()} Kautilya AI by RevealIQ. All rights reserved.</div>
        </div>
      </div>
    </div>
  );
}

function LegalSection({ title, children }) {
  return (
    <section>
      <h2 className="text-base font-semibold text-white mb-3 pb-2 border-b border-[#1f2029]">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

/* ── Privacy Policy ─────────────────────────────────────────────────────── */
const PrivacyPage = () => {
  useEffect(() => { document.title = "Privacy Policy — Kautilya AI"; }, []);
  return (
    <LegalShell
      title="Privacy Policy"
      subtitle="Last updated: May 29, 2026 · Effective: May 29, 2026"
    >
      {/* Who we are */}
      <LegalSection title="1. Who We Are">
        <p>
          Kautilya AI is an AI assistant platform available at <strong className="text-white">ai.revealiq.in</strong> and as an Android application. It is operated by <strong className="text-white">Harsh Vardhan</strong>, an individual developer based in India, trading under the brand <strong className="text-white">RevealIQ</strong>.
        </p>
        <p>
          Harsh Vardhan is the <strong className="text-white">Data Fiduciary</strong> for all personal data collected through the platform under the Digital Personal Data Protection Act, 2023 (DPDP Act).
        </p>
        <div className="bg-[#0f0f15] border border-[#1f2029] rounded-xl p-4 text-xs space-y-1">
          <div><span className="text-gray-500">Operated by:</span> <span className="text-white">Harsh Vardhan (Individual Developer)</span></div>
          <div><span className="text-gray-500">Brand:</span> <span className="text-white">RevealIQ / Kautilya AI</span></div>
          <div><span className="text-gray-500">Country:</span> <span className="text-white">India</span></div>
          <div><span className="text-gray-500">Contact:</span> <a href="mailto:hello@revealiq.in" className="text-[#FF6D3F] hover:underline">hello@revealiq.in</a></div>
          <div><span className="text-gray-500">Grievance Officer:</span> <span className="text-white">Harsh Vardhan</span> · <a href="mailto:support@revealiq.in" className="text-[#FF6D3F] hover:underline">support@revealiq.in</a></div>
        </div>
      </LegalSection>

      {/* Data we collect */}
      <LegalSection title="2. Personal Data We Collect">
        <p>We collect only what is necessary to provide the service. Below is an itemised list as required under the DPDP Act 2023:</p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border border-[#1f2029] rounded-xl overflow-hidden">
            <thead>
              <tr className="bg-[#0f0f15] text-gray-300">
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Data Category</th>
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Specific Data</th>
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Purpose</th>
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Retention</th>
              </tr>
            </thead>
            <tbody className="text-gray-400">
              {[
                ["Account / Identity", "Name, email address, profile photo", "Account creation, personalisation, transactional emails", "Until account deletion + 5 years (CERT-In)"],
                ["User-generated content", "Chat messages, uploaded files, documents", "AI response generation, conversation history", "90 days after account deletion"],
                ["Voice / Audio", "Microphone input (only while voice mode is active)", "Voice-to-text for AI conversation, TTS playback", "Not retained — processed in real-time only"],
                ["Usage & analytics", "Page views, feature interactions, session duration", "Product improvement, abuse detection", "180 days"],
                ["Device / Technical", "IP address, browser type, device OS, Android ID", "Security, abuse prevention, CERT-In compliance", "180 days (ICT logs)"],
                ["Financial (Razorpay)", "Subscription status, payment reference ID", "Billing management (no card data stored)", "7 years (GST law)"],
                ["API usage", "API call timestamps, model used, token counts", "Rate limiting, billing, analytics", "90 days"],
                ["Integration credentials", "OAuth tokens for Google, GitHub (encrypted)", "Running your configured integrations", "Until revoked by user"],
                ["Communication preferences", "Marketing opt-in status, unsubscribe flag", "Ensuring legal email consent", "Until account deletion"],
              ].map(([cat, data, purpose, retention]) => (
                <tr key={cat} className="border-b border-[#1f2029] last:border-0">
                  <td className="px-3 py-2 font-medium text-white align-top">{cat}</td>
                  <td className="px-3 py-2 align-top">{data}</td>
                  <td className="px-3 py-2 align-top">{purpose}</td>
                  <td className="px-3 py-2 align-top">{retention}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-gray-500">We do not collect passwords (Google handles authentication), raw payment card details (Razorpay handles this), or biometric data for identification purposes.</p>
      </LegalSection>

      {/* Google API data */}
      <LegalSection title="3. Google API Services — User Data Policy">
        <p>
          Kautilya AI's use and transfer of information received from Google APIs to any other application adheres strictly to the{" "}
          <strong className="text-white">Google API Services User Data Policy</strong>, including the Limited Use requirements. Google user data is used only for the specific purpose described when you authorize the scope.
        </p>
        <div className="space-y-2 bg-[#0f0f15] border border-[#1f2029] rounded-xl p-4">
          {[
            ["calendar.events", "Book, view, and edit calendar events and Google Meet links on your behalf when using voice/chat agents."],
            ["spreadsheets", "Read lead data from your Sheets for outbound campaigns; write qualified leads back to specified sheets."],
            ["tasks", "Write follow-up action items to your Google Tasks after call transcriptions."],
            ["drive.readonly", "Read document summaries from your Drive to ground AI agent responses (RAG)."],
            ["gmail.send", "Send summary emails and notifications on your behalf after voice agent sessions."],
          ].map(([scope, desc]) => (
            <div key={scope} className="text-xs">
              <div className="text-indigo-400 font-mono mb-0.5">…/auth/{scope}</div>
              <div className="text-gray-400">{desc}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500">Google data is never used for advertising, never shared with third parties for their own purposes, never used to train AI models without explicit consent, and access is limited to the stated purposes only.</p>
      </LegalSection>

      {/* How we use data */}
      <LegalSection title="4. How We Use Your Data (Legal Basis)">
        <ul className="list-disc pl-5 space-y-2">
          <li><strong className="text-white">Contract performance:</strong> Providing the AI chat, voice, analytics, and developer API services you signed up for.</li>
          <li><strong className="text-white">Your consent:</strong> Sending marketing and re-engagement emails (you can withdraw any time from Account Settings).</li>
          <li><strong className="text-white">Legitimate interest:</strong> Security monitoring, abuse detection, rate limiting, and product analytics (we minimise data collected for these purposes).</li>
          <li><strong className="text-white">Legal obligation:</strong> Retaining logs for 180 days and subscriber records for 5 years as required by CERT-In Directions 2022; retaining billing records for 7 years under GST law.</li>
        </ul>
        <p>We <strong className="text-white">do not</strong> use your chat conversations or uploaded files to train or fine-tune AI models. We <strong className="text-white">do not</strong> sell, rent, or share your personal data with third parties for their own marketing or business purposes.</p>
      </LegalSection>

      {/* Third parties */}
      <LegalSection title="5. Third-Party Processors">
        <p>We share your data with the following processors only as necessary to deliver the service. Each processes data in their respective country:</p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border border-[#1f2029] rounded-xl overflow-hidden">
            <thead>
              <tr className="bg-[#0f0f15] text-gray-300">
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Processor</th>
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Country</th>
                <th className="text-left px-3 py-2 border-b border-[#1f2029]">Purpose</th>
              </tr>
            </thead>
            <tbody className="text-gray-400">
              {[
                ["Google Firebase / Firestore", "USA", "Authentication, database, cloud infrastructure"],
                ["HuggingFace Spaces", "USA", "Backend application hosting"],
                ["Anthropic / other LLM providers", "USA", "AI model inference (chat, reasoning)"],
                ["Resend", "USA", "Transactional email delivery"],
                ["Razorpay", "India", "Payment processing and subscription billing"],
                ["Vobiz / Exotel", "India", "Telephony and voice agent calls"],
                ["LiveKit", "USA/Cloud", "Real-time voice streaming"],
              ].map(([p, c, purpose]) => (
                <tr key={p} className="border-b border-[#1f2029] last:border-0">
                  <td className="px-3 py-2 font-medium text-white">{p}</td>
                  <td className="px-3 py-2">{c}</td>
                  <td className="px-3 py-2">{purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-gray-500">
          Several processors are based in the United States. Your data is transferred there as necessary to provide the service. These transfers are made on the basis of legitimate interest in providing you the service and contractual necessity, consistent with DPDP Act 2023 Rules on cross-border data flows.
        </p>
      </LegalSection>

      {/* Children */}
      <LegalSection title="6. Children's Privacy (Under 18)">
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-xs text-amber-300">
          <strong>Kautilya AI is intended for users aged 18 and above.</strong> We do not knowingly collect personal data from anyone under 18 years of age. If you are under 18, do not create an account or use this platform.
        </div>
        <p>If we become aware that a user is under 18, we will promptly delete their account and all associated personal data. If you believe a minor has created an account, please contact us at <a href="mailto:support@revealiq.in" className="text-[#FF6D3F] hover:underline">support@revealiq.in</a> and we will act within 7 business days.</p>
      </LegalSection>

      {/* Security */}
      <LegalSection title="7. Security Measures">
        <ul className="list-disc pl-5 space-y-2">
          <li>All data in transit is encrypted using TLS 1.2+.</li>
          <li>Firestore data is encrypted at rest by Google Cloud (AES-256).</li>
          <li>API keys are stored as SHA-256 hashes; the plaintext is shown once and never persisted.</li>
          <li>Firebase Auth tokens are validated on every API request — no endpoint is accessible without authentication.</li>
          <li>Content Security Policy (CSP), HSTS, X-Frame-Options, and other security headers are enforced on all responses.</li>
          <li>Webhook endpoints use constant-time HMAC comparison to prevent timing attacks.</li>
        </ul>
        <p className="text-xs text-gray-500">No system is 100% secure. In the event of a data breach, we will notify the Data Protection Board of India (DPBI) within 72 hours and affected users as soon as practicable.</p>
      </LegalSection>

      {/* Your rights */}
      <LegalSection title="8. Your Rights Under the DPDP Act 2023">
        <p>As a data principal, you have the following rights. We will respond within <strong className="text-white">7 business days</strong> of receiving a valid request:</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            ["Right to Access", "Request a summary of the personal data we hold about you and how we use it."],
            ["Right to Correction", "Request correction of inaccurate or incomplete personal data."],
            ["Right to Erasure", "Request deletion of your data when purpose is fulfilled or consent is withdrawn. Submit via Account Settings → My Data or email us."],
            ["Right to Withdraw Consent", "Withdraw marketing email consent any time from Account Settings → My Data. Withdrawal does not affect data processed before withdrawal."],
            ["Right to Grievance Redressal", "Raise a concern about how we handle your data. We will acknowledge within 24 hours and resolve within 15 business days."],
            ["Right to Nominate", "Nominate another person to exercise your rights in case of death or incapacity (contact us by email)."],
          ].map(([right, desc]) => (
            <div key={right} className="bg-[#0f0f15] border border-[#1f2029] rounded-xl p-4">
              <div className="text-white font-medium text-xs mb-1">{right}</div>
              <div className="text-gray-500 text-xs">{desc}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500">
          If you are unsatisfied with our response, you may file a complaint with the <strong>Data Protection Board of India (DPBI)</strong> once it is operational, or approach the appropriate court of law.
        </p>
      </LegalSection>

      {/* Grievance */}
      <LegalSection title="9. Grievance Officer & Contact">
        <div className="bg-[#0f0f15] border border-[#1f2029] rounded-xl p-5 space-y-2 text-sm">
          <div className="text-white font-semibold mb-3">Grievance Officer</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <span className="text-gray-500">Name:</span><span className="text-white">Harsh Vardhan</span>
            <span className="text-gray-500">Role:</span><span className="text-white">Developer & Data Fiduciary</span>
            <span className="text-gray-500">Email:</span><a href="mailto:support@revealiq.in" className="text-[#FF6D3F] hover:underline">support@revealiq.in</a>
            <span className="text-gray-500">General contact:</span><a href="mailto:hello@revealiq.in" className="text-[#FF6D3F] hover:underline">hello@revealiq.in</a>
            <span className="text-gray-500">Response time:</span><span className="text-white">Acknowledge within 24 hours, resolve within 15 business days</span>
          </div>
        </div>
        <p className="text-xs text-gray-500">
          For IT Act 2000 / IT Rules 2021 complaints, the same officer handles grievances with a 15-day resolution target per Rule 3(1)(c) of the IT (Intermediary Guidelines) Rules, 2021.
        </p>
      </LegalSection>

      {/* Changes */}
      <LegalSection title="10. Changes to This Policy">
        <p>We will notify registered users by email at least 30 days before any material change to this Privacy Policy. Minor updates (typos, clarifications) may be made without notice. The "Last Updated" date at the top always reflects the current version.</p>
      </LegalSection>
    </LegalShell>
  );
};

/* ── Terms of Service ───────────────────────────────────────────────────── */
const TermsPage = () => {
  useEffect(() => { document.title = "Terms of Service — Kautilya AI"; }, []);
  return (
    <LegalShell
      title="Terms of Service"
      subtitle="Last updated: May 29, 2026 · By using Kautilya AI, you agree to these terms."
    >
      <LegalSection title="1. Parties & Platform">
        <p>
          These Terms of Service ("Terms") govern your use of Kautilya AI ("<strong className="text-white">Platform</strong>"), operated by <strong className="text-white">Harsh Vardhan</strong> (an independent developer, trading as <strong className="text-white">RevealIQ</strong>), accessible at ai.revealiq.in and as an Android application. By creating an account or using the Platform in any way, you agree to be bound by these Terms. If you do not agree, do not use the Platform.
        </p>
      </LegalSection>

      <LegalSection title="2. Eligibility — Age Restriction">
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-xs text-amber-300">
          <strong>You must be 18 years of age or older to use Kautilya AI.</strong> By creating an account you confirm that you are at least 18 years old. If we discover a user is under 18, their account will be immediately terminated and data deleted.
        </div>
      </LegalSection>

      <LegalSection title="3. Account Security">
        <p>You are responsible for maintaining the confidentiality of your account. All activity under your account is your responsibility. You must notify us immediately at <a href="mailto:hello@revealiq.in" className="text-[#FF6D3F] hover:underline">hello@revealiq.in</a> if you suspect unauthorised access. We use Google OAuth for authentication — we do not store or manage passwords.</p>
      </LegalSection>

      <LegalSection title="4. Prohibited Content & Uses (IT Rules 2021, Rule 3(1)(b))">
        <p>You agree not to use the Platform to generate, upload, share, or transmit content that:</p>
        <ol className="list-decimal pl-5 space-y-2">
          <li>Belongs to another person without the right to use it (copyright/IP infringement).</li>
          <li>Is harmful, harassing, blasphemous, defamatory, obscene, pornographic, paedophilic, libelous, invasive of another's privacy, or racially or ethnically objectionable.</li>
          <li>Harms or could harm minors in any way, including generating CSAM (child sexual abuse material — a criminal offence under Section 67B of the IT Act and Section 15 of the POCSO Act, carrying imprisonment up to 7 years).</li>
          <li>Infringes any patent, trademark, copyright, or other intellectual property right.</li>
          <li>Violates any law for the time being in force.</li>
          <li>Deceives or misleads the addressee about the origin of messages or communicates any information that is grossly offensive or menacing in nature.</li>
          <li>Impersonates another person.</li>
          <li>Threatens the unity, integrity, defence, security, or sovereignty of India, or friendly relations with foreign states, or public order.</li>
          <li>Contains software viruses or any other computer code designed to interrupt, destroy, or limit the functionality of any computer resource.</li>
          <li>Is patently false and untrue, and written or published in any form with the intent to mislead or harass a person, entity, or agency for financial gain.</li>
        </ol>
        <p>You also agree not to: generate deepfakes or synthetic media of real persons without consent; attempt prompt injection attacks on the platform; bypass rate limits or security controls; use the Developer API to resell or redistribute AI access in violation of upstream LLM provider terms.</p>
      </LegalSection>

      <LegalSection title="5. AI-Generated Content — Important Disclaimer">
        <div className="bg-[#0f0f15] border border-indigo-500/20 rounded-xl p-4 space-y-2 text-xs">
          <div className="text-indigo-300 font-semibold text-sm">All responses on this platform are AI-generated.</div>
          <p className="text-gray-400">Kautilya AI uses large language models (LLMs) to generate responses. These responses:</p>
          <ul className="list-disc pl-4 space-y-1 text-gray-400">
            <li>May contain errors, inaccuracies, or outdated information.</li>
            <li>Are <strong className="text-white">not</strong> professional legal, medical, financial, or expert advice.</li>
            <li>Should always be verified independently before being acted upon.</li>
            <li>Do not represent the views or opinions of RevealIQ or Harsh Vardhan.</li>
          </ul>
          <p className="text-gray-400">You assume full responsibility for any decisions you make based on AI-generated output from this platform.</p>
        </div>
      </LegalSection>

      <LegalSection title="6. Intellectual Property">
        <ul className="list-disc pl-5 space-y-2">
          <li><strong className="text-white">Your content:</strong> You retain ownership of all content you input into the Platform (chat messages, uploaded files).</li>
          <li><strong className="text-white">AI-generated output:</strong> Output generated by the AI in response to your prompts is provided for your use. We do not claim ownership of AI-generated output. However, because LLMs are non-deterministic, similar outputs may be generated for other users — we cannot guarantee uniqueness.</li>
          <li><strong className="text-white">Platform IP:</strong> The Platform, its design, code, branding, and all original content created by RevealIQ/Harsh Vardhan are protected intellectual property. You may not reverse-engineer, copy, or redistribute the Platform.</li>
          <li><strong className="text-white">License to operate:</strong> You grant us a limited, non-exclusive license to process your input data solely to deliver the service to you.</li>
        </ul>
      </LegalSection>

      <LegalSection title="7. Telephony & Campaign Compliance (Outbound Dialer)">
        <p>The Platform includes an outbound voice campaign dialer. If you use this feature:</p>
        <ul className="list-disc pl-5 space-y-2">
          <li>You must comply with <strong className="text-white">TRAI DND (Do-Not-Disturb)</strong> registry rules in India for all outbound calls.</li>
          <li>You must possess explicit prior consent from each lead before adding them to a campaign.</li>
          <li>You are solely responsible for all regulatory compliance, including TCPA (USA) and applicable international laws.</li>
          <li>We disclaim all liability for fines, penalties, or regulatory action resulting from your campaign configurations.</li>
        </ul>
      </LegalSection>

      <LegalSection title="8. Subscription, Billing & Developer API">
        <ul className="list-disc pl-5 space-y-2">
          <li>Paid subscriptions are billed monthly via <strong className="text-white">Razorpay</strong>. All prices are in INR and inclusive of applicable GST (18%).</li>
          <li>Subscriptions auto-renew. You will receive an email reminder before each renewal. Cancel any time from the Razorpay email or by writing to us — cancellation takes effect at the end of the current billing period.</li>
          <li>Developer API usage beyond free quotas is billed on a pay-as-you-go basis as disclosed on the Developer API page.</li>
          <li>Refunds are governed by our <a href="/refund" className="text-[#FF6D3F] hover:underline">Refund & Cancellation Policy</a>.</li>
        </ul>
      </LegalSection>

      <LegalSection title="9. Limitation of Liability">
        <p>To the maximum extent permitted by applicable Indian law:</p>
        <ul className="list-disc pl-5 space-y-2">
          <li>The Platform is provided "as is" without warranties of any kind, express or implied.</li>
          <li>Harsh Vardhan / RevealIQ shall not be liable for any indirect, incidental, special, or consequential damages — including loss of data, revenue, or business — arising from your use of the Platform or AI-generated output.</li>
          <li>Our total aggregate liability for any claim shall not exceed the amount you paid us in the 3 months preceding the claim.</li>
          <li>Nothing in these Terms limits liability for death or personal injury caused by negligence, fraud, or any liability that cannot be excluded under Indian law.</li>
        </ul>
      </LegalSection>

      <LegalSection title="10. Governing Law & Jurisdiction">
        <p>These Terms are governed by the laws of India. Any dispute arising out of or relating to these Terms shall be subject to the exclusive jurisdiction of the competent courts in India. We will endeavour to resolve disputes amicably first — please contact the Grievance Officer before initiating legal proceedings.</p>
      </LegalSection>

      <LegalSection title="11. Grievance Officer (IT Rules 2021 & Consumer Protection Act 2019)">
        <div className="bg-[#0f0f15] border border-[#1f2029] rounded-xl p-4 text-xs grid grid-cols-2 gap-2">
          <span className="text-gray-500">Name:</span><span className="text-white">Harsh Vardhan</span>
          <span className="text-gray-500">Email:</span><a href="mailto:support@revealiq.in" className="text-[#FF6D3F] hover:underline">support@revealiq.in</a>
          <span className="text-gray-500">Acknowledgement:</span><span className="text-white">Within 24 hours of receiving the complaint</span>
          <span className="text-gray-500">Resolution target:</span><span className="text-white">Within 15 business days</span>
          <span className="text-gray-500">Consumer Protection:</span><span className="text-white">Within 48 hours acknowledgement, 30 days resolution</span>
        </div>
        <p className="text-xs text-gray-500">Appointed under Rule 3(1)(c) of the IT (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021 and Rule 7 of the Consumer Protection (E-Commerce) Rules, 2020.</p>
      </LegalSection>

      <LegalSection title="12. Modifications">
        <p>We may modify these Terms at any time. Material changes will be notified to registered users by email at least 30 days before the effective date. Your continued use of the Platform after the effective date constitutes acceptance of the updated Terms.</p>
      </LegalSection>
    </LegalShell>
  );
};

/* ── Refund & Cancellation Policy ──────────────────────────────────────── */
const RefundPage = () => {
  useEffect(() => { document.title = "Refund & Cancellation Policy — Kautilya AI"; }, []);
  return (
    <LegalShell
      title="Refund & Cancellation Policy"
      subtitle="Last updated: May 29, 2026 · Applies to all paid subscriptions and Developer API credits."
    >
      <LegalSection title="1. Overview">
        <p>
          This policy governs refunds and cancellations for paid subscriptions and Developer API credits on Kautilya AI, operated by Harsh Vardhan (RevealIQ). Payments are processed by <strong className="text-white">Razorpay</strong> — we do not store payment card details.
        </p>
      </LegalSection>

      <LegalSection title="2. Subscription Cancellation">
        <ul className="list-disc pl-5 space-y-2">
          <li><strong className="text-white">How to cancel:</strong> Write to <a href="mailto:hello@revealiq.in" className="text-[#FF6D3F] hover:underline">hello@revealiq.in</a> with your registered email address, or use the cancellation link in any Razorpay billing email. We will process the cancellation within 24 hours.</li>
          <li><strong className="text-white">When cancellation takes effect:</strong> At the end of your current billing period. You retain Pro access until then.</li>
          <li><strong className="text-white">No lock-in:</strong> There is no minimum commitment period. You may cancel at any time.</li>
          <li><strong className="text-white">Auto-renewal:</strong> You will receive an email reminder 3 days before each monthly renewal. Auto-renewal can be cancelled any time before the renewal date.</li>
        </ul>
      </LegalSection>

      <LegalSection title="3. Refund Eligibility">
        <div className="space-y-3">
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 text-xs text-emerald-300">
            <strong className="block mb-1">Eligible for Full Refund:</strong>
            <ul className="list-disc pl-4 space-y-1">
              <li>You were charged after cancelling — billing error.</li>
              <li>Duplicate charge in the same billing cycle.</li>
              <li>Service was completely unavailable for more than 48 continuous hours in your billing period due to our fault.</li>
              <li>Request within <strong>7 days</strong> of first Pro subscription charge if you have not materially used the Pro features (fewer than 20 Pro-tier messages sent).</li>
            </ul>
          </div>
          <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-4 text-xs text-rose-300">
            <strong className="block mb-1">Not Eligible for Refund:</strong>
            <ul className="list-disc pl-4 space-y-1">
              <li>Change of mind after actively using the service.</li>
              <li>Refund requested after 7 days of the charge date (except for billing errors).</li>
              <li>Dissatisfaction with AI output quality (AI responses are inherently probabilistic).</li>
              <li>Account terminated due to violation of Terms of Service.</li>
              <li>Pay-as-you-go API credits that have been consumed.</li>
            </ul>
          </div>
        </div>
      </LegalSection>

      <LegalSection title="4. How to Request a Refund">
        <ol className="list-decimal pl-5 space-y-2">
          <li>Email <a href="mailto:hello@revealiq.in" className="text-[#FF6D3F] hover:underline">hello@revealiq.in</a> with the subject line: <strong className="text-white">Refund Request — [your registered email]</strong></li>
          <li>Include your registered email address, the charge date, Razorpay payment ID (from your payment confirmation email), and the reason for the refund request.</li>
          <li>We will review and respond within <strong className="text-white">48 hours</strong>.</li>
          <li>Approved refunds are processed through Razorpay back to your original payment method within <strong className="text-white">5–7 business days</strong>.</li>
        </ol>
      </LegalSection>

      <LegalSection title="5. Developer API Credits">
        <ul className="list-disc pl-5 space-y-2">
          <li>Unused PAYG (pay-as-you-go) API credits are eligible for refund within 30 days of purchase if fewer than 10% of purchased credits have been used.</li>
          <li>Credits consumed are non-refundable.</li>
          <li>Contact <a href="mailto:hello@revealiq.in" className="text-[#FF6D3F] hover:underline">hello@revealiq.in</a> with your credit balance and purchase reference.</li>
        </ul>
      </LegalSection>

      <LegalSection title="6. Consumer Protection Act 2019">
        <p>
          Nothing in this policy limits your rights under the <strong className="text-white">Consumer Protection Act, 2019</strong>. If you believe you have received a defective service, you may raise a complaint with the Grievance Officer below or approach the National Consumer Disputes Redressal Commission (NCDRC) or State Consumer Forum.
        </p>
      </LegalSection>

      <LegalSection title="7. Grievance Officer">
        <div className="bg-[#0f0f15] border border-[#1f2029] rounded-xl p-4 text-xs grid grid-cols-2 gap-2">
          <span className="text-gray-500">Name:</span><span className="text-white">Harsh Vardhan</span>
          <span className="text-gray-500">Email:</span><a href="mailto:support@revealiq.in" className="text-[#FF6D3F] hover:underline">support@revealiq.in</a>
          <span className="text-gray-500">Acknowledgement:</span><span className="text-white">Within 48 hours</span>
          <span className="text-gray-500">Resolution:</span><span className="text-white">Within 30 days</span>
        </div>
      </LegalSection>
    </LegalShell>
  );
};

export default App;
