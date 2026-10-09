# Academic Market Timing

A daily-updated academic labor-market timing dashboard.

**Live app:** https://a2xw.github.io/w-cd.github.io/projects/academic-market-timing/

## What it does

The project asks a specific question: **is the academic job market for a given field improving or deteriorating relative to its own recent history?**

It tracks 12 broad field groups:

- Computer Science & AI
- Health & Medical
- Engineering & Technology
- Physical & Environmental Sciences
- Biological Sciences
- Mathematics & Statistics
- Psychology
- Business & Management
- Sociology, Demography & Social Sciences
- Economics & Finance
- Politics & Government
- Humanities

The dashboard updates automatically each day with GitHub Actions.

## Signals

### 1. Hiring supply
The collector parses the public discipline counts exposed by jobs.ac.uk. The model compares today's count to that field's own trailing baseline rather than comparing raw counts across fields.

### 2. Hiring sentiment
Public Google News RSS headlines are scored with a small transparent lexicon of expansion terms (e.g. hiring, recruiting, expansion) and stress terms (e.g. freeze, layoffs, cuts, deficit). The collector also attempts a small Reddit RSS community layer from academic subreddits. Reddit is optional and failure is non-fatal.

### 3. Macro backdrop
The model uses the FRED/BLS JOLTS **private educational services job-openings rate** (series `JTU6100JOR`) as a slow-moving U.S. labor-demand anchor.

### 4. Timing score
The current score is:

```
Timing = 0.55 × supply signal
       + 0.28 × sentiment signal
       + 0.17 × macro signal
```

Every component is mapped onto a 0–100 scale.

- **60+**: relatively favorable / improving
- **42–60**: mixed
- **below 42**: relatively tight / deteriorating

These cutoffs are descriptive, not causal.

## Competition pressure

`Competition pressure = 100 - Timing score`

This is deliberately labeled a **market-tightness proxy**. It is **not** applicants per vacancy and should never be interpreted as a direct acceptance probability.

## Forecast

The 30- and 90-day outlooks use bounded linear extrapolation over up to the most recent 30 daily timing observations. Daily slope is capped to prevent unstable early forecasts. With fewer than five observations the forecast is held effectively at the current score.

The app separately displays **model confidence**, which increases as real daily history accumulates and source coverage remains healthy.

## Automation

The workflow lives at:

`.github/workflows/academic-market-timing.yml`

It runs daily at **11:17 UTC** and can also be triggered manually from GitHub Actions. It:

1. checks out the repository;
2. runs `scripts/update_market.py`;
3. refreshes `data/latest.json` and `data/history.json`;
4. commits the new snapshot back to `main`.

No API secrets are required.

## Data caveats

This project is designed as a **timing instrument**, not a definitive global census of faculty jobs.

- jobs.ac.uk has meaningful international coverage but is UK-centered.
- Headline sentiment is noisy.
- Reddit RSS availability can vary.
- The JOLTS education series is much broader than tenure-track faculty hiring.
- Applicant counts are not directly observed.
- Field definitions are broad and imperfect.
- Early forecasts should be treated as low-confidence until enough daily observations accumulate.

The intended use is to identify **changes in market regime** and seasonality over time, not to estimate an individual's chance of obtaining an offer.

## Local run

```bash
python academic-market-timing/scripts/update_market.py
```

Then open `academic-market-timing/index.html` through a local static server or GitHub Pages.

## License

Research / portfolio project. Verify source-site terms before redistributing raw scraped content. The repository stores only aggregate counts and derived scores, not copied job listings.
