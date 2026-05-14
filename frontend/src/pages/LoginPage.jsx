import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginWithGoogle } from "../lib/firebase";
import { GoogleLogo, ArrowRight, Brain, ChartLineUp, Robot, ShieldCheck, Sparkle } from "@phosphor-icons/react";

const features = [
  {
    icon: Brain,
    title: "Multi-Model Intelligence",
    desc: "Kautilya Pro, Coder & Daily — each optimized for its domain.",
    color: "text-violet-400",
    bg: "bg-violet-400/10",
  },
  {
    icon: ChartLineUp,
    title: "Deep Research",
    desc: "Perplexity-style web search with structured reports and citations.",
    color: "text-blue-400",
    bg: "bg-blue-400/10",
  },
  {
    icon: Robot,
    title: "AI Voice Agents",
    desc: "Deploy voice agents for sales, support, and outbound campaigns.",
    color: "text-emerald-400",
    bg: "bg-emerald-400/10",
  },
  {
    icon: ShieldCheck,
    title: "Enterprise Secure",
    desc: "Firebase Auth, role-based tiers, and full data privacy.",
    color: "text-amber-400",
    bg: "bg-amber-400/10",
  },
];

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
      setError("Failed to sign in. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-[#080a0f] text-white overflow-hidden">
      {/* Left panel — branding & features */}
      <div className="hidden lg:flex flex-col justify-between w-[52%] px-16 py-14 relative overflow-hidden">
        {/* Ambient gradient */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-20%] left-[-15%] w-[60%] h-[60%] bg-indigo-600/12 rounded-full blur-[160px]" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600/10 rounded-full blur-[140px]" />
        </div>

        {/* Logo */}
        <div className="relative flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
            <span className="text-white text-lg font-black tracking-tight">K</span>
          </div>
          <div>
            <span className="text-white font-bold text-lg tracking-tight">Kautilya AI</span>
            <span className="ml-2 text-[10px] uppercase tracking-[0.2em] text-indigo-400/70 font-semibold">by RevealIQ</span>
          </div>
        </div>

        {/* Main headline */}
        <div className="relative">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 mb-6">
            <Sparkle className="w-3.5 h-3.5 text-indigo-400" weight="fill" />
            <span className="text-[11px] text-indigo-300 font-semibold uppercase tracking-wider">Next-Gen Business AI</span>
          </div>

          <h1 className="text-5xl font-black tracking-tight leading-[1.1] mb-6">
            <span className="text-white">Intelligence</span>
            <br />
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              that works
            </span>
            <br />
            <span className="text-white">for you.</span>
          </h1>

          <p className="text-white/50 text-lg leading-relaxed max-w-[400px]">
            From deep research and code analysis to AI voice agents — Kautilya brings enterprise intelligence to your workflow.
          </p>
        </div>

        {/* Feature grid */}
        <div className="relative grid grid-cols-2 gap-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:border-white/10 hover:bg-white/[0.05] transition-all duration-300"
            >
              <div className={`w-8 h-8 rounded-lg ${f.bg} flex items-center justify-center mb-3`}>
                <f.icon className={`w-4 h-4 ${f.color}`} weight="duotone" />
              </div>
              <div className="text-sm font-semibold text-white/90 mb-1">{f.title}</div>
              <div className="text-xs text-white/40 leading-relaxed">{f.desc}</div>
            </div>
          ))}
        </div>

        {/* Bottom tagline */}
        <div className="relative text-[11px] text-white/25 font-medium tracking-wide">
          Trusted by teams across India · Powered by NVIDIA NIM & Groq
        </div>
      </div>

      {/* Right panel — sign in */}
      <div className="flex-1 flex items-center justify-center px-6 relative">
        {/* Mobile ambient */}
        <div className="absolute inset-0 pointer-events-none lg:hidden">
          <div className="absolute top-[-20%] right-[-20%] w-[70%] h-[70%] bg-indigo-600/15 rounded-full blur-[120px]" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] bg-violet-600/10 rounded-full blur-[100px]" />
        </div>

        {/* Vertical divider (desktop) */}
        <div className="hidden lg:block absolute left-0 inset-y-0 w-px bg-gradient-to-b from-transparent via-white/[0.06] to-transparent" />

        <div className="w-full max-w-[400px] relative">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <span className="text-white text-lg font-black">K</span>
            </div>
            <span className="text-white font-bold text-lg">Kautilya AI</span>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-black tracking-tight text-white mb-2">Welcome back</h2>
            <p className="text-white/40 text-sm">Sign in to access your AI workspace.</p>
          </div>

          {/* Sign in card */}
          <div className="space-y-4">
            <button
              onClick={handleLogin}
              disabled={loading}
              className="group w-full flex items-center justify-center gap-3 bg-white text-[#0a0a0a] py-4 px-6 rounded-2xl font-semibold text-[15px] hover:bg-white/95 active:scale-[0.98] transition-all duration-200 disabled:opacity-60 shadow-xl shadow-white/5"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
                  <span>Signing in…</span>
                </>
              ) : (
                <>
                  <GoogleLogo className="w-5 h-5" weight="bold" />
                  <span>Continue with Google</span>
                  <ArrowRight className="w-4 h-4 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" weight="bold" />
                </>
              )}
            </button>

            {error && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm text-center">
                {error}
              </div>
            )}
          </div>

          {/* Trust badges */}
          <div className="mt-8 grid grid-cols-3 gap-3">
            {[
              { label: 'Secure Auth', sub: 'Firebase' },
              { label: 'AI Reasoning', sub: 'NVIDIA NIM' },
              { label: 'Fast', sub: 'Groq Infra' },
            ].map((b) => (
              <div key={b.label} className="text-center p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[11px] font-semibold text-white/70">{b.label}</div>
                <div className="text-[10px] text-white/30 mt-0.5">{b.sub}</div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <p className="mt-8 text-center text-white/25 text-xs leading-relaxed">
            By signing in, you agree to our{" "}
            <a href="#" className="text-indigo-400/70 hover:text-indigo-400 transition-colors underline underline-offset-2">Terms</a>
            {" "}and{" "}
            <a href="#" className="text-indigo-400/70 hover:text-indigo-400 transition-colors underline underline-offset-2">Privacy Policy</a>
          </p>
        </div>
      </div>
    </div>
  );
}
