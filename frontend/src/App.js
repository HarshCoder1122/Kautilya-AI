import { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { getAuthInstance } from "@/lib/firebase";
import { onAuthStateChanged } from "firebase/auth";
import ChatPage from "@/pages/ChatPage";
import DashboardPage from "@/pages/DashboardPage";
import LoginPage from "@/pages/LoginPage";

function App() {
  const [theme, setTheme] = useState('dark');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    const auth = getAuthInstance();
    const unsubscribe = onAuthStateChanged(auth, async (authUser) => {
      if (authUser) {
        const token = await authUser.getIdToken();
        localStorage.setItem('firebase_token', token);
        setUser(authUser);
      } else {
        localStorage.removeItem('firebase_token');
        setUser(null);
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#020202] text-white">
        <div className="w-12 h-12 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
        <div className="text-sm text-gray-500 font-medium tracking-widest uppercase">Initializing J.A.R.V.I.S</div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={!user ? <LoginPage /> : <Navigate to="/" />} />
        <Route path="/" element={user ? <ChatPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
        <Route path="/dashboard/*" element={user ? <DashboardPage theme={theme} toggleTheme={toggleTheme} user={user} /> : <Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
