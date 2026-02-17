# Team Financial Analyst

An AI-powered financial analysis workflow built on Claude Code. Drop in financial statements, get an executive briefing in 2 minutes, then go as deep as you need — with specialized modules for scoring, industry analysis, Indian market checks, peer comparisons, and investment due diligence.

## Setup

1. Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) if you haven't already
2. Clone this repo:
   ```bash
   git clone https://github.com/paidinesh7/team-financial-analyst.git
   ```
3. Open the project folder in Claude Code:
   ```bash
   cd team-financial-analyst
   claude
   ```

## How to use

### 1. Add your files

Drop financial statements into the `statements/` folder — PDFs, spreadsheets, CSVs, images of financial statements, annual reports. Anything you'd normally read during an analysis.

For company comparisons, add statements for multiple companies.

### 2. Ask for an analysis

Open Claude Code in this project folder and say something like:

- "Analyze the financials in the statements folder"
- "What do the numbers look like for this company?"
- "Review the annual report I just added"
- "Compare these two companies"

### 3. Get the executive briefing

The agent reads everything and produces a quick briefing:

- **Company snapshot** — what the business does, how it makes money
- **Key numbers table** — the metrics that matter most for this specific company
- **Red flags** — the 3-5 most critical issues, ranked by severity, with numbers
- **What looks good** — specific strengths backed by data
- **Questions to dig into** — what the data raises but doesn't answer

Designed to be absorbed in about 2 minutes.

### 4. Choose what to explore next

After the briefing, the agent suggests follow-on options based on what it found. It picks the most relevant ones for the company and explains each option so you know what you're getting. You might see:

| Option | What it does |
|--------|-------------|
| **Go deeper** | Full line-by-line analysis of income statement, balance sheet, cash flows, ratio analysis, and a connecting-the-dots narrative |
| **Scoring frameworks** | Computes quantitative health scores — Altman Z-Score (bankruptcy risk), Piotroski F-Score (financial strength), Beneish M-Score (earnings manipulation probability), DuPont analysis (what's driving ROE). Each score is explained before it's presented |
| **Industry deep dive** | Applies the metrics that actually matter for the company's industry — NPA ratios for banks, ARR and churn for SaaS, capacity utilization for manufacturers, and more |
| **Indian market checks** | Screens for India-specific risk patterns — promoter pledge levels, related party transactions, auditor red flags, CARO remarks, contingent liabilities |
| **Compare companies** | Side-by-side comparison on the same metrics across multiple companies, with a strengths/weaknesses matrix |
| **Due diligence checklist** | A structured 22-point pass/fail checklist across earnings quality, balance sheet strength, growth, working capital, and governance — designed as a final gate before an investment decision |

You don't have to pick from the suggestions — you can ask about anything specific at any point.

### 5. Keep going

Every module can lead to further questions. Ask follow-ups, challenge the output, or request a different module. The conversation is cumulative — the agent remembers what it's already analyzed.

## What's in this repo

```
├── CLAUDE.md                    # Agent instructions (analysis framework + all modules)
├── Understanding_finance.pdf    # Reference: Merrill Lynch guide to financial reports
├── statements/                  # Drop your financial statements here
└── README.md                    # You're reading this
```

## What the scoring frameworks measure

If you're new to these, here's a quick primer:

- **Altman Z-Score** — Predicts the probability of bankruptcy within two years by combining five financial ratios into a single score. Developed in 1968, still widely used. Gives a clear Safe / Grey zone / Distress reading.

- **Piotroski F-Score** — Scores a company 0–9 on nine binary tests covering profitability, leverage, and efficiency. Originally designed to find strong companies among cheap stocks. A score of 8-9 means financially healthy, 0-4 means multiple areas of concern.

- **Beneish M-Score** — Estimates the probability that a company is manipulating its reported earnings. Uses eight financial ratios that tend to be distorted during earnings manipulation. A score above -1.78 means "investigate further."

- **DuPont Analysis** — Breaks ROE into three parts: profit margin, asset turnover, and leverage. Tells you whether high ROE comes from genuine profitability, efficient operations, or just piling on debt.

## Tips

- **More files = better analysis.** Multiple years of statements, investor presentations, and MD&A sections give the agent more to work with. A single year's financials never tell the full story.
- **Ask specific follow-ups.** "Is the debt maturity schedule a problem?" gets a better answer than a generic "go deeper."
- **Challenge the output.** If something doesn't look right, say so. The agent will re-examine and correct itself.
- **You don't need finance knowledge to start.** The agent explains every framework and metric before using it. The scoring frameworks section above gives you the basics, but the agent will go into more detail when you select them.
- **Indian companies benefit from the India-specific checks.** Promoter pledge analysis and related party screening catch risks that standard analysis misses.
