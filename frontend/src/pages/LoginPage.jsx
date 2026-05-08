import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginWithGoogle } from "@/lib/firebase";
import { GoogleLogo, Brain, ShieldCheck, Lightning, Globe } from "@phosphor-icons/react";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError(null);
      await loginWithGoogle();
      navigate("/");
    } catch (err) {
      setError("Failed to sign in with Google. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#020202] text-white p-4 relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-600/20 rounded-full blur-[120px] animate-pulse"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-rose-600/20 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: '2s' }}></div>

      <div className="w-full max-w-[440px] z-10">
        <div className="text-center mb-10">
          <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-600/20">
            <span className="text-3xl font-bold font-display">K</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight mb-3 font-display bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent">
            Welcome to Kautilya AI
          </h1>
          <p className="text-gray-400 text-lg">
            Synchronize your workspace with the next generation of business intelligence.
          </p>
        </div>

        <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[32px] p-8 shadow-2xl">
          <div className="space-y-6">
            <button
              onClick={handleLogin}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 bg-white text-black py-4 px-6 rounded-2xl font-semibold text-lg hover:bg-gray-100 transition-all duration-300 disabled:opacity-50 active:scale-[0.98]"
            >
              {loading ? (
                <div className="w-6 h-6 border-2 border-black/20 border-t-black rounded-full animate-spin"></div>
              ) : (
                <>
                  <GoogleLogo className="w-6 h-6" weight="bold" />
                  <span>Sign in with Google</span>
                </>
              )}
            </button>

            {error && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm text-center">
                {error}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 pt-4">
              <div className="p-4 rounded-2xl bg-white/5 border border-white/5 flex flex-col items-center gap-2">
                <ShieldCheck className="w-6 h-6 text-indigo-400" weight="duotone" />
                <span className="text-[11px] text-gray-500 uppercase tracking-widest font-medium">Secure</span>
              </div>
              <div className="p-4 rounded-2xl bg-white/5 border border-white/5 flex flex-col items-center gap-2">
                <Lightning className="w-6 h-6 text-amber-400" weight="duotone" />
                <span className="text-[11px] text-gray-500 uppercase tracking-widest font-medium">Real-time</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-10 text-center">
          <p className="text-gray-500 text-sm">
            By signing in, you agree to our <a href="#" className="text-indigo-400 hover:underline">Terms</a> and <a href="#" className="text-indigo-400 hover:underline">Privacy Policy</a>
          </p>
        </div>
      </div>

      {/* Floating Icons Decors */}
      <div className="absolute top-20 right-[15%] opacity-20 hidden lg:block">
        <Brain className="w-12 h-12 text-indigo-400 animate-bounce" style={{ animationDuration: '4s' }} />
      </div>
      <div className="absolute bottom-20 left-[15%] opacity-20 hidden lg:block">
        <Globe className="w-12 h-12 text-rose-400 animate-bounce" style={{ animationDuration: '6s' }} />
      </div>
    </div>
  );
}
