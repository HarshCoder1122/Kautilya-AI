# Features for Kautilya ChatApp — Strategic Enhancement Plan

## Domain Focus: **AI-Powered Business Intelligence & Sales Automation**

> **Vision**: Position Kautilya as the go-to AI platform for **Indian SMEs and sales teams** — combining Perplexity-style research capabilities, Claude-level coding assistance, and voice-first sales automation. Think of it as "Perplexity for Indian Business + Claude for Sales Tech + Voice AI for Customer Engagement."

---

## 1. Deep Research Mode (Perplexity-Style)

### Feature: Multi-Source Research Agent
**What it does**: When a user asks about market trends, competitors, or business decisions, Kautilya performs:
- Real-time web search (SerpAPI/Google Custom Search)
- News aggregation with Indian business sources (Economic Times, Inc42, YourStory)
- PDF/document analysis if files uploaded
- Structured report generation with citations

**Implementation**:
```python
# New route: /api/research
# Tools needed:
- Web search (SerpAPI)
- News API integration
- Document parsing (PyPDF2, unstructured)
- Citation tracking
- Report formatter (markdown → PDF)
```

**UI in Chat**:
- Collapsible source cards (like Perplexity)
- "Sources" button showing 5-10 referenced URLs
- Export as PDF/Word
- Confidence scoring per source

---

## 2. Code Interpreter & Execution (Claude Artifacts Style)

### Feature: Live Code Sandbox
**What it does**: When user asks for data analysis, charts, or coding help:
- Generate Python code to analyze data
- Execute in sandboxed environment (E2B, Modal, or local Docker)
- Return results + visualizations
- Allow iterative refinement

**Use Cases**:
- "Analyze my sales CSV and show monthly trends"
- "Create a Python script to scrape Flipkart prices"
- "Build a Django REST API for my inventory system"

**Implementation**:
```python
# New service: services/code_interpreter_service.py
# Sandboxing options:
- E2B (recommended): e2b.dev API
- Modal: modal.com serverless
- Local: restricted Python subprocess

# Features:
- File upload (CSV, Excel, JSON)
- Pandas/Matplotlib/Seaborn support
- Chart generation (PNG/SVG)
- Code explanation mode
```

**UI in Chat**:
- Code block with "Run" button
- Output panel showing charts/tables
- Download generated files
- Edit-and-rerun capability

---

## 3. Sales Intelligence Suite

### 3.1 Lead Scoring AI
**What it does**: Analyze conversation transcripts and score leads:
- Intent classification (hot/warm/cold)
- Sentiment trend analysis
- Key phrase extraction (budget, timeline, authority)
- Auto-tagging in CRM

**Integration**:
```python
# New: services/sales_intelligence_service.py
# Connects to:
- Existing call transcripts from livekit_agent.py
- Web chat logs from chat_routes.py
# Outputs:
- Lead score (0-100)
- Recommended next action
- Risk alerts (competitor mentions, objections)
```

### 3.2 Competitor Mention Tracker
**What it does**: Automatically flag when customers mention competitors during calls/chats:
- Real-time alert to sales manager
- Competitive battlecard suggestion
- Win/loss pattern analysis

### 3.3 Follow-Up Automation
**What it does**: AI-generated personalized follow-ups:
- Extract action items from conversation
- Draft email/WhatsApp follow-up
- Schedule in user's calendar (Google Calendar API)
- Track response rates

---

## 4. Voice-First Sales Assistant

### 4.1 Real-Time Call Coaching
**What it does**: Whisper suggestions to sales rep during live calls:
- Objection handling prompts
- Talking ratio alerts (listening vs speaking)
- Question suggestions based on conversation flow
- Compliance warnings (don't promise X, mention Y disclaimer)

**Implementation**:
```python
# Extend livekit_agent.py
# New mode: "coaching_mode" parallel stream
# Uses:
- Real-time transcription (Whisper streaming)
- Intent detection on customer speech
- Suggestion generation (NVIDIA NIM for speed)
# Output: Text overlay or earpiece audio
```

### 4.2 Call Summary & Action Extraction
**What it does** (extends existing post-call analysis):
- Enhanced with CRM field extraction
- Auto-populate Salesforce/HubSpot/Zoho fields
- Action item extraction with deadlines
- Next call scheduling

---

## 5. Knowledge Base & RAG Enhancement

### 5.1 Multi-Modal Knowledge Base
**What it does**: Upload and query various content types:
- PDFs (product brochures, contracts)
- YouTube videos (sales training, competitor ads)
- Web pages (pricing pages, feature docs)
- Spreadsheets (pricing tables, inventory)

**Implementation**:
```python
# Extend existing vector_store_service.py
# Add parsers:
- PyMuPDF for PDFs
- Youtube-transcript-api for videos
- BeautifulSoup for web scraping
- OpenPyXL for Excel

# Query modes:
- Semantic search
- Structured Q&A (tables/charts)
- Source highlighting
```

### 5.2 Company-Specific Fine-Tuning
**What it does**: Train lightweight LoRA adapters on company data:
- Product knowledge
- Brand voice guidelines
- Support ticket history
- Sales playbook

**Implementation**:
```python
# New: services/finetune_service.py
# Using:
- Unsloth for efficient fine-tuning
- Modal for training jobs
- Firestore for adapter storage
- Inference via Groq (if supported) or local vLLM
```

---

## 6. Agent Collaboration System (Kimi-Style)

### Feature: Multi-Agent Workflow
**What it does**: Route queries to specialized agents:
- **Research Agent**: Web search, market analysis
- **Coder Agent**: Code generation, debugging
- **Sales Agent**: Pitch creation, objection handling
- **Support Agent**: Technical troubleshooting

**Implementation**:
```python
# New: services/orchestrator_service.py
# Router LLM (small, fast) classifies intent:
- "analyze my sales data" → Coder Agent
- "what's my competitor pricing" → Research Agent
- "my customer is angry" → Support Agent

# Agents can:
- Call each other (agent delegation)
- Share context via shared memory
- Report back to parent conversation
```

**UI in Chat**:
- Agent switcher dropdown
- "Ask the Researcher" mode
- Side-by-side agent comparison

---

## 7. Canvas/Whiteboard Mode (Claude Artifacts)

### Feature: Interactive Document Creation
**What it does**: Create and iterate on documents alongside chat:
- Sales proposals
- Email sequences
- Competitor comparison tables
- Project plans

**Implementation**:
```vue
<!-- New view: CanvasView.vue -->
<!-- Features:
- Split-pane layout (chat + canvas)
- Artifact generation on demand
- Version history
- Export (PDF, Word, HTML)
- Collaborative editing (Firebase Realtime DB)
-->
```

**Use Cases**:
- "Create a sales proposal for ACME Corp based on our call"
- "Draft a 5-email sequence for abandoned carts"
- "Build a competitive battlecard against CompetitorX"

---

## 8. Real-Time Dashboard & Analytics

### Feature: Live Business Intelligence
**What it does**: Auto-generated dashboards from conversational data:
- Call volume by hour/day
- Sentiment trends
- Top customer questions (topic clustering)
- Agent performance comparison
- Revenue impact tracking

**Implementation**:
```python
# Extend existing analytics in dashboard-app
# New charts:
- Funnel visualization (calls → leads → conversions)
- Word cloud from transcripts
- Sentiment heatmap by time
- Agent leaderboard

# Auto-generation:
- Natural language to chart ("show me calls by hour")
```

---

## 9. Integration Ecosystem

### Essential Integrations for Sales/Business Users:

| Platform | Integration Type | Use Case |
|----------|-----------------|----------|
| **Salesforce** | OAuth + API | Auto-log calls, update opportunities |
| **HubSpot** | OAuth + API | CRM sync, contact enrichment |
| **Zoho CRM** | API | Indian SME favorite |
| **WhatsApp Business** | Meta API | Post-call follow-ups |
| **Google Calendar** | OAuth | Meeting scheduling |
| **Slack** | Webhook | Team alerts, channel summaries |
| **Zapier** | Webhook | Connect to 5000+ apps |
| **Make (Integromat)** | API | Complex automation workflows |

---

## 10. Mobile App Strategy

### Kautilya Mobile (React Native/Flutter)

**Core Features**:
- Voice-first interface (tap to talk)
- Push notifications for hot leads
- Offline call recording + sync
- Quick reply templates
- Live call dashboard

**Differentiator**:
- Works on low-bandwidth (2G optimized)
- Regional language voice input
- Integrated with Indian UPI for payments

---

## Implementation Priority Matrix

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| **P0** | Code Interpreter | Medium | Very High |
| **P0** | Enhanced Sales Analytics | Low | High |
| **P1** | Deep Research Mode | Medium | High |
| **P1** | CRM Integrations | Medium | High |
| **P1** | Canvas Mode | Medium | Medium |
| **P2** | Multi-Agent System | High | Very High |
| **P2** | Mobile App | High | High |
| **P2** | Fine-Tuning Pipeline | High | Medium |
| **P3** | Advanced Voice Coaching | High | Medium |

---

## Competitive Positioning

| Competitor | Their Strength | Kautilya's Advantage |
|------------|----------------|----------------------|
| **Perplexity** | Deep research | + Voice AI + Indian focus + Sales automation |
| **Claude (Anthropic)** | Code/Artifacts | + Real-time voice + SIP telephony + Campaign dialer |
| **Kimi (Moonshot)** | Long context | + Indian languages + Telephony integration |
| **Bland AI** | Voice agents | + Multi-provider LLM + Chat + Research + Code |
| **Synthflow** | No-code voice | + Developer-friendly + Custom code execution |

---

## Recommended First 3 Features to Build

### 1. Code Interpreter (Quick Win)
**Why**: Immediately differentiates from pure voice agents, attracts developer/sales ops users
**Timeline**: 2-3 weeks
**Tech**: E2B sandbox + existing chat infrastructure

### 2. Salesforce/HubSpot Integration
**Why**: Unlocks enterprise sales teams (high ACV customers)
**Timeline**: 1-2 weeks
**Tech**: OAuth flow + webhook handlers

### 3. Enhanced Research Mode
**Why**: Positions against Perplexity, valuable for market research
**Timeline**: 2-3 weeks
**Tech**: SerpAPI + existing LLM service + citation tracking

---

## Success Metrics

- **Activation**: % users who create first agent within 24h
- **Engagement**: Conversations per user per week
- **Retention**: 7-day, 30-day retention rates
- **Revenue**: MRR, Pro conversion rate, ACV
- **Voice Quality**: Call completion rate, avg call duration, sentiment scores
- **Sales Impact**: Leads generated, deals influenced, revenue attributed

---

## Final Vision Statement

> **Kautilya becomes the AI co-founder for every Indian SME** — handling customer calls, researching competitors, writing code, analyzing data, and coaching the sales team — all in Hinglish, all at Indian prices.

---

# NEW FEATURES — Added April 2026

## 11. ReAct Orchestration Engine (Reasoning + Action)

### Feature: Multi-Step Task Automation with Visible Reasoning
**What it does**: When user asks complex queries, Kautilya shows its thinking process and executes multiple actions in parallel:

**Example Flow**:
```
User: "Find best stock to buy under ₹500"

Step 1 - REASONING:
💭 "Need current market data, fundamentals, news sentiment, technical analysis"

Step 2 - ACTION PLAN:
🔧 Call: NSE API (market data)
🔧 Call: Screener.in (fundamentals)  
🔧 Call: News API (sentiment)
🔧 Call: Technical indicators API

Step 3 - PARALLEL EXECUTION:
✓ All 4 calls execute simultaneously (async)

Step 4 - SYNTHESIS:
📊 "Based on analysis, top 3 candidates: RELIANCE, TCS, HDFC Bank
    RECOMMENDATION: TCS
    Reasoning: Strong quarterly results + bullish technicals + positive news
    Risk: Mid-term resistance at ₹4,200"
```

**Implementation**:
```python
# New: services/orchestrator_service.py

class ReActOrchestrator:
    AVAILABLE_TOOLS = {
        "web_search": serpapi_search,
        "stock_data": get_nse_stock_data,
        "code_execute": e2b_sandbox,
        "calendar_create": google_calendar_api,
        "email_send": sendgrid_api,
        "crm_update": salesforce_api,
        "firestore_query": firebase_query,
        "browser_screenshot": browserstack_api,
    }
    
    async def run(self, query: str, context: dict) -> dict:
        # Step 1: Reason what tools needed
        plan = await self.reasoner.plan(query)
        
        # Step 2: Execute actions (parallel where possible)
        results = await self.execute_parallel(plan.actions)
        
        # Step 3: Synthesize final answer
        answer = await self.synthesizer.generate(
            query=query, observations=results, context=context
        )
        
        return {
            "answer": answer,
            "reasoning_trace": plan.thought_process,
            "actions_taken": plan.actions,
            "sources": results.sources
        }
```

**UI Components**:
- Collapsible reasoning trace (🧠 Show reasoning)
- Action cards with status indicators
- Real-time progress updates
- Source links for each action
- Confidence scoring

---

## 12. BrowserStack Integration

### Feature: Cross-Browser Testing & Visual QA
**What it does**: Test websites on real devices, capture screenshots, perform visual regression

**Core Capabilities**:
| Product | Purpose |
|---------|---------|
| **Live** | Real devices (iOS/Android) manual testing |
| **Automate** | Selenium/Cypress/Playwright on 3000+ combos |
| **App Live** | Native app testing on real devices |
| **Percy** | Visual regression testing |
| **Geolocation** | Test from India, US, UK IPs |

**Use Cases**:
- "Test my website on iPhone 14"
- "Compare my pricing page with competitor"
- "Check if my site works on 2G connection"
- "Daily screenshot monitoring of competitor sites"

**Implementation**:
```python
# services/browserstack_service.py

class BrowserStackService:
    def capture_screenshot(self, url: str, device: str) -> ScreenshotResult:
        """Capture screenshot on real device"""
        response = requests.post(
            "https://api.browserstack.com/screenshots",
            auth=(USERNAME, ACCESS_KEY),
            json={
                "url": url,
                "device": device,  # "iPhone 14 Pro", "Samsung Galaxy S23"
                "os": "ios",
                "os_version": "17",
                "browser": "safari"
            }
        )
        return ScreenshotResult(
            image_url=response.json()["screenshot_url"],
            device_info=response.json()["device"],
            load_time=response.json()["page_load_time"]
        )
    
    def automate_test(self, script: str, browsers: List[str]) -> TestResult:
        """Run Selenium/Playwright tests"""
        # Upload script to BrowserStack Automate
        # Run parallel across specified browsers
        # Return test results with videos/logs
        pass
```

**AI-Powered Visual QA**:
```python
# AI analyzes screenshots for issues
issues = await ai_analyze_screenshot(screenshot_url)
# Returns: ["Button cut off", "Font too small", "Layout broken on mobile"]
```

---

## 13. AI-Powered Data Analysis & Interactive Dashboard

### Feature: Upload Files → Auto-Generate Dashboard → Natural Language Editing

**Complete Workflow**:
```
User uploads files (PDF, Excel, CSV, Images)
    ↓
AI parses & extracts structured data
    ↓
Auto-detects schema & relationships
    ↓
Generates insights (trends, anomalies, correlations)
    ↓
Builds interactive dashboard (charts, KPIs, tables)
    ↓
User edits via chat: "Add pie chart", "Filter to Mumbai"
    ↓
Publish to web with unique URL
```

### 13.1 Multi-File Upload & Analysis

**Supported Formats**:
| File Type | Parser | Analysis |
|-----------|--------|----------|
| **PDF** | PyMuPDF | Text, tables, charts extraction |
| **Excel** | OpenPyXL | Formulas, pivot tables, graphs |
| **CSV** | pandas | Statistical analysis, trends |
| **Word** | python-docx | Document structure, key points |
| **PowerPoint** | python-pptx | Slide summaries |
| **Images** | PIL + Gemini Vision | OCR, chart-to-data |
| **JSON/XML** | native | Structured data |

**Upload Interface**:
```vue
<UploadZone 
  accept=".pdf,.xlsx,.csv,.docx,.pptx,.json,.png,.jpg"
  multiple
  @process="handleFiles"
/>
```

### 13.2 AI-Powered Data Understanding

```python
# services/document_analyzer.py

class DocumentAnalyzer:
    async def analyze_files(self, files: List[File]) -> AnalysisResult:
        # Stage 1: Parse & Extract
        documents = [await self.parse_file(f) for f in files]
        
        # Stage 2: Cross-Document Intelligence
        relationships = await self.find_relationships(documents)
        # e.g., "sales_Q1.xlsx connects to sales_Q2.xlsx"
        
        # Stage 3: Schema Detection
        schema = await self.infer_schema(documents)
        # Detects: Time series, categories, metrics, dimensions
        
        # Stage 4: Insight Extraction
        insights = await self.extract_insights(documents)
        # Auto-detects: Trends, anomalies, correlations
        
        return AnalysisResult(
            documents=documents,
            relationships=relationships,
            suggested_dashboards=self.suggest_dashboards(schema, insights),
            key_metrics=self.extract_kpis(documents)
        )
```

### 13.3 Auto-Generated Insights

```python
# services/insight_engine.py

class InsightEngine:
    def analyze(self, df: pd.DataFrame) -> List[Insight]:
        insights = []
        
        # Trend Detection
        if self.has_datetime(df):
            trend = self.detect_trend(df)
            insights.append(Insight(
                type="trend",
                description=f"Revenue shows {trend.direction} trend of {trend.rate}% per month",
                confidence=trend.confidence,
                chart_suggestion="line_chart"
            ))
        
        # Anomaly Detection
        anomalies = self.detect_anomalies(df)
        for anomaly in anomalies:
            insights.append(Insight(
                type="anomaly",
                description=f"Unusual spike on {anomaly.date}: {anomaly.value}",
                severity=anomaly.severity
            ))
        
        # Correlation Discovery
        correlations = self.find_correlations(df)
        for corr in correlations:
            insights.append(Insight(
                type="correlation",
                description=f"{corr.col1} and {corr.col2} are {corr.strength} correlated (r={corr.r})",
                suggestion=f"Consider analyzing {corr.col1} impact on {corr.col2}"
            ))
        
        # Segmentation
        segments = self.segment_data(df)
        insights.append(Insight(
            type="segmentation",
            description=f"Data naturally clusters into {len(segments)} segments",
            segments=segments
        ))
        
        return insights
```

### 13.4 Interactive Dashboard Builder

**Widget Types**:
- **Chart Widget**: Line, Bar, Pie, Scatter, Heatmap (Chart.js/Plotly)
- **KPI Card**: Metrics with trends, sparklines
- **Table Widget**: Sortable, filterable, drill-down
- **Insight Widget**: AI-generated text summaries
- **Filter Bar**: Global filters (date range, region, category)
- **Map Widget**: Geographical data visualization

**Natural Language Editing**:
```
User: "Add a pie chart showing revenue by region"
→ AI understands schema
→ Generates Chart.js config
→ Adds to dashboard grid
→ Suggests color palette

User: "Make the line chart monthly instead of weekly"
→ AI re-aggregates data
→ Updates chart config
→ Refreshes visualization

User: "What's the correlation between marketing spend and sales?"
→ AI runs correlation analysis
→ Creates scatter plot with trend line
→ Shows R² value
```

### 13.5 Predictive Analytics

```python
# services/prediction_service.py

class PredictionService:
    def forecast(self, df: pd.DataFrame, target: str, periods: int):
        # Try multiple models
        models = {
            'prophet': ProphetForecaster(),
            'arima': ARIMAForecaster(),
            'lgbm': LightGBMForecaster()
        }
        
        # Cross-validation to pick best
        best_model = self.select_best_model(df, models)
        
        # Generate forecast
        forecast = best_model.predict(df, periods)
        
        return {
            'predictions': forecast.values,
            'confidence_intervals': forecast.ci,
            'model_used': best_model.name,
            'accuracy': best_model.mape,
            'chart_config': self.generate_forecast_chart(forecast)
        }
```

### 13.6 Web Publishing & Sharing

```python
# Publish dashboard to public URL

@dashboard_bp.route('/api/dashboards/<id>/publish', methods=['POST'])
def publish_dashboard(id):
    dashboard = get_dashboard(id)
    slug = generate_slug(dashboard.title)
    
    public_dashboard = {
        'slug': slug,
        'title': dashboard.title,
        'widgets': dashboard.widgets,
        'data_snapshot': dashboard.data,
        'theme': dashboard.theme,
        'access': request.json.get('access', 'public'),
        'refresh_mode': request.json.get('refresh', 'manual'),  # manual, hourly, daily
        'created_at': firestore.SERVER_TIMESTAMP
    }
    
    db.collection('public_dashboards').document(slug).set(public_dashboard)
    
    return {
        'public_url': f'https://kautilya.ai/d/{slug}',
        'embed_code': f'<iframe src="https://kautilya.ai/d/{slug}" width="100%" height="800"></iframe>',
        'qr_code': generate_qr(f'https://kautilya.ai/d/{slug}')
    }
```

**Public Dashboard Features**:
- Live/Static mode (auto-refresh or snapshot)
- Interactive filters
- Export: PNG, PDF, CSV
- Comments from viewers
- Password protection option
- Scheduled email reports

### 13.7 Use Case Examples

**Sales Manager**:
```
Uploads: sales_2025.xlsx, targets.pdf, team_performance.csv
Dashboard Generated:
├─ Revenue trend (line chart)
├─ Team leaderboard (table)
├─ Target vs Actual (bullet chart)
├─ Regional heatmap (map)
└─ Top 10 products (bar chart)

Insights:
→ "Q3 missed target by 12% due to supply chain issues"
→ "South region outperforming by 25%"
→ "Predicted Q4: 15% growth if trend continues"
```

**Marketing Director**:
```
Uploads: campaign_data.csv, social_analytics.xlsx, brand_survey.pdf
Dashboard Generated:
├─ Campaign ROI comparison
├─ Sentiment timeline
├─ Channel performance matrix
├─ Word cloud (brand perception)
└─ Funnel visualization

User asks: "Which campaign had best ROI?"
AI: "Diwali campaign: 4.5x ROI, 2.3M impressions"
```

**Startup Founder**:
```
Uploads: pitch_deck.pptx, financial_model.xlsx, user_metrics.csv
Dashboard Generated:
├─ Investor dashboard
├─ Burn rate projection
├─ Cohort retention curves
├─ Competitive positioning map
└─ KPI scorecard

Share: "Send to investors"
→ Public URL with password
→ Auto-updates weekly
→ PDF scheduled to investors every Monday
```

---

## 14. Smart Automation Agents

### 14.1 Stock Research Agent
```
User: "Best stock under ₹500 for long term"

Actions:
├─ Search: "top stocks under 500 rupees 2026 India"
├─ Fetch: NSE top gainers/losers
├─ Analyze: Quarterly results (Screener.in scraping)
├─ Check: Promoter holding changes
├─ News: Recent announcements
└─ Output: Ranked list with reasoning
```

### 14.2 Property Research Agent
```
User: "2BHK in Bangalore Whitefield under 80 lakh"

Actions:
├─ Search: 99acres, MagicBricks listings
├─ Map: Check nearby metro/connectivity
├─ Verify: RERA registration
├─ Compare: Price per sqft in area
└─ Schedule: Site visits via Google Calendar
```

### 14.3 Competitor Tracker Agent
```
User: "What are my competitors doing?"

Actions (Daily automation):
├─ BrowserStack screenshots of competitor sites
├─ News: Google Alerts API
├─ Social: Track LinkedIn/Twitter
├─ Pricing: Monitor pricing page changes
└─ Report: Weekly digest email with visual diffs
```

### 14.4 Interview Prep Agent
```
User: "Prepare me for TCS interview"

Actions:
├─ Search: Recent TCS interview experiences
├─ Code: LeetCode problems TCS asks
├─ Company: TCS latest news, financials
├─ Mock: Generate questions with answers
└─ Schedule: Practice sessions in calendar
```

---

## 15. Voice-Enabled Dashboard

### Feature: Talk to Your Data
```
User says: "Kautilya, show me Mumbai sales"
→ Speech-to-text
→ Intent: "filter_dashboard"
→ Entity: region="Mumbai"
→ Applies filter
→ Speaks: "Mumbai sales are 2.5 crores this month, up 15%"

User says: "Compare with last month"
→ Adds comparison view
→ Shows MoM change indicators
```

---

## 16. Implementation Priority — Updated

| Phase | Features | Timeline | Status |
|-------|----------|----------|--------|
| **Phase 1** | Code Interpreter, File Upload, Basic Charts | 2-3 weeks | P0 |
| **Phase 2** | ReAct Orchestrator, Auto-Insights | 2 weeks | P0 |
| **Phase 3** | BrowserStack Integration, Visual QA | 1-2 weeks | P1 |
| **Phase 4** | Advanced Dashboard, Predictions | 2-3 weeks | P1 |
| **Phase 5** | Smart Agents (Stock, Property, Competitor) | 2 weeks | P2 |
| **Phase 6** | Voice Commands, Collaboration | 2 weeks | P2 |
| **Phase 7** | Mobile App, Public Sharing | 3-4 weeks | P3 |

---

## Tech Stack for New Features

| Component | Tool | Purpose |
|-----------|------|---------|
| **Planning LLM** | Groq (Llama 70B) | Fast reasoning for ReAct |
| **Execution** | Python asyncio | Parallel API calls |
| **Browser** | BrowserStack API | Real device screenshots |
| **Code Sandbox** | E2B.dev | Safe code execution |
| **Charts** | Chart.js / Plotly.js | Visualizations |
| **Tables** | AG-Grid | Interactive data tables |
| **Grid Layout** | vue-grid-layout | Drag-drop dashboards |
| **PDF Export** | jsPDF + html2canvas | Report generation |
| **Data Processing** | PyArrow / Polars | Fast data analysis |
| **ML/Forecasting** | Prophet, scikit-learn | Predictions |
| **File Parsing** | PyMuPDF, OpenPyXL, pandas | Document extraction |
| **Collaboration** | Firestore + Yjs | Real-time editing |

---

## MVP Definition

**Week 4 Target**:
- User uploads Excel file
- AI auto-generates 5 charts + 3 KPIs
- Natural language editing works ("Add pie chart")
- Can share public URL
- Basic ReAct for stock queries

**Success Criteria**:
- Dashboard generated in < 10 seconds
- Natural language to chart in < 3 seconds
- Public URL loads in < 2 seconds
- 90%+ accuracy on NL commands
