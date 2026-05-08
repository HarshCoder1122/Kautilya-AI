import { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "@/pages/ChatPage";
import DashboardPage from "@/pages/DashboardPage";

function App() {
  const [theme, setTheme] = useState('dark');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  // Firebase token from localStorage (set by backend auth flow)
  useEffect(() => {
    const token = localStorage.getItem('firebase_token');
    if (token) {
      setUser({ token });
    }
    setLoading(false);
  }, []);

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  // Simple auth check - in production, integrate proper Firebase SDK
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-foreground">Loading...</div>;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage theme={theme} toggleTheme={toggleTheme} user={user} />} />
        <Route path="/dashboard/*" element={<DashboardPage theme={theme} toggleTheme={toggleTheme} user={user} />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
