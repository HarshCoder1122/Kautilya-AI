import { useState } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import {
  Robot, Users, Megaphone, Phone, ChartBar, ChatCircleDots,
  Gear, SignOut, CaretLeft, SpeakerHigh
} from "@phosphor-icons/react";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { ScrollArea } from "@/components/ui/scroll-area";
import { logout } from "../lib/firebase";
import { UserCircle } from "@phosphor-icons/react";
import AgentStudio from "@/components/dashboard/AgentStudio";
import LeadManagement from "@/components/dashboard/LeadManagement";
import CampaignDialer from "@/components/dashboard/CampaignDialer";
import CallAnalytics from "@/components/dashboard/CallAnalytics";
import BIAnalytics from "@/components/dashboard/BIAnalytics";
import WidgetPreview from "@/components/dashboard/WidgetPreview";
import TextToSpeechStudio from "@/components/dashboard/TextToSpeechStudio";
import UserSettings from "@/components/dashboard/UserSettings";

const navItems = [
  { id: 'agents', label: 'Agent Studio', icon: Robot, path: '/dashboard' },
  { id: 'leads', label: 'Leads', icon: Users, path: '/dashboard/leads' },
  { id: 'campaigns', label: 'Campaigns', icon: Megaphone, path: '/dashboard/campaigns' },
  { id: 'calls', label: 'Call Analytics', icon: Phone, path: '/dashboard/calls' },
  { id: 'analytics', label: 'BI Analytics', icon: ChartBar, path: '/dashboard/analytics' },
  { id: 'widgets', label: 'Widgets', icon: ChatCircleDots, path: '/dashboard/widgets' },
  { id: 'tts', label: 'TTS Studio', icon: SpeakerHigh, path: '/dashboard/tts' },
  { id: 'settings', label: 'Settings', icon: Gear, path: '/dashboard/settings' },
];

export default function DashboardPage({ theme, toggleTheme, user }) {
  const navigate = useNavigate();
  const location = useLocation();

  const activeItem = navItems.find(item =>
    item.path === location.pathname
  ) || navItems[0];

  return (
    <div className="dashboard-layout" data-testid="dashboard-page">
      {/* Sidebar */}
      <div className="dashboard-sidebar" data-testid="dashboard-sidebar">
        {/* Logo */}
        <div className="p-4 flex items-center justify-between border-b border-[var(--k-border)]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-[var(--k-brand)] flex items-center justify-center">
              <span className="text-white text-xs font-bold k-heading">K</span>
            </div>
            <div>
              <span className="text-sm font-semibold k-heading tracking-tight text-foreground">Kautilya</span>
              <span className="text-[10px] text-muted-foreground ml-1">Dashboard</span>
            </div>
          </div>
          <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
        </div>

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
                onClick={() => navigate(item.path)}
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
            onClick={() => navigate('/')}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors text-sm"
          >
            <CaretLeft className="w-4 h-4" />
            <span>Back to Chat</span>
          </button>
          <button
            data-testid="settings-btn"
            onClick={() => navigate('/dashboard/settings')}
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
        <Routes>
          <Route index element={<AgentStudio />} />
          <Route path="leads" element={<LeadManagement />} />
          <Route path="campaigns" element={<CampaignDialer />} />
          <Route path="calls" element={<CallAnalytics />} />
          <Route path="analytics" element={<BIAnalytics />} />
          <Route path="widgets" element={<WidgetPreview />} />
          <Route path="tts" element={<TextToSpeechStudio />} />
          <Route path="settings" element={<UserSettings user={user} />} />
        </Routes>
      </div>
    </div>
  );
}
