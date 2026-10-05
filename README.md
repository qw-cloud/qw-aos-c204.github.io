# Qingyang (Frank) Wu — Research Systems Portfolio

This repository is the public index for a growing collection of research and engineering projects.

**Live portfolio:** https://qw-cloud.github.io/qw-aos-c204.github.io/

## Current focus

I am interested in building systems that turn messy signals into interpretable decisions:

- longitudinal data products;
- quantitative modeling and forecasting;
- interactive research interfaces;
- applied machine learning;
- automated public-data pipelines.

## Projects

### Academic Market Timing
**Live:** https://qw-cloud.github.io/qw-aos-c204.github.io/academic-market-timing/

A daily-updated faculty hiring market timing system that combines field-level vacancy signals, hiring sentiment, macro labor-demand conditions, competition-pressure proxies, and forward timing scores.

Directory: `academic-market-timing/`

### AeroVision
**Live:** https://qw-cloud.github.io/qw-aos-c204.github.io/projects/aerovision/

An interactive visualization layer around an earlier satellite-imagery aircraft detection project using classical ML, CNNs, and a custom ResNet.

Directory: `projects/aerovision/`

This project originated as coursework and is preserved as earlier work rather than defining the portfolio homepage.

## Repository structure

```text
/
├── index.html
├── styles.css
├── app.js
│
├── academic-market-timing/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── data/
│   ├── scripts/
│   └── README.md
│
├── projects/
│   └── aerovision/
│       ├── index.html
│       ├── styles.css
│       ├── app.js
│       └── README.md
│
└── .github/
    └── workflows/
        └── academic-market-timing.yml
```

The root is intentionally a portfolio index. Individual projects live in their own directories and can evolve independently.
