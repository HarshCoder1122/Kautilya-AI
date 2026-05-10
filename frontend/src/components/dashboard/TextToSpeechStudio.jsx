import { useState, useRef, useEffect } from "react";
import { Play, Pause, VolumeHigh, Gear, Sparkle, Download, Waveform, SpeakerHigh, Pulse } from "@phosphor-icons/react";
import { ttsAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function TextToSpeechStudio() {
  const [selectedProvider, setSelectedProvider] = useState('revealIQ');
  const [text, setText] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const audioInstanceRef = useRef(null);
  
  // RevealIQ specific
  const [revealIQModel, setRevealIQModel] = useState('kokoro-en');
  const [revealIQVoice, setRevealIQVoice] = useState('af_nicole');
  const [revealIQSpeed, setRevealIQSpeed] = useState(1.0);
  
  // Cartesia specific
  const [cartesiaVoice, setCartesiaVoice] = useState(ttsAPI.cartesia.getVoices()[0].id);
  
  // ElevenLabs specific
  const [elevenLabsVoiceId, setElevenLabsVoiceId] = useState(ttsAPI.elevenLabs.getVoices()[0].id);
  
  // Sarvam specific
  const [sarvamLanguage, setSarvamLanguage] = useState(ttsAPI.sarvam.getLanguages()[0].id);

  // Clean up audio instance on unmount
  useEffect(() => {
    return () => {
      if (audioInstanceRef.current) {
        audioInstanceRef.current.pause();
        audioInstanceRef.current = null;
      }
    };
  }, []);

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    
    // Stop any existing playback
    if (audioInstanceRef.current) {
      audioInstanceRef.current.pause();
      audioInstanceRef.current = null;
    }

    try {
      setLoading(true);
      
      if (selectedProvider === 'revealIQ') {
        // --- START NEW ZERO-LAG STREAMING LOGIC ---
        const response = await ttsAPI.revealIQ.stream(text, revealIQModel, revealIQVoice, revealIQSpeed);
        
        if (!response.ok) throw new Error('Streaming failed');

        const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        const reader = response.body.getReader();
        let startTime = audioCtx.currentTime + 0.1;

        setIsPlaying(true);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          // Convert Int16 PCM bytes to Float32 for Web Audio API
          const pcmData = new Int16Array(value.buffer);
          const float32Data = new Float32Array(pcmData.length);
          for (let i = 0; i < pcmData.length; i++) {
            float32Data[i] = pcmData[i] / 32768.0;
          }

          const audioBuffer = audioCtx.createBuffer(1, float32Data.length, 24000);
          audioBuffer.getChannelData(0).set(float32Data);

          const source = audioCtx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(audioCtx.destination);
          
          source.start(startTime);
          startTime += audioBuffer.duration;
        }
        // --- END STREAMING LOGIC ---
        return;
      }

      // Fallback for other providers (Standard synthesis)
      let audioBlob;
      switch (selectedProvider) {
        case 'cartesia':
          audioBlob = await ttsAPI.cartesia.synthesize(text, cartesiaVoice);
          break;
        case 'elevenLabs':
          audioBlob = await ttsAPI.elevenLabs.synthesize(text, elevenLabsVoiceId);
          break;
        case 'sarvam':
          audioBlob = await ttsAPI.sarvam.synthesize(text, sarvamLanguage);
          break;
        default:
          throw new Error('Invalid provider');
      }
      
      const url = URL.createObjectURL(audioBlob);
      setAudioUrl(url);
      const audio = new Audio(url);
      audioInstanceRef.current = audio;
      audio.onended = () => setIsPlaying(false);
      await audio.play();
      setIsPlaying(true);
    } catch (error) {
      console.error('TTS synthesis failed:', error);
      alert('Failed to synthesize speech. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePlay = () => {
    if (audioInstanceRef.current) {
      if (isPlaying) {
        audioInstanceRef.current.pause();
      } else {
        audioInstanceRef.current.play();
      }
    }
  };

  const handleDownload = () => {
    if (audioUrl) {
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = `kautilya-tts-${Date.now()}.wav`;
      a.click();
    }
  };

  const revealIQVoices = ttsAPI.revealIQ.getVoices(revealIQModel);

  const voiceDisplayNames = {
    'af_heart': 'Priya Sharma (Sweet)',
    'af_bella': 'Ananya Singh (Professional)',
    'af_nicole': 'Neha Kapoor (Expressive)',
    'af_sky': 'Sneha Reddy (Soft)',
    'am_adam': 'Arjun Mehta (Deep)',
    'am_michael': 'Rahul Verma (Narrator)',
    'hf_alpha': 'Aarav Kumar (Hindi Female)',
    'hf_beta': 'Vihaan Sharma (Hindi Male)',
  };

  return (
    <div className="h-full bg-[var(--k-surface)]/30 backdrop-blur-sm" data-testid="tts-studio">
      <div className="px-8 py-8 border-b border-[var(--k-border)] bg-gradient-to-r from-black/20 to-transparent">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 rounded-xl bg-[var(--k-brand)] flex items-center justify-center shadow-lg shadow-[var(--k-brand)]/20">
                <Waveform className="w-6 h-6 text-white" weight="bold" />
              </div>
              <h1 className="text-3xl font-bold k-heading tracking-tighter text-foreground">Voice Studio</h1>
            </div>
            <p className="text-sm text-muted-foreground/60 ml-13">Next-generation neural speech synthesis</p>
          </div>
        </div>
      </div>

      <ScrollArea className="h-[calc(100vh-140px)]">
        <div className="max-w-5xl mx-auto px-8 py-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* Left: Configuration */}
            <div className="lg:col-span-5 space-y-8">
              <div className="p-6 rounded-2xl border border-[var(--k-border)] bg-black/20 backdrop-blur-md">
                <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground mb-6 flex items-center gap-2">
                  <Gear className="w-4 h-4" /> Engine Configuration
                </h3>
                
                <Tabs value={selectedProvider} onValueChange={setSelectedProvider} className="space-y-6">
                  <TabsList className="grid grid-cols-4 bg-muted/10 p-1 rounded-xl h-12 border border-white/5">
                    {['revealIQ', 'cartesia', 'elevenLabs', 'sarvam'].map(p => (
                      <TabsTrigger key={p} value={p} className="text-[10px] uppercase font-bold tracking-wider data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white transition-all duration-300">
                        {p}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  <div className="space-y-6 pt-2">
                    {selectedProvider === 'revealIQ' && (
                      <>
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">Language Model</label>
                          <select
                            value={revealIQModel}
                            onChange={(e) => {
                              setRevealIQModel(e.target.value);
                              setRevealIQVoice(e.target.value === 'kokoro-en' ? 'af_heart' : 'hf_alpha');
                            }}
                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm focus:ring-2 focus:ring-[var(--k-brand)]/50 focus:outline-none transition-all appearance-none cursor-pointer"
                          >
                            <option value="kokoro-en" className="bg-[#1a1a1a] text-white">Swara-EN (English)</option>
                            <option value="kokoro-hi" className="bg-[#1a1a1a] text-white">Swara-HI (Hindi)</option>
                          </select>
                        </div>
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">Voice Personality</label>
                          <select
                            value={revealIQVoice}
                            onChange={(e) => setRevealIQVoice(e.target.value)}
                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm focus:ring-2 focus:ring-[var(--k-brand)]/50 focus:outline-none transition-all appearance-none cursor-pointer"
                          >
                            {revealIQVoices.map(voice => (
                              <option key={voice} value={voice} className="bg-[#1a1a1a] text-white">{voiceDisplayNames[voice] || voice}</option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}

                    {selectedProvider === 'cartesia' && (
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">Sonic Identity</label>
                        <select
                          value={cartesiaVoice}
                          onChange={(e) => setCartesiaVoice(e.target.value)}
                          className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm"
                        >
                          {ttsAPI.cartesia.getVoices().map(voice => (
                            <option key={voice.id} value={voice.id}>{voice.name}</option>
                          ))}
                        </select>
                      </div>
                    )}

                    {selectedProvider === 'elevenLabs' && (
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">Premium Narrator</label>
                        <select
                          value={elevenLabsVoiceId}
                          onChange={(e) => setElevenLabsVoiceId(e.target.value)}
                          className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm"
                        >
                          {ttsAPI.elevenLabs.getVoices().map(voice => (
                            <option key={voice.id} value={voice.id}>{voice.name}</option>
                          ))}
                        </select>
                      </div>
                    )}

                    {selectedProvider === 'sarvam' && (
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">Regional Language</label>
                        <select
                          value={sarvamLanguage}
                          onChange={(e) => setSarvamLanguage(e.target.value)}
                          className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm"
                        >
                          {ttsAPI.sarvam.getLanguages().map(lang => (
                            <option key={lang.id} value={lang.id}>{lang.name}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                </Tabs>
              </div>

              {/* Status Visualizer */}
              {loading && (
                <div className="p-8 rounded-2xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5 flex flex-col items-center justify-center space-y-4 animate-in fade-in zoom-in duration-300">
                  <div className="flex items-center gap-1">
                    {[...Array(6)].map((_, i) => (
                      <div 
                        key={i} 
                        className="w-1.5 h-8 bg-[var(--k-brand)] rounded-full animate-pulse" 
                        style={{ animationDelay: `${i * 100}ms`, height: `${16 + Math.random() * 24}px` }} 
                      />
                    ))}
                  </div>
                  <span className="text-xs font-bold uppercase tracking-widest text-[var(--k-brand)]">Neural Processing...</span>
                </div>
              )}
            </div>

            {/* Right: Input & Playback */}
            <div className="lg:col-span-7 space-y-6">
              <div className="relative group">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Type or paste the content you want to transform into high-fidelity speech..."
                  className="w-full h-[320px] p-8 text-xl bg-black/40 border border-white/5 rounded-3xl focus:ring-2 focus:ring-[var(--k-brand)]/30 focus:outline-none transition-all placeholder:text-muted-foreground/20 leading-relaxed shadow-inner font-light"
                />
                <div className="absolute bottom-6 right-8 text-[10px] font-mono text-muted-foreground/30 uppercase tracking-widest">
                  {text.length} Characters
                </div>
              </div>

              <div className="flex items-center gap-4">
                <button
                  onClick={handleSynthesize}
                  disabled={loading || !text.trim()}
                  className="flex-1 h-14 flex items-center justify-center gap-3 rounded-2xl bg-[var(--k-brand)] hover:bg-[var(--k-brand-hover)] text-white font-bold transition-all duration-300 shadow-lg shadow-[var(--k-brand)]/20 active:scale-[0.98] disabled:opacity-30 disabled:grayscale"
                >
                  {loading ? <Pulse className="w-6 h-6 animate-spin" /> : <Sparkle className="w-6 h-6" weight="fill" />}
                  <span className="uppercase tracking-widest text-sm">Generate Voice</span>
                </button>

                {audioUrl && (
                  <button
                    onClick={handleDownload}
                    className="w-14 h-14 flex items-center justify-center rounded-2xl border border-white/10 bg-white/5 hover:bg-white/10 text-white transition-all duration-300 active:scale-[0.95]"
                    title="Download WAV"
                  >
                    <Download className="w-6 h-6" />
                  </button>
                )}
              </div>

              {/* Custom Playback Bar */}
              {audioUrl && (
                <div className="p-6 rounded-3xl border border-white/5 bg-gradient-to-br from-white/10 to-transparent flex items-center gap-6 animate-in slide-in-from-bottom-4 duration-500">
                  <button 
                    onClick={handleTogglePlay}
                    className="w-14 h-14 rounded-full bg-white text-black flex items-center justify-center hover:scale-110 transition-transform active:scale-90"
                  >
                    {isPlaying ? <Pause className="w-6 h-6" weight="fill" /> : <Play className="w-6 h-6 ml-1" weight="fill" />}
                  </button>
                  
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-white/50 flex items-center gap-2">
                        <SpeakerHigh className="w-3 h-3" /> Master Output
                      </span>
                      <span className="text-[10px] font-mono text-white/40">HI-RES AUDIO</span>
                    </div>
                    <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                      <div 
                        className={`h-full bg-white transition-all duration-300 ${isPlaying ? 'w-full opacity-100' : 'w-1/3 opacity-50'}`}
                        style={{ transitionDuration: isPlaying ? '30s' : '0.5s' }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
