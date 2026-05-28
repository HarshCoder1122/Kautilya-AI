import { useState, useEffect, lazy, Suspense } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { getAuthInstance } from "./lib/firebase.js";
import { onAuthStateChanged, getRedirectResult } from "firebase/auth";

import InstallPWA from "./components/shared/InstallPWA";

// Lazy load route components
const ChatPage = lazy(() => import("./pages/ChatPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));

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
  // Hydrate from cache so returning users don't see the spinner at all.
  // The async Firebase listener will reconcile / sign out as needed.
  const cachedUser = _readCachedUser();
  const [user, setUser] = useState(cachedUser);
  const [loading, setLoading] = useState(!cachedUser);

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

    // Resolve Google Redirect Sign-In results if coming back from redirect flow
    getRedirectResult(auth)
      .then((result) => {
        if (result?.user) {
          console.log("[Auth] Redirect sign-in success:", result.user);
        }
      })
      .catch((e) => {
        console.warn("[Auth] Redirect sign-in error:", e);
      });

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

    return () => {
      unsubscribe();
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
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/login" element={!user ? <LoginPage /> : <Navigate to="/" />} />
          <Route path="/" element={user ? <ChatPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
          <Route path="/dashboard/*" element={user ? <DashboardPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

const PrivacyPage = () => {
  useEffect(() => {
    document.title = "Privacy Policy — Kautilya AI";
  }, []);
  return (
    <div className="min-h-screen bg-[#07070a] text-[#f5f5f7] font-sans p-6 md:p-12 flex items-center justify-center">
      <div className="max-w-3xl w-full bg-[#0f0f15] border border-[#1f2029] rounded-3xl p-8 md:p-12 shadow-2xl">
        <div className="text-center border-b border-[#1f2029] pb-8 mb-8">
          <div className="text-2xl font-bold text-[#FF6D3F] font-sans tracking-tight mb-2">Kautilya AI</div>
          <h1 className="text-3xl font-semibold text-white mb-2">Privacy Policy</h1>
          <div className="text-xs text-gray-500">Last Updated: May 24, 2026</div>
        </div>
        <div className="space-y-6 text-sm text-gray-400 leading-relaxed">
          <p>Kautilya AI ("we," "our," or "us") is dedicated to protecting your privacy. This Privacy Policy details how we gather, utilize, and protect your information when you access our platform, voice agents, chat widgets, and third-party integrations (specifically Google APIs and GitHub services).</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">1. Information We Collect</h2>
          <p>We only collect the information necessary to provide and optimize the Kautilya AI conversational and automation services:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li><strong>Account Information:</strong> Profile details securely managed via Google Single Sign-On (Google Authentication).</li>
            <li><strong>Conversation Transcripts & Logs:</strong> Summaries and interaction transcripts securely stored inside your sandboxed Firestore databases.</li>
            <li><strong>User-Configured Credentials:</strong> Encrypted integrations keys and OAuth access tokens (HubSpot, Zoho, WhatsApp Business, Slack, Google APIs, GitHub).</li>
          </ul>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">2. Disclosure of Google User Data</h2>
          <p>To enable the strategic automation capabilities of your Kautilya conversational and voice agents, you can authorize our app to connect to Google Services. Below are the specific scopes requested and how they are used:</p>

          <div className="border border-[#1f2029] bg-[#FF6D3F]/5 p-6 rounded-2xl space-y-4">
            <div>
              <span className="font-semibold text-white block mb-1">https://www.googleapis.com/auth/calendar.events</span>
              <p className="text-xs text-gray-500">Allows Kautilya voice and chat agents to check your availability, book calendar events, edit meetings, and generate Google Meet links dynamically on your behalf.</p>
            </div>
            <div>
              <span className="font-semibold text-white block mb-1">https://www.googleapis.com/auth/spreadsheets</span>
              <p className="text-xs text-gray-500">Allows campaign workers to stream outbound leads from a Google Sheet and write qualified lead contacts directly into your custom spreadsheets.</p>
            </div>
            <div>
              <span className="font-semibold text-white block mb-1">https://www.googleapis.com/auth/tasks</span>
              <p className="text-xs text-gray-500">Allows our transcription follow-up pipeline to write task lists and action items directly to your personal Google Tasks boards.</p>
            </div>
            <div>
              <span className="font-semibold text-white block mb-1">https://www.googleapis.com/auth/drive.readonly</span>
              <p className="text-xs text-gray-500">Allows the workspace search and RAG engine to query document summaries and retrieve reference materials from your Drive to train/ground your agents.</p>
            </div>
            <div>
              <span className="font-semibold text-white block mb-1">https://www.googleapis.com/auth/gmail.send</span>
              <p className="text-xs text-gray-500">Allows the followup extraction pipeline to dispatch summary emails to clients or internal notifications following voice agent calls.</p>
            </div>
          </div>

          <p className="text-xs text-gray-500 mt-4"><strong>Google API Services User Data Policy Compliance:</strong> Kautilya AI's use and transfer to any other app of information received from Google APIs will adhere to the Google API Services User Data Policy, including the Limited Use requirements.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">3. GitHub Integration</h2>
          <p>By connecting your account with GitHub OAuth (repo, read:user), the system securely spins up a sandboxed Model Context Protocol (MCP) server that lets your conversational agent pull code, review commits, and push PR revisions solely at your explicit direction.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">4. Data Retention and Security</h2>
          <p>We employ enterprise-grade security protocols, including Firestore AES encryption and TLS transport protection. Your OAuth access tokens are securely sandboxed and never shared with third parties or external providers. You can permanently revoke any integration at any time from your settings panel.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">5. Contact Us</h2>
          <p>If you have any questions regarding this privacy policy or our Google verification status, contact us at support@revealiq.in.</p>
        </div>
        <div className="text-center border-t border-[#1f2029] pt-6 mt-8 text-xs text-gray-500">
          &copy; 2026 Kautilya AI by RevealIQ. All rights reserved.
        </div>
      </div>
    </div>
  );
};

const TermsPage = () => {
  useEffect(() => {
    document.title = "Terms of Service — Kautilya AI";
  }, []);
  return (
    <div className="min-h-screen bg-[#07070a] text-[#f5f5f7] font-sans p-6 md:p-12 flex items-center justify-center">
      <div className="max-w-3xl w-full bg-[#0f0f15] border border-[#1f2029] rounded-3xl p-8 md:p-12 shadow-2xl">
        <div className="text-center border-b border-[#1f2029] pb-8 mb-8">
          <div className="text-2xl font-bold text-[#FF6D3F] font-sans tracking-tight mb-2">Kautilya AI</div>
          <h1 className="text-3xl font-semibold text-white mb-2">Terms of Service</h1>
          <div className="text-xs text-gray-500">Last Updated: May 24, 2026</div>
        </div>
        <div className="space-y-6 text-sm text-gray-400 leading-relaxed">
          <p>Welcome to Kautilya AI ("Platform," "we," "our," or "us"). By accessing or utilizing our single-page React app, API services, conversational widgets, voice workers, or third-party integrations, you agree to comply with and be bound by the following Terms of Service. If you do not agree to these terms, do not access or use the Platform.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">1. Account Eligibility and Security</h2>
          <p>To access the advanced dashboard and integrations settings, you must register through our secure Google SSO protocol. You are entirely responsible for the security of your account and any strategic agent creations or API key uses occurring under your account.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">2. Customer Telephony & Campaign Regulations</h2>
          <p>Our platform includes a background outbound dialer engine (`campaign_worker.py`) that makes automated voice calls on your behalf via SIP provider channels. You agree to use the dialer solely in accordance with regulatory laws:</p>

          <div className="border border-[#1f2029] bg-[#FF6D3F]/5 p-6 rounded-2xl">
            <strong className="text-white block mb-2">TRAI, TCPA, and FCC Regulatory Compliance:</strong>
            <p className="text-xs text-gray-500 leading-relaxed">You explicitly agree to comply with all regional cold-calling and outbound campaign regulations, including the <strong>TCPA (Telephone Consumer Protection Act)</strong> in the United States and the <strong>TRAI (Telecom Regulatory Authority of India)</strong> Do-Not-Disturb (DND) registries in India. You must possess explicit opt-in consent before staging leads inside the campaign system. We disclaim all liability for regulatory fines resulting from unsolicited outbound campaign configurations.</p>
          </div>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">3. Third-Party Integrations and OAuth API Use</h2>
          <p>Our platform lets you connect external developer services and Google APIs (Sheets, Tasks, Calendar, Drive, Gmail) using secure, central OAuth. Your authorization gives our background agent workers isolated, limited permissions to interact with these systems on your behalf. We are not responsible for the uptime or operations of external API providers.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">4. Prohibited Uses</h2>
          <p>You agree not to use the Platform to:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li>Generate spam or fraudulent outbound telephony campaigns.</li>
            <li>Deploy deceptive, misleading, or malicious conversational agents.</li>
            <li>Bypass rate-limits or system security sandboxes (such as the Python code interpreter).</li>
            <li>Reverse-engineer or exploit Platform assets and models.</li>
          </ul>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">5. Limitation of Liability</h2>
          <p>TO THE MAXIMUM EXTENT PERMITTED BY LAW, KAUTILYA AI AND ITS PARENT REVEALIQ INDUSTRIES SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOSS OF DATA, REVENUE, OR API CHARGES RESULTING FROM PLATFORM CONVERSATIONS AND SCHEDULINGS.</p>

          <h2 className="text-lg font-semibold text-[#FF6D3F] pt-4">6. Modifications to Terms</h2>
          <p>We reserve the right to modify these Terms at any time. Your continued use of Kautilya AI after the posting of modifications indicates your active acceptance of the updated Terms.</p>
        </div>
        <div className="text-center border-t border-[#1f2029] pt-6 mt-8 text-xs text-gray-500">
          &copy; 2026 Kautilya AI by RevealIQ. All rights reserved.
        </div>
      </div>
    </div>
  );
};

export default App;
