import { useState } from "react";
import { X, Code, ChartBar, FileText, Copy, Download, ArrowsOutSimple } from "@phosphor-icons/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Area, AreaChart } from "recharts";

export function CanvasPane({ content, onClose, activeMode }) {
  const [activeTab, setActiveTab] = useState(content?.type === 'code' ? 'code' : content?.type === 'document' ? 'document' : 'dashboard');

  // Try to parse dynamic data from content.code if it's meant to be a dashboard/chart
  const getDynamicData = () => {
    if (!content?.code) return null;
    try {
      // If code starts with { or [, it might be JSON data for charts
      if (content.code.trim().startsWith('{') || content.code.trim().startsWith('[')) {
        return JSON.parse(content.code);
      }
    } catch (e) {
      return null;
    }
    return null;
  };

  const dynamicData = getDynamicData();
  const kpis = dynamicData?.kpis || [];
  const revenueData = dynamicData?.revenue || [];
  const salesByRegion = dynamicData?.salesByRegion || [];
  const funnelData = dynamicData?.conversionFunnel || [];

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
              {(!kpis || kpis.length === 0) && (!revenueData || revenueData.length === 0) ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <ChartBar className="w-12 h-12 text-muted-foreground/20 mb-4" />
                  <p className="text-sm text-muted-foreground">No dashboard data generated for this query</p>
                  <p className="text-[10px] text-muted-foreground/60 mt-1 max-w-[200px]">Ask the assistant to generate a report or visualize data.</p>
                </div>
              ) : (
                <>
                  {/* KPIs */}
                  {kpis.length > 0 && (
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {kpis.map((kpi, i) => (
                        <div key={i} className="p-3 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                          <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold truncate">{kpi.label}</div>
                          <div className="text-xl font-medium k-heading tracking-tight text-foreground mt-1 truncate">{kpi.value}</div>
                          {kpi.change && (
                            <div className={`text-xs font-medium mt-0.5 ${kpi.positive ? 'text-[var(--k-green)]' : 'text-red-400'}`}>
                              {kpi.change}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Revenue Chart */}
                  {revenueData.length > 0 && (
                    <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                      <div className="text-xs font-semibold text-foreground mb-3 k-heading">Trend Analysis</div>
                      <ResponsiveContainer width="100%" height={200}>
                        <AreaChart data={revenueData}>
                          <defs>
                            <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="var(--k-brand)" stopOpacity={0.1}/>
                              <stop offset="95%" stopColor="var(--k-brand)" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" vertical={false} />
                          <XAxis dataKey="label" hide={false} tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                          <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                          <Area type="monotone" dataKey="value" stroke="var(--k-brand)" strokeWidth={2} fill="url(#colorRevenue)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Sales by Region */}
                  {salesByRegion.length > 0 && (
                    <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                      <div className="text-xs font-semibold text-foreground mb-3 k-heading">Distribution</div>
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={salesByRegion}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" vertical={false} />
                          <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                          <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                            {salesByRegion.map((entry, index) => (
                              <Cell key={index} fill={entry.fill || "var(--k-brand)"} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Funnel */}
                  {funnelData.length > 0 && (
                    <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                      <div className="text-xs font-semibold text-foreground mb-3 k-heading">Funnel Analysis</div>
                      <div className="space-y-2">
                        {funnelData.map((stage, i) => {
                          const width = (stage.value / funnelData[0].value) * 100;
                          return (
                            <div key={i} className="flex items-center gap-3">
                              <span className="text-[10px] text-muted-foreground w-20 text-right truncate">{stage.stage}</span>
                              <div className="flex-1 h-7 bg-[var(--k-surface-elevated)] rounded-sm overflow-hidden">
                                <div
                                  className="h-full bg-[var(--k-brand)] rounded-sm flex items-center justify-end pr-2 transition-all duration-500"
                                  style={{ width: `${width}%`, opacity: 1 - (i * 0.1) }}
                                >
                                  <span className="text-[10px] text-white font-medium">{stage.value}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
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
                {content?.code && !dynamicData ? (
                  <div className="whitespace-pre-wrap font-sans text-foreground leading-relaxed">
                    {content.code}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <FileText className="w-12 h-12 text-muted-foreground/20 mb-4" />
                    <p className="text-sm text-muted-foreground">No document content generated</p>
                  </div>
                )}
              </div>
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
