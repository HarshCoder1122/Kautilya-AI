import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronLeft, ArrowRight } from 'lucide-react';

const SWIPE_THRESHOLD = 60; // px the user must drag to flip a card
const BRAND = '#FF6D3F';    // Kautilya brand orange — matches logo, links, consent modal

export function OnboardingModal({ user }) {
  const [visible, setVisible] = useState(false);
  const [animatingOut, setAnimatingOut] = useState(false);
  const [index, setIndex] = useState(0);

  // Drag state lives in a ref so pointer-move doesn't thrash React renders.
  const trackRef = useRef(null);
  const dragRef = useRef({ active: false, startX: 0, dx: 0 });
  const [dragX, setDragX] = useState(0);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const hasSeen = localStorage.getItem('kautilya_onboarding_done');
    if (!hasSeen) {
      const timer = setTimeout(() => setVisible(true), 600);
      return () => clearTimeout(timer);
    }
  }, []);

  const firstName = user?.displayName?.split(' ')[0] || 'there';

  const slides = [
    {
      key: 'welcome',
      eyebrow: `Hi ${firstName} 👋`,
      image: '/images/onboarding/reasoning.png',
      title: 'Welcome to Kautilya AI',
      description:
        'Your strategic AI workspace. Swipe through a quick tour of what you can do — it takes 20 seconds.',
    },
    {
      key: 'reasoning',
      eyebrow: 'Think with you',
      image: '/images/onboarding/reasoning.png',
      title: 'Advanced AI Reasoning',
      description:
        'Powered by frontier models to break down complex strategic problems and assist you with high accuracy.',
    },
    {
      key: 'canvas',
      eyebrow: 'Build & preview',
      image: '/images/onboarding/canvas.png',
      title: 'Interactive Canvas',
      description:
        'Generate, preview and edit React components, markdown docs and charts side-by-side with the chat.',
    },
    {
      key: 'integrations',
      eyebrow: 'Live data',
      image: '/images/onboarding/integrations.png',
      title: 'Live Integrations',
      description:
        'Search maps, analyse spreadsheets and pull live data straight into your conversations — no copy-paste.',
    },
  ];

  const lastIndex = slides.length - 1;
  const isLast = index === lastIndex;

  const goTo = useCallback(
    (i) => setIndex(Math.max(0, Math.min(lastIndex, i))),
    [lastIndex]
  );

  const handleFinish = useCallback(() => {
    setAnimatingOut(true);
    setTimeout(() => {
      localStorage.setItem('kautilya_onboarding_done', '1');
      setVisible(false);
    }, 400);
  }, []);

  const handleNext = useCallback(() => {
    if (isLast) handleFinish();
    else goTo(index + 1);
  }, [isLast, index, goTo, handleFinish]);

  // Keyboard arrows + Escape
  useEffect(() => {
    if (!visible) return;
    const onKey = (e) => {
      if (e.key === 'ArrowRight') goTo(index + 1);
      else if (e.key === 'ArrowLeft') goTo(index - 1);
      else if (e.key === 'Escape') handleFinish();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [visible, index, goTo, handleFinish]);

  // --- Pointer / swipe handlers -------------------------------------------
  const onPointerDown = (e) => {
    dragRef.current = { active: true, startX: e.clientX, dx: 0 };
    setDragging(true);
  };

  const onPointerMove = (e) => {
    const d = dragRef.current;
    if (!d.active) return;
    let dx = e.clientX - d.startX;
    // Rubber-band at the edges so it feels bounded, not broken.
    if ((index === 0 && dx > 0) || (index === lastIndex && dx < 0)) dx *= 0.35;
    d.dx = dx;
    setDragX(dx);
  };

  const endDrag = () => {
    const d = dragRef.current;
    if (!d.active) return;
    d.active = false;
    setDragging(false);
    if (d.dx <= -SWIPE_THRESHOLD) goTo(index + 1);
    else if (d.dx >= SWIPE_THRESHOLD) goTo(index - 1);
    setDragX(0);
  };

  if (!visible) return null;

  const trackStyle = {
    transform: `translateX(calc(${-index * 100}% + ${dragX}px))`,
    transition: dragging ? 'none' : 'transform 0.45s cubic-bezier(0.22, 1, 0.36, 1)',
  };

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center p-4 transition-all duration-500 ${
        animatingOut ? 'opacity-0' : 'opacity-100'
      }`}
    >
      {/* Backdrop — matches the consent modal that precedes onboarding */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={handleFinish}
      />

      {/* Modal shell */}
      <div
        className={`relative w-full max-w-[28rem] bg-[#0f0f18] border border-[#2a2a3a] shadow-2xl rounded-3xl overflow-hidden transform transition-all duration-500 ${
          animatingOut ? 'scale-95 translate-y-4' : 'scale-100 translate-y-0'
        }`}
      >
        {/* Brand accent line */}
        <div
          className="absolute top-0 left-0 w-full h-1"
          style={{ background: `linear-gradient(90deg, ${BRAND}, #f59e0b)` }}
        />

        {/* Skip */}
        {!isLast && (
          <button
            onClick={handleFinish}
            className="absolute top-4 right-5 z-20 text-xs font-medium text-gray-500 hover:text-gray-300 transition-colors"
          >
            Skip
          </button>
        )}

        {/* Swipeable track */}
        <div
          ref={trackRef}
          className="relative overflow-hidden touch-pan-y select-none"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerLeave={endDrag}
          onPointerCancel={endDrag}
        >
          <div className="flex" style={trackStyle}>
            {slides.map((s) => (
              <div key={s.key} className="min-w-full px-6 pt-8 pb-6">
                <div className="flex flex-col items-center text-center">
                  {/* Premium Image Card */}
                  <div className="relative mb-6 w-full aspect-[16/10] rounded-2xl overflow-hidden shadow-2xl border border-[#2a2a3a]">
                    <img src={s.image} alt={s.title} className="w-full h-full object-cover" />
                    {/* Subtle bottom gradient to blend image into background */}
                    <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-gradient-to-t from-[#0f0f18] to-transparent pointer-events-none" />
                  </div>

                  <span
                    className="text-xs font-semibold uppercase tracking-wider mb-2"
                    style={{ color: BRAND }}
                  >
                    {s.eyebrow}
                  </span>
                  <h2 className="text-2xl font-bold text-white tracking-tight mb-3 leading-snug">
                    {s.title}
                  </h2>
                  <p className="text-gray-400 text-sm leading-relaxed max-w-[260px]">
                    {s.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer: dots + controls */}
        <div className="px-8 pb-7 pt-2">
          {/* Progress dots */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {slides.map((s, i) => (
              <button
                key={s.key}
                onClick={() => goTo(i)}
                aria-label={`Go to slide ${i + 1}`}
                className="h-1.5 rounded-full transition-all duration-300"
                style={{
                  width: i === index ? 22 : 6,
                  background: i === index ? BRAND : '#3a3a4a',
                }}
              />
            ))}
          </div>

          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => goTo(index - 1)}
              className={`inline-flex items-center gap-1 text-sm font-medium text-gray-400 hover:text-white transition-all ${
                index === 0 ? 'opacity-0 pointer-events-none' : 'opacity-100'
              }`}
            >
              <ChevronLeft className="w-4 h-4" />
              Back
            </button>

            {/* Primary CTA — indigo to match the consent modal's "Continue" button */}
            <button
              onClick={handleNext}
              className="group relative inline-flex items-center justify-center gap-2 px-7 py-3 text-sm font-semibold text-white rounded-full overflow-hidden bg-indigo-600 hover:bg-indigo-500 transition-colors duration-200 shadow-lg"
            >
              <span className="relative z-10 flex items-center gap-2">
                {isLast ? 'Get Started' : 'Next'}
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </span>
              <div className="absolute inset-0 h-full w-full bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
