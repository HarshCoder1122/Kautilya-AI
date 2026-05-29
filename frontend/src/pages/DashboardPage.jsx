import { useState } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import {
  Robot, Users, Megaphone, Phone, ChartBar, ChatCircleDots,
  Gear, SignOut, CaretLeft, SpeakerHigh, PlugsConnected, Terminal, List, CreditCard
} from "@phosphor-icons/react";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { ScrollArea } from "@/components/ui/scroll-area";
import { logout } from "../lib/firebase";
import { UserCircle } from "@phosphor-icons/react";
import AgentStudio, { AgentDetailPage } from "@/components/dashboard/AgentStudio";
import UsagePage from "@/components/dashboard/UsagePage";
import LeadManagement from "@/components/dashboard/LeadManagement";
import CampaignDialer from "@/components/dashboard/CampaignDialer";
import CallAnalytics from "@/components/dashboard/CallAnalytics";
import BIAnalytics from "@/components/dashboard/BIAnalytics";
import WidgetPreview from "@/components/dashboard/WidgetPreview";
import TextToSpeechStudio from "@/components/dashboard/TextToSpeechStudio";
import UserSettings from "@/components/dashboard/UserSettings";
import Integrations from "@/components/dashboard/Integrations";
import DeveloperAPI from "@/components/dashboard/DeveloperAPI";
import Billing from "@/components/dashboard/Billing";

const navItems = [
  { id: 'agents', label: 'Agent Studio', icon: Robot, path: '/dashboard' },
  { id: 'leads', label: 'Leads', icon: Users, path: '/dashboard/leads' },
  { id: 'campaigns', label: 'Campaigns', icon: Megaphone, path: '/dashboard/campaigns' },
  { id: 'calls', label: 'Call Analytics', icon: Phone, path: '/dashboard/calls' },
  { id: 'analytics', label: 'BI Analytics', icon: ChartBar, path: '/dashboard/analytics' },
  { id: 'widgets', label: 'Widgets', icon: ChatCircleDots, path: '/dashboard/widgets' },
  { id: 'tts', label: 'TTS Studio', icon: SpeakerHigh, path: '/dashboard/tts' },
  { id: 'integrations', label: 'Integrations', icon: PlugsConnected, path: '/dashboard/integrations' },
  { id: 'api', label: 'Developer API', icon: Terminal, path: '/dashboard/api' },
  { id: 'billing', label: 'Billing', icon: CreditCard, path: '/dashboard/billing' },
  { id: 'usage', label: 'Usage', icon: ChartBar, path: '/dashboard/usage' },
];

export default function DashboardPage({ theme, toggleTheme, user }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const activeItem = navItems.find(item =>
    item.path === location.pathname
  ) || navItems[0];

  const handleNavClick = (path) => {
    navigate(path);
    setMobileSidebarOpen(false);
  };

  return (
    <div className="dashboard-layout" data-testid="dashboard-page">
      {/* Mobile overlay */}
      <div className={`sidebar-overlay ${mobileSidebarOpen ? 'active' : ''}`} onClick={() => setMobileSidebarOpen(false)} />

      {/* Sidebar */}
      <div className={`dashboard-sidebar ${mobileSidebarOpen ? 'open' : ''}`} data-testid="dashboard-sidebar">
        {/* Logo */}
        <div className="p-4 flex items-center justify-between border-b border-[var(--k-border)]">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="Kautilya Logo" className="w-7 h-7 object-contain" />
            <div>
              <span className="text-sm font-semibold k-heading tracking-tight text-foreground">Kautilya</span>
              <span className="text-[10px] text-muted-foreground ml-1">Dashboard</span>
            </div>
          </div>
          <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
        </div>

        {/* Mobile close button area — tap outside closes sidebar via overlay */}

        {/* Navigation */}
        <ScrollArea className="flex-1 py-3">
          <div className="px-3 mb-2">
            <span className="px-2 text-[10px] tracking-[0.2em] uppercase font-semibold text-muted-foreground">Management</span>
          </div>
          <div className="px-2 space-y-0.5">
            {navItems.map((item) => (
              <button
                key={item.id}
                data-testid={`nav-${item.id}`}
                onClick={() => handleNavClick(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-200 text-left ${
                  activeItem.id === item.id
                    ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)]'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                }`}
              >
                <item.icon className="w-4 h-4" weight={activeItem.id === item.id ? 'duotone' : 'regular'} />
                <span className="text-sm font-medium">{item.label}</span>
              </button>
            ))}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="p-3 border-t border-[var(--k-border)] space-y-0.5">
          <button
            data-testid="back-to-chat-btn"
            onClick={() => { navigate('/'); setMobileSidebarOpen(false); }}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors text-sm"
          >
            <CaretLeft className="w-4 h-4" />
            <span>Back to Chat</span>
          </button>
          <button
            data-testid="settings-btn"
            onClick={() => handleNavClick('/dashboard/settings')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors text-sm ${
              activeItem.id === 'settings'
                ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)]'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            }`}
          >
            <Gear className="w-4 h-4" />
            <span>Settings</span>
          </button>
          <button
            data-testid="sign-out-btn"
            onClick={() => logout()}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-muted-foreground hover:bg-rose-500/10 hover:text-rose-400 transition-colors text-sm"
          >
            <SignOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>

          <div className="pt-2 px-1">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-white/5 border border-white/5 overflow-hidden">
              {user?.photoURL ? (
                <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full" />
              ) : (
                <UserCircle className="w-7 h-7 text-muted-foreground" />
              )}
              <div className="overflow-hidden">
                <div className="text-[10px] font-medium truncate text-foreground">{user?.displayName || 'User'}</div>
                <div className="text-[9px] truncate text-muted-foreground">{user?.email}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="dashboard-content" data-testid="dashboard-content">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-[var(--k-border)] bg-[var(--k-surface)] sticky top-0 z-20">
          <button
            onClick={() => setMobileSidebarOpen(true)}
            className="p-2 rounded-md hover:bg-accent transition-colors"
          >
            <List className="w-5 h-5 text-muted-foreground" />
          </button>
          <span className="text-sm font-semibold k-heading text-foreground">{activeItem.label}</span>
        </div>
        <Routes>
          <Route index element={<AgentStudio />} />
          <Route path="agents/:agentId" element={<AgentDetailPage />} />
          <Route path="leads" element={<LeadManagement />} />
          <Route path="campaigns" element={<CampaignDialer />} />
          <Route path="calls" element={<CallAnalytics />} />
          <Route path="analytics" element={<BIAnalytics />} />
          <Route path="widgets" element={<WidgetPreview />} />
          <Route path="tts" element={<TextToSpeechStudio />} />
          <Route path="integrations" element={<Integrations />} />
          <Route path="api" element={<DeveloperAPI />} />
          <Route path="billing" element={<Billing user={user} />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="settings" element={<UserSettings user={user} />} />
        </Routes>
      </div>
    </div>
  );
}
