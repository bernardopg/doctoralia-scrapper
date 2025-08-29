```mermaid
graph TD
    A[🚀 Start] --> B{Command Type}

    B -->|setup| C[🔧 Setup Command]
    B -->|scrape| D[🕷️ Scraping Command]
    B -->|generate| E[🤖 Response Generation]
    B -->|run| F[⚡ Complete Workflow]
    B -->|status| G[📊 Status Check]

    %% Setup Workflow
    C --> C1[📱 Configure Telegram]
    C1 --> C2[🕷️ Configure Scraping Mode]
    C2 --> C3[💾 Save Configuration]

    %% Scraping Workflow
    D --> D1[🔗 Validate Doctoralia URL]
    D1 --> D2[🌐 Initialize Selenium WebDriver]
    D2 --> D3[📄 Load Doctor Page]
    D3 --> D4[🔍 Extract Reviews Data]
    D4 --> D5[💾 Save to JSON File]
    D5 --> D6[📊 Generate Statistics]
    D6 --> D7{Telegram Enabled?}
    D7 -->|Yes| D8[📱 Send Scraping Notification]
    D7 -->|No| D9[✅ Scraping Complete]

    %% Response Generation Workflow
    E --> E1[📂 Load Latest Scraped Data]
    E1 --> E2[🔍 Identify Unanswered Reviews]
    E2 --> E3[🤖 Generate AI Responses]
    E3 --> E4[📝 Apply Quality Templates]
    E4 --> E5[💾 Save Response Files]
    E5 --> E6{Telegram Enabled?}
    E6 -->|Yes| E7[📱 Send Response Notification]
    E6 -->|No| E8[✅ Generation Complete]

    %% Complete Workflow
    F --> F1[🔄 Execute Scraping]
    F1 --> F2[🔄 Execute Generation]
    F2 --> F3[✅ Workflow Complete]

    %% Status Check
    G --> G1[⚙️ Check Configuration]
    G1 --> G2[📁 Check Data Files]
    G2 --> G3[📊 Display System Status]

    %% Daily Automation
    H[⏰ Daily Cron Job<br/>9:00 AM] --> I[📜 Execute Daily Script]
    I --> J[🔄 Run Complete Workflow]
    J --> K[📝 Log Results]
    K --> L[📧 Send Daily Report]

    %% Error Handling
    D4 -.->|Error| M[🚨 Error Handler]
    E3 -.->|Error| M
    M --> N[🔄 Retry with Backoff]
    N --> O{Retry Success?}
    O -->|Yes| P[✅ Continue]
    O -->|No| Q[🛑 Circuit Breaker]

    %% Monitoring & Logging
    R[📊 Performance Monitor] --> S[📈 Track Metrics]
    S --> T[📝 Log Performance]
    T --> U[🎯 Health Check]

    %% External Components
    V[🌐 Doctoralia Website] --> D3
    W[🤖 Telegram Bot API] --> D8
    W --> E7

    %% Data Flow
    X[📄 Scraped JSON] --> E1
    Y[📝 Response Templates] --> E4
    Z[⚙️ Configuration] --> C3
    Z --> D2
    Z --> E

    %% Styling
    classDef startEnd fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef data fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef external fill:#fce4ec,stroke:#880e4f,stroke-width:2px

    class A,C3,D9,E8,F3,G3,L,P startEnd
    class C,C1,C2,D,D1,D2,D3,D4,D5,D6,E,E1,E2,E3,E4,E5,F,F1,F2,G,G1,G2,I,J,K,M,N,Q,R,S,T,U start process
    class B,D7,E6,O decision
    class X,Y,Z data
    class V,W external
```
