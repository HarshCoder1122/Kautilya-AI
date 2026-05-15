import { useState, useEffect, lazy, Suspense } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { getAuthInstance } from "./lib/firebase.js";
import { onAuthStateChanged } from "firebase/auth";

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

function App() {
  const [theme, setTheme] = useState('dark');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    const auth = getAuthInstance();
    let refreshInterval = null;

    const refreshToken = async (authUser) => {
      try {
        const token = await authUser.getIdToken(true);
        localStorage.setItem('firebase_token', token);
      } catch (e) {
        console.warn('[Auth] Token refresh failed:', e);
      }
    };

    const unsubscribe = onAuthStateChanged(auth, async (authUser) => {
      if (refreshInterval) clearInterval(refreshInterval);
      if (authUser) {
        const token = await authUser.getIdToken(true);
        localStorage.setItem('firebase_token', token);
        setUser(authUser);
        // Refresh token every 55 minutes (expires at 60m)
        refreshInterval = setInterval(() => refreshToken(authUser), 55 * 60 * 1000);
      } else {
        localStorage.removeItem('firebase_token');
        setUser(null);
      }
      setLoading(false);
    });

    return () => {
      unsubscribe();
      if (refreshInterval) clearInterval(refreshInterval);
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
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/login" element={!user ? <LoginPage /> : <Navigate to="/" />} />
          <Route path="/" element={user ? <ChatPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
          <Route path="/dashboard/*" element={user ? <DashboardPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
