// Mock data for Kautilya AI UI

export const mockConversations = [
  {
    id: 'conv-1',
    title: 'Q3 Revenue Analysis',
    lastMessage: 'The revenue trend shows a 23% increase...',
    timestamp: '2 min ago',
    agent: 'researcher',
  },
  {
    id: 'conv-2',
    title: 'Sales Pitch for TechCorp',
    lastMessage: 'Here is the customized pitch deck...',
    timestamp: '1 hour ago',
    agent: 'sales',
  },
  {
    id: 'conv-3',
    title: 'Data Pipeline Script',
    lastMessage: 'I have created the ETL pipeline...',
    timestamp: '3 hours ago',
    agent: 'coder',
  },
  {
    id: 'conv-4',
    title: 'Market Research - Fintech',
    lastMessage: 'Based on 47 sources analyzed...',
    timestamp: 'Yesterday',
    agent: 'researcher',
  },
  {
    id: 'conv-5',
    title: 'Customer Churn Analysis',
    lastMessage: 'The predictive model suggests...',
    timestamp: 'Yesterday',
    agent: 'researcher',
  },
];

export const mockMessages = [
  {
    id: 'msg-1',
    role: 'user',
    content: 'Analyze our Q3 sales data and create a revenue forecast for Q4. Also identify our top-performing regions.',
    timestamp: '10:30 AM',
  },
  {
    id: 'msg-2',
    role: 'assistant',
    content: '',
    thinking: 'Analyzing the uploaded sales data... Identifying revenue patterns across regions... Running ARIMA model for Q4 forecast... Cross-referencing with market trends...',
    thinkingDone: true,
    timestamp: '10:31 AM',
    agentType: 'researcher',
    responseText: `## Q3 Revenue Analysis & Q4 Forecast

Based on my analysis of your sales data, here are the key findings:

### Revenue Summary
- **Total Q3 Revenue**: INR 4.2 Cr (up 23% from Q2)
- **Average Deal Size**: INR 2.8L (up 15%)
- **Win Rate**: 34% (industry avg: 28%)

### Top Performing Regions
1. **Maharashtra** — INR 1.1 Cr (26% of total)
2. **Karnataka** — INR 89L (21% of total)
3. **Delhi NCR** — INR 72L (17% of total)

### Q4 Forecast
Using ARIMA modeling with seasonal adjustments, the projected Q4 revenue is **INR 4.8-5.2 Cr**, representing a potential **14-24% growth**.

### Key Recommendations
- Double down on Maharashtra with dedicated sales reps
- Karnataka shows highest growth velocity — expand team there
- Consider launching enterprise tier targeting Delhi NCR`,
    citations: [
      { id: 1, title: 'Industry Benchmark Report 2025', url: '#', source: 'McKinsey' },
      { id: 2, title: 'India SaaS Market Analysis', url: '#', source: 'Nasscom' },
      { id: 3, title: 'Regional Economic Indicators', url: '#', source: 'RBI Data' },
    ],
    hasArtifact: true,
    artifactType: 'chart',
  },
];

export const mockAgents = [
  {
    id: 'agent-1',
    name: 'Sales Assistant',
    type: 'sales',
    status: 'active',
    description: 'Handles lead qualification, pitch generation, and follow-up automation',
    voice: 'Priya (Hindi)',
    model: 'Llama 3.3 70B',
    callsHandled: 342,
    avgScore: 4.2,
    systemPrompt: 'You are a professional sales assistant specializing in B2B SaaS sales for the Indian market. Speak in Hinglish when appropriate.',
  },
  {
    id: 'agent-2',
    name: 'Support Agent',
    type: 'support',
    status: 'active',
    description: 'Customer support with product knowledge base and escalation logic',
    voice: 'Rahul (Hindi)',
    model: 'Llama 3.3 70B',
    callsHandled: 1205,
    avgScore: 4.5,
    systemPrompt: 'You are a helpful customer support agent. Always be empathetic and solution-oriented.',
  },
  {
    id: 'agent-3',
    name: 'Lead Qualifier',
    type: 'qualifier',
    status: 'paused',
    description: 'Outbound qualifier that scores leads based on BANT framework',
    voice: 'Ananya (Hindi)',
    model: 'Nemotron Pro',
    callsHandled: 89,
    avgScore: 3.8,
    systemPrompt: 'You are a lead qualification specialist. Use the BANT framework to qualify leads.',
  },
];

export const mockLeads = [
  { id: 'lead-1', name: 'Rajesh Kumar', company: 'TechServe India', email: 'rajesh@techserve.in', phone: '+91 98765 43210', score: 92, status: 'hot', source: 'Campaign', lastContact: '2 hours ago', value: '12L' },
  { id: 'lead-2', name: 'Priya Sharma', company: 'FinEdge Solutions', email: 'priya@finedge.co', phone: '+91 87654 32109', score: 78, status: 'warm', source: 'Website', lastContact: '1 day ago', value: '8.5L' },
  { id: 'lead-3', name: 'Amit Patel', company: 'CloudNine Labs', email: 'amit@cloudnine.io', phone: '+91 76543 21098', score: 65, status: 'warm', source: 'Referral', lastContact: '3 days ago', value: '15L' },
  { id: 'lead-4', name: 'Sneha Reddy', company: 'DataPulse AI', email: 'sneha@datapulse.ai', phone: '+91 65432 10987', score: 45, status: 'cold', source: 'Campaign', lastContact: '1 week ago', value: '6L' },
  { id: 'lead-5', name: 'Vikram Singh', company: 'MetroRetail', email: 'vikram@metroretail.in', phone: '+91 54321 09876', score: 88, status: 'hot', source: 'Inbound Call', lastContact: '5 hours ago', value: '22L' },
  { id: 'lead-6', name: 'Anita Desai', company: 'GreenTech Power', email: 'anita@greentech.co.in', phone: '+91 43210 98765', score: 71, status: 'warm', source: 'Website', lastContact: '2 days ago', value: '9L' },
];

export const mockCampaigns = [
  { id: 'camp-1', name: 'Q4 Enterprise Push', status: 'running', agent: 'Sales Assistant', totalLeads: 450, contacted: 312, connected: 198, converted: 45, startDate: '2025-10-01', schedule: 'Mon-Fri, 10AM-6PM' },
  { id: 'camp-2', name: 'Renewal Reminder', status: 'scheduled', agent: 'Support Agent', totalLeads: 120, contacted: 0, connected: 0, converted: 0, startDate: '2025-11-15', schedule: 'Mon-Sat, 9AM-5PM' },
  { id: 'camp-3', name: 'Fintech Outreach', status: 'completed', agent: 'Lead Qualifier', totalLeads: 200, contacted: 200, connected: 156, converted: 34, startDate: '2025-09-01', schedule: 'Mon-Fri, 11AM-7PM' },
];

export const mockCalls = [
  { id: 'call-1', leadName: 'Rajesh Kumar', company: 'TechServe India', duration: '4:32', sentiment: 'positive', score: 92, summary: 'Interested in enterprise plan. Requested demo for next week. Budget approved.', actionItems: ['Schedule demo', 'Send pricing doc'], agent: 'Sales Assistant', date: '2025-10-28 10:30 AM' },
  { id: 'call-2', leadName: 'Priya Sharma', company: 'FinEdge Solutions', duration: '6:15', sentiment: 'neutral', score: 78, summary: 'Evaluating multiple vendors. Needs compliance documentation. Follow up in 2 weeks.', actionItems: ['Send compliance docs', 'Follow up Nov 12'], agent: 'Sales Assistant', date: '2025-10-28 11:45 AM' },
  { id: 'call-3', leadName: 'Vikram Singh', company: 'MetroRetail', duration: '3:48', sentiment: 'positive', score: 88, summary: 'Ready to sign. Negotiating annual discount. Decision by Friday.', actionItems: ['Prepare contract', 'Apply 15% annual discount'], agent: 'Lead Qualifier', date: '2025-10-27 3:20 PM' },
  { id: 'call-4', leadName: 'Sneha Reddy', company: 'DataPulse AI', duration: '2:10', sentiment: 'negative', score: 45, summary: 'Not in buying cycle. Budget allocated elsewhere. Revisit in Q2.', actionItems: ['Add to Q2 pipeline', 'Send case study'], agent: 'Sales Assistant', date: '2025-10-27 4:00 PM' },
];

export const mockBIData = {
  revenue: [
    { month: 'Apr', value: 28 },
    { month: 'May', value: 32 },
    { month: 'Jun', value: 35 },
    { month: 'Jul', value: 38 },
    { month: 'Aug', value: 42 },
    { month: 'Sep', value: 48 },
    { month: 'Oct', value: 52 },
  ],
  salesByRegion: [
    { name: 'Maharashtra', value: 110, fill: '#0052FF' },
    { name: 'Karnataka', value: 89, fill: '#2563EB' },
    { name: 'Delhi NCR', value: 72, fill: '#10B981' },
    { name: 'Tamil Nadu', value: 58, fill: '#F59E0B' },
    { name: 'Gujarat', value: 45, fill: '#8B5CF6' },
  ],
  kpis: [
    { label: 'Total Revenue', value: 'INR 4.2 Cr', change: '+23%', positive: true },
    { label: 'Active Deals', value: '47', change: '+12', positive: true },
    { label: 'Win Rate', value: '34%', change: '+6%', positive: true },
    { label: 'Avg Deal Size', value: 'INR 2.8L', change: '+15%', positive: true },
    { label: 'Pipeline Value', value: 'INR 8.9 Cr', change: '+31%', positive: true },
    { label: 'Churn Rate', value: '2.1%', change: '-0.8%', positive: true },
  ],
  conversionFunnel: [
    { stage: 'Leads', value: 1200 },
    { stage: 'Qualified', value: 480 },
    { stage: 'Proposal', value: 192 },
    { stage: 'Negotiation', value: 96 },
    { stage: 'Closed Won', value: 47 },
  ],
};

export const mockArtifactCode = `import pandas as pd
import matplotlib.pyplot as plt

# Load and analyze sales data
df = pd.read_csv('sales_q3.csv')

# Revenue by region
regional = df.groupby('region')['revenue'].sum().sort_values(ascending=False)
print("Top Regions by Revenue:")
print(regional.head())

# Monthly trend
monthly = df.groupby('month')['revenue'].sum()

# Forecast using simple moving average
from statsmodels.tsa.arima.model import ARIMA
model = ARIMA(monthly, order=(1,1,1))
results = model.fit()
forecast = results.forecast(steps=3)
print(f"\\nQ4 Forecast: INR {forecast.sum():.1f}L")`;

export const mockResearchSources = [
  { id: 1, title: 'India SaaS Report 2025', source: 'Nasscom', url: '#', snippet: 'Indian SaaS companies are projected to reach $50B in revenue by 2030...' },
  { id: 2, title: 'SME Digital Transformation', source: 'McKinsey', url: '#', snippet: 'Over 63 million SMEs in India are adopting digital-first strategies...' },
  { id: 3, title: 'AI Adoption in Indian Enterprises', source: 'Deloitte', url: '#', snippet: '78% of Indian enterprises plan to increase AI spending in 2025...' },
  { id: 4, title: 'Regional Economic Indicators Q3', source: 'RBI', url: '#', snippet: 'Maharashtra continues to lead with 18% of national GDP contribution...' },
  { id: 5, title: 'Voice AI Market Analysis', source: 'Gartner', url: '#', snippet: 'Conversational AI market to reach $32.6B globally by 2028...' },
];
