import { useState, useRef } from "react";
import { Play, Stop, VolumeHigh, Settings, Sparkle, Download } from "@phosphor-icons/react";
import { ttsAPI } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

export default function TextToSpeechStudio() {
  const [selectedProvider, setSelectedProvider] = useState('revealIQ');
  const [text, setText] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef(null);
  
  // RevealIQ specific
  const [revealIQModel, setRevealIQModel] = useState('kokoro-en');
  const [revealIQVoice, setRevealIQVoice] = useState('af_heart');
  const [revealIQSpeed, setRevealIQSpeed] = useState(1.0);
  
  // Cartesia specific
  const [cartesiaVoice, setCartesiaVoice] = useState('');
  
  // ElevenLabs specific
  const [elevenLabsVoiceId, setElevenLabsVoiceId] = useState('');
  
  // Sarvam specific
  const [sarvamLanguage, setSarvamLanguage] = useState('hi-IN');

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    
    try {
      setLoading(true);
      let audioBlob;
      
      switch (selectedProvider) {
        case 'revealIQ':
          audioBlob = await ttsAPI.revealIQ.synthesize(text, revealIQModel, revealIQVoice, revealIQSpeed);
          break;
        case 'cartesia':
          if (!cartesiaVoice) {
            alert('Please enter a voice ID');
            return;
          }
          audioBlob = await ttsAPI.cartesia.synthesize(text, cartesiaVoice);
          break;
        case 'elevenLabs':
          if (!elevenLabsVoiceId) {
            alert('Please enter a voice ID');
            return;
          }
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
      
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
        setIsPlaying(true);
      }
    } catch (error) {
      console.error('TTS synthesis failed:', error);
      alert('Failed to synthesize speech: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePlay = () => {
    if (audioRef.current && audioUrl) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        audioRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const handleDownload = () => {
    if (audioUrl) {
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = `tts-${selectedProvider}-${Date.now()}.wav`;
      a.click();
    }
  };

  const revealIQVoices = ttsAPI.revealIQ.getVoices(revealIQModel);

  // Voice display names mapping
  const voiceDisplayNames = {
    'af_heart': 'Priya Sharma',
    'af_bella': 'Ananya Singh',
    'af_nicole': 'Neha Kapoor',
    'af_sky': 'Sneha Reddy',
    'am_adam': 'Arjun Mehta',
    'am_michael': 'Rahul Verma',
    'hf_alpha': 'Aarav Kumar',
    'hf_beta': 'Vihaan Sharma',
  };

  // Model display names mapping
  const modelDisplayNames = {
    'kokoro-en': 'Swara-EN',
    'kokoro-hi': 'Swara-HI',
  };

  return (
    <div className="h-full" data-testid="tts-studio">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Text to Speech Studio</h1>
            <p className="text-sm text-muted-foreground mt-1">Synthesize speech with multiple TTS providers</p>
          </div>
        </div>
      </div>

      <ScrollArea className="h-[calc(100vh-120px)]">
        <div className="px-8 py-6 space-y-6">
          <Tabs value={selectedProvider} onValueChange={setSelectedProvider}>
            <TabsList className="bg-transparent h-10 p-0 gap-2 mb-6">
              <TabsTrigger value="revealIQ" className="bg-transparent data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white px-4 rounded-md text-sm">
                RevealIQ
              </TabsTrigger>
              <TabsTrigger value="cartesia" className="bg-transparent data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white px-4 rounded-md text-sm">
                Cartesia
              </TabsTrigger>
              <TabsTrigger value="elevenLabs" className="bg-transparent data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white px-4 rounded-md text-sm">
                ElevenLabs
              </TabsTrigger>
              <TabsTrigger value="sarvam" className="bg-transparent data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white px-4 rounded-md text-sm">
                Sarvam
              </TabsTrigger>
            </TabsList>

            {/* RevealIQ */}
            <TabsContent value="revealIQ" className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Model</label>
                  <select
                    value={revealIQModel}
                    onChange={(e) => {
                      setRevealIQModel(e.target.value);
                      setRevealIQVoice(e.target.value === 'kokoro-en' ? 'af_heart' : 'hf_alpha');
                    }}
                    className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                  >
                    <option value="kokoro-en">{modelDisplayNames['kokoro-en']}</option>
                    <option value="kokoro-hi">{modelDisplayNames['kokoro-hi']}</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Voice</label>
                  <select
                    value={revealIQVoice}
                    onChange={(e) => setRevealIQVoice(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                  >
                    {revealIQVoices.map(voice => (
                      <option key={voice} value={voice}>{voiceDisplayNames[voice] || voice}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Speed: {revealIQSpeed.toFixed(1)}x</label>
                  <input
                    type="range"
                    min="0.5"
                    max="2.0"
                    step="0.1"
                    value={revealIQSpeed}
                    onChange={(e) => setRevealIQSpeed(parseFloat(e.target.value))}
                    className="w-full"
                  />
                </div>
              </div>
              
              <div className="text-xs text-muted-foreground">
                <Sparkle className="w-3 h-3 inline mr-1" />
                Swara TTS engine based on Kokoro-82M. Configure API keys in Settings.
              </div>
            </TabsContent>

            {/* Cartesia */}
            <TabsContent value="cartesia" className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Voice ID</label>
                <input
                  type="text"
                  placeholder="e.g., 79a125e8-cd45-4c05-8747-8f8c6989182a"
                  value={cartesiaVoice}
                  onChange={(e) => setCartesiaVoice(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                />
              </div>
            </TabsContent>

            {/* ElevenLabs */}
            <TabsContent value="elevenLabs" className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Voice ID</label>
                <input
                  type="text"
                  placeholder="e.g., 21m00Tcm4TlvDq8ikWAM"
                  value={elevenLabsVoiceId}
                  onChange={(e) => setElevenLabsVoiceId(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                />
              </div>
            </TabsContent>

            {/* Sarvam */}
            <TabsContent value="sarvam" className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Language</label>
                <select
                  value={sarvamLanguage}
                  onChange={(e) => setSarvamLanguage(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                >
                  <option value="hi-IN">Hindi</option>
                  <option value="en-IN">English (India)</option>
                  <option value="ta-IN">Tamil</option>
                  <option value="te-IN">Telugu</option>
                  <option value="kn-IN">Kannada</option>
                  <option value="ml-IN">Malayalam</option>
                </select>
              </div>
            </TabsContent>
          </Tabs>

          {/* Text Input */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Text to Synthesize</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Enter text to synthesize..."
              rows={4}
              className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] resize-none"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSynthesize}
              disabled={loading || !text.trim()}
              className="flex items-center gap-2 px-6 py-2.5 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Sparkle className="w-4 h-4 animate-spin" />
                  Synthesizing...
                </>
              ) : (
                <>
                  <Sparkle className="w-4 h-4" />
                  Synthesize
                </>
              )}
            </button>
            
            {audioUrl && (
              <>
                <button
                  onClick={handlePlay}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-md border border-[var(--k-border)] text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200"
                >
                  {isPlaying ? <Stop className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  {isPlaying ? 'Stop' : 'Play'}
                </button>
                
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-md border border-[var(--k-border)] text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200"
                >
                  <Download className="w-4 h-4" />
                  Download
                </button>
              </>
            )}
          </div>

          {/* Audio Player */}
          {audioUrl && (
            <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
              <audio
                ref={audioRef}
                onEnded={() => setIsPlaying(false)}
                controls
                className="w-full"
              />
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
