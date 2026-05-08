import { useState } from "react";
import { X, Code, ChartBar, FileText, Copy, Download, ArrowsOutSimple } from "@phosphor-icons/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { mockArtifactCode, mockBIData } from "@/lib/mockData";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, Area, AreaChart } from "recharts";

export function CanvasPane({ content, onClose, activeMode }) {
  const [activeTab, setActiveTab] = useState(content?.type === 'code' ? 'code' : 'dashboard');

  return (
    <div className="canvas-pane flex flex-col" data-testid="canvas-pane">
      {/* Header */}
      <div className="h-12 min-h-[48px] flex items-center justify-between px-4 border-b border-[var(--k-border)]">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium k-heading tracking-tight text-foreground">
            {content?.title || 'Canvas'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button data-testid="copy-canvas-btn" className="p-1.5 rounded-md hover:bg-accent transition-colors" title="Copy">
            <Copy className="w-3.5 h-3.5 text-muted-foreground" />
          </button>
          <button data-testid="download-canvas-btn" className="p-1.5 rounded-md hover:bg-accent transition-colors" title="Download">
            <Download className="w-3.5 h-3.5 text-muted-foreground" />
          </button>
          <button data-testid="close-canvas-btn" onClick={onClose} className="p-1.5 rounded-md hover:bg-accent transition-colors">
            <X className="w-3.5 h-3.5 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
        <div className="px-4 pt-2 border-b border-[var(--k-border)]">
          <TabsList className="bg-transparent h-9 p-0 gap-4">
            <TabsTrigger
              value="dashboard"
              data-testid="canvas-tab-dashboard"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground text-muted-foreground px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium"
            >
              <ChartBar className="w-3.5 h-3.5 mr-1.5" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger
              value="code"
              data-testid="canvas-tab-code"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground text-muted-foreground px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium"
            >
              <Code className="w-3.5 h-3.5 mr-1.5" />
              Code
            </TabsTrigger>
            <TabsTrigger
              value="document"
              data-testid="canvas-tab-document"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground text-muted-foreground px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium"
            >
              <FileText className="w-3.5 h-3.5 mr-1.5" />
              Document
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="dashboard" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full">
            <div className="p-4 space-y-4">
              {(!mockBIData.kpis || mockBIData.kpis.length === 0) ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <ChartBar className="w-12 h-12 text-muted-foreground/20 mb-4" />
                  <p className="text-sm text-muted-foreground">No dashboard data available for this artifact</p>
                </div>
              ) : (
                <>
                  {/* KPIs */}
                  <div className="grid grid-cols-3 gap-3">
                    {mockBIData.kpis.slice(0, 3).map((kpi, i) => (
                      <div key={i} className="p-3 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]" data-testid={`canvas-kpi-${i}`}>
                        <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold">{kpi.label}</div>
                        <div className="text-xl font-medium k-heading tracking-tight text-foreground mt-1">{kpi.value}</div>
                        <div className={`text-xs font-medium mt-0.5 ${kpi.positive ? 'text-[var(--k-green)]' : 'text-red-400'}`}>{kpi.change}</div>
                      </div>
                    ))}
                  </div>

                  {/* Revenue Chart */}
                  <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                    <div className="text-xs font-semibold text-foreground mb-3 k-heading">Revenue Trend</div>
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={mockBIData.revenue}>
                        <defs>
                          <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#0052FF" stopOpacity={0.1}/>
                            <stop offset="95%" stopColor="#0052FF" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                        <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                        <Area type="monotone" dataKey="value" stroke="#0052FF" strokeWidth={2} fill="url(#colorRevenue)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Sales by Region */}
                  <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                    <div className="text-xs font-semibold text-foreground mb-3 k-heading">Sales by Region</div>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={mockBIData.salesByRegion}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                        <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                        <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                          {mockBIData.salesByRegion.map((entry, index) => (
                            <Cell key={index} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Funnel */}
                  <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                    <div className="text-xs font-semibold text-foreground mb-3 k-heading">Conversion Funnel</div>
                    <div className="space-y-2">
                      {mockBIData.conversionFunnel.map((stage, i) => {
                        const width = (stage.value / mockBIData.conversionFunnel[0].value) * 100;
                        return (
                          <div key={i} className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground w-20 text-right">{stage.stage}</span>
                            <div className="flex-1 h-7 bg-[var(--k-surface-elevated)] rounded-sm overflow-hidden">
                              <div
                                className="h-full bg-[var(--k-brand)] rounded-sm flex items-center justify-end pr-2 transition-all duration-500"
                                style={{ width: `${width}%`, opacity: 1 - (i * 0.15) }}
                              >
                                <span className="text-[10px] text-white font-medium">{stage.value}</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="code" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full">
            <div className="p-4">
              <div className="canvas-code-block">
                <pre className="text-[13px] leading-relaxed">
                  <code>{content?.code || "No code available"}</code>
                </pre>
              </div>
              {content?.code && (
                <div className="mt-4 p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-[var(--k-green)]" />
                    <span className="text-xs font-medium text-[var(--k-green)]">Execution Ready</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Click run to execute this script in the interpreter.</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="document" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full">
            <div className="p-6 max-w-none">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <h1 className="text-2xl font-medium k-heading tracking-tight">Q3 Revenue Analysis Report</h1>
                <p className="text-xs text-muted-foreground mb-6">Generated by Kautilya AI | October 2025</p>
                <h2 className="text-lg font-medium k-heading tracking-tight mt-6">Executive Summary</h2>
                <p className="text-sm leading-relaxed text-foreground">
                  Q3 2025 demonstrated strong revenue growth of 23% quarter-over-quarter, reaching INR 4.2 Crores.
                  The growth was primarily driven by expansion in Maharashtra and Karnataka markets, with enterprise
                  segment showing the highest average deal size increase of 15%.
                </p>
                <h2 className="text-lg font-medium k-heading tracking-tight mt-6">Key Findings</h2>
                <ul className="text-sm space-y-2">
                  <li>Win rate improved to 34%, exceeding industry average of 28%</li>
                  <li>Average deal size grew to INR 2.8L from INR 2.4L in Q2</li>
                  <li>Customer acquisition cost decreased by 12%</li>
                  <li>Net Revenue Retention (NRR) stands at 124%</li>
                </ul>
                <h2 className="text-lg font-medium k-heading tracking-tight mt-6">Recommendations</h2>
                <ol className="text-sm space-y-2">
                  <li>Increase headcount in Maharashtra region by 3 reps</li>
                  <li>Launch enterprise tier targeting Delhi NCR segment</li>
                  <li>Implement partner channel program for Gujarat expansion</li>
                </ol>
              </div>
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
