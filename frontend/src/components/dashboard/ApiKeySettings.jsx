import { useState, useEffect } from "react";
import { Key, Save, Trash, Eye, EyeSlash, Plus, CheckCircle } from "@phosphor-icons/react";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function ApiKeySettings() {
  const [apiKeys, setApiKeys] = useState({});
  const [showKeys, setShowKeys] = useState({});
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    loadApiKeys();
  }, []);

  const loadApiKeys = () => {
    const saved = localStorage.getItem('api_keys');
    if (saved) {
      setApiKeys(JSON.parse(saved));
    }
  };

  const saveApiKeys = (keys) => {
    localStorage.setItem('api_keys', JSON.stringify(keys));
    setApiKeys(keys);
    showNotification('API keys saved successfully');
  };

  const showNotification = (message) => {
    setNotification(message);
    setTimeout(() => setNotification(null), 3000);
  };

  const handleSaveKey = (provider, key) => {
    const newKeys = { ...apiKeys, [provider]: key };
    saveApiKeys(newKeys);
  };

  const handleDeleteKey = (provider) => {
    const newKeys = { ...apiKeys };
    delete newKeys[provider];
    saveApiKeys(newKeys);
  };

  const toggleShowKey = (provider) => {
    setShowKeys(prev => ({ ...prev, [provider]: !prev[provider] }));
  };

  const providers = [
    { id: 'revealIQ', name: 'RevealIQ (Hugging Face)', description: 'Kokoro TTS engine for English and Hindi', icon: '🎤' },
    { id: 'cartesia', name: 'Cartesia', description: 'High-quality neural TTS', icon: '🎵' },
    { id: 'elevenLabs', name: 'ElevenLabs', description: 'Premium AI voice synthesis', icon: '🔊' },
    { id: 'sarvam', name: 'Sarvam AI', description: 'Indian language TTS', icon: '🇮🇳' },
    { id: 'openai', name: 'OpenAI', description: 'GPT models and TTS', icon: '🤖' },
    { id: 'groq', name: 'Groq', description: 'Fast inference API', icon: '⚡' },
  ];

  return (
    <div className="h-full" data-testid="api-key-settings">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">API Key Settings</h1>
            <p className="text-sm text-muted-foreground mt-1">Configure your API keys for external services</p>
          </div>
        </div>
      </div>

      {notification && (
        <div className="mx-8 mt-4 px-4 py-2 rounded-md bg-[var(--k-green)]/10 border border-[var(--k-green)]/20 text-[var(--k-green)] text-sm flex items-center gap-2">
          <CheckCircle className="w-4 h-4" />
          {notification}
        </div>
      )}

      <ScrollArea className="h-[calc(100vh-180px)]">
        <div className="px-8 py-6 space-y-6">
          <div className="text-xs text-muted-foreground mb-4">
            <Key className="w-3 h-3 inline mr-1" />
            API keys are stored locally in your browser. Never share your API keys with others.
          </div>

          <div className="space-y-4">
            {providers.map((provider) => {
              const hasKey = apiKeys[provider.id];
              const isVisible = showKeys[provider.id];
              return (
                <div key={provider.id} className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{provider.icon}</span>
                      <div>
                        <div className="text-sm font-medium text-foreground">{provider.name}</div>
                        <div className="text-xs text-muted-foreground">{provider.description}</div>
                      </div>
                    </div>
                    {hasKey && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleShowKey(provider.id)}
                          className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                          title={isVisible ? 'Hide key' : 'Show key'}
                        >
                          {isVisible ? <EyeSlash className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                        <button
                          onClick={() => handleDeleteKey(provider.id)}
                          className="p-1.5 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors"
                          title="Delete key"
                        >
                          <Trash className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <input
                      type={isVisible ? 'text' : 'password'}
                      placeholder={`Enter ${provider.name} API key`}
                      value={apiKeys[provider.id] || ''}
                      onChange={(e) => {
                        const newKeys = { ...apiKeys, [provider.id]: e.target.value };
                        setApiKeys(newKeys);
                      }}
                      className="flex-1 px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                    />
                    <button
                      onClick={() => handleSaveKey(provider.id, apiKeys[provider.id])}
                      className="flex items-center gap-2 px-4 py-2 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200"
                    >
                      <Save className="w-4 h-4" />
                      Save
                    </button>
                  </div>

                  {hasKey && (
                    <div className="mt-2 text-xs text-[var(--k-green)] flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" />
                      API key configured
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Usage Tracking Section */}
          <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
            <div className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <Key className="w-4 h-4 text-[var(--k-brand)]" />
              Usage Tracking
            </div>
            <div className="text-xs text-muted-foreground space-y-2">
              <p>API usage is tracked per provider based on your configured keys:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>RevealIQ: TTS synthesis calls</li>
                <li>Cartesia: Voice synthesis requests</li>
                <li>ElevenLabs: Character usage</li>
                <li>Sarvam: API calls and duration</li>
              </ul>
              <p className="mt-2">View detailed usage in the Analytics section.</p>
            </div>
          </div>

          {/* Security Note */}
          <div className="p-4 rounded-md border border-[var(--k-yellow)]/30 bg-[var(--k-yellow)]/5">
            <div className="text-xs text-[var(--k-yellow)]">
              <strong>Security Note:</strong> API keys are stored in localStorage for convenience. 
              For production deployments, consider using environment variables or a secure key management service.
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
