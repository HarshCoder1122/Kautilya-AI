import React, { useState, useEffect } from 'react';
import { Sparkles, Zap, LayoutTemplate, MapPin, Code, ChevronRight } from 'lucide-react';

export function OnboardingModal({ user }) {
  const [visible, setVisible] = useState(false);
  const [animatingOut, setAnimatingOut] = useState(false);

  useEffect(() => {
    // Check if the user has already seen the onboarding
    const hasSeen = localStorage.getItem('kautilya_onboarding_done');
    if (!hasSeen) {
      // Small delay for smooth entrance after chat page loads
      const timer = setTimeout(() => setVisible(true), 600);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!visible) return null;

  const handleGetStarted = () => {
    setAnimatingOut(true);
    setTimeout(() => {
      localStorage.setItem('kautilya_onboarding_done', '1');
      setVisible(false);
    }, 400); // Wait for exit animation
  };

  const features = [
    {
      icon: <Sparkles className="w-5 h-5 text-indigo-400" />,
      title: 'Advanced AI Reasoning',
      description: 'Powered by frontier models to solve complex strategic problems and assist you with high accuracy.',
    },
    {
      icon: <LayoutTemplate className="w-5 h-5 text-emerald-400" />,
      title: 'Interactive Canvas',
      description: 'Generate, preview, and edit React components, markdown documents, and charts directly in the UI.',
    },
    {
      icon: <Zap className="w-5 h-5 text-amber-400" />,
      title: 'Live Integrations',
      description: 'Search maps, analyze spreadsheets, and pull live data seamlessly into your conversations.',
    },
    {
      icon: <Code className="w-5 h-5 text-blue-400" />,
      title: 'Developer Focused',
      description: 'Execute code snippets safely in an isolated environment and visualize the outputs instantly.',
    }
  ];

  return (
    <div className={`fixed inset-0 z-[9999] flex items-center justify-center p-4 transition-all duration-500 ${animatingOut ? 'opacity-0' : 'opacity-100'}`}>
      {/* Blurred Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-md"
        onClick={handleGetStarted}
      />
      
      {/* Modal Content */}
      <div className={`relative w-full max-w-2xl bg-[#0a0a0f]/95 border border-[#2a2a3a] shadow-2xl rounded-3xl overflow-hidden transform transition-all duration-500 ${animatingOut ? 'scale-95 translate-y-4' : 'scale-100 translate-y-0'}`}>
        
        {/* Top Decorative Gradient */}
        <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-[#FF6D3F]"></div>

        <div className="p-8 sm:p-10">
          <div className="flex flex-col items-center text-center mb-10">
            <div className="w-16 h-16 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl flex items-center justify-center mb-5 shadow-inner">
              <Sparkles className="w-8 h-8 text-indigo-400" />
            </div>
            <h2 className="text-3xl font-bold text-white tracking-tight mb-3">
              Welcome to Kautilya AI
            </h2>
            <p className="text-gray-400 text-sm max-w-md mx-auto leading-relaxed">
              Hello {user?.displayName?.split(' ')[0] || 'there'}, you're now equipped with a powerful AI ecosystem. Here are some key capabilities to explore.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
            {features.map((feature, idx) => (
              <div 
                key={idx} 
                className="bg-[#12121a] hover:bg-[#161622] transition-colors border border-[#1f2029] rounded-2xl p-5 flex items-start gap-4 group"
              >
                <div className="mt-1 p-2 bg-black/40 rounded-xl group-hover:scale-110 transition-transform">
                  {feature.icon}
                </div>
                <div>
                  <h3 className="text-white font-semibold text-sm mb-1">{feature.title}</h3>
                  <p className="text-gray-400 text-xs leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-center">
            <button
              onClick={handleGetStarted}
              className="group relative inline-flex items-center justify-center px-8 py-3.5 text-sm font-semibold text-white transition-all duration-200 bg-indigo-600 border border-transparent rounded-full hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-600 focus:ring-offset-[#0a0a0f] overflow-hidden"
            >
              <span className="relative z-10 flex items-center gap-2">
                Get Started
                <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </span>
              <div className="absolute inset-0 h-full w-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]"></div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
