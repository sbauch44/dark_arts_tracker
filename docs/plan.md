# Corporate Dark Arts Tracker: Project Plan

**Version:** 0.1
**Last updated:** 2026-05-04

## 1. Objective

Build a system that ingests SEC filings, extracts incentive-structure and insider-transaction signals, scores them against a "dark arts" pattern taxonomy, and surfaces tickers worth flagging long or short. Success criteria:

1. End-to-end pipeline that ingests Form 4, DEF 14A, DEFM14A, 8-K, SC 13D, 10-K/Q for a defined universe.
2. A labeled dataset of historical "MNPI-adjacent grant" events derived from Background of the Merger sections in completed deal proxies.
3. A feature-rich grant-level dataset suitable for both heuristic flagging and statistical modeling.
4. A Bayesian scoring model with calibrated forward-return predictions.
5. A backtest showing the top-decile score outperforms control on a rolling out-of-sample basis.
6. A watchlist with alerts when new filings cross score thresholds.

This is a personal research project. Not a production trading system. The deliverable is conviction-supported flags, not auto-execution.

## 2. Signal Taxonomy

Synthesizing Walker (Yet Another Value) and Puangmalai (Nongaap), the patterns we are detecting fall into seven families.

**Pattern A: Spring-loaded grants.** Equity granted shortly before positive material news. Detected by negative grant-to-news offset combined with strong positive abnormal return in the 5-90 days post-grant. Archetypes: KODK July 2020 options, EKSO November 2025 PSUs, TWTR April 2022 RSUs, LHCG March 2022 RSUs.

**Pattern B: Bullet-dodged grants.** Equity granted shortly after negative material news drives down the stock. Detected by V-shaped abnormal return pattern around the grant date. Archetype: STMP 2019 options.

**Pattern C: MNPI-adjacent change-of-control PSUs.** PSUs with stock-price hurdles modestly above current market combined with change-of-control vesting triggers. The smoking gun for pending M&A. Archetype: EKSO PSUs at $7.50 hurdle when stock at $4.

**Pattern D: Aggressive new-regime packages.** Heavy stock-price-conditional PSUs granted shortly after CEO change, activist truce, or restructuring. Slower-burn bullish signal on operational turnaround. Archetype: VAC 2026 CEO/COO packages.

**Pattern E: Activist-aligned grants.** Cooperation agreement amendments raising activist ownership caps, immediately followed by chunky stock-price PSUs. Optionality on takeout. Archetype: RPD March 2026.

**Pattern F: Misaligned absolute-size incentives.** Comp tied to total EBITDA or market cap with no per-share constraint. Bearish flag on value destruction risk in M&A. Archetype: GME 2025.

**Pattern G: Governance-hygiene red flags.** Two-person comp committees, no comp consultant engaged, founder or sponsor rep as comp chair, single annual meeting, frequent unanimous written consent. Acts as a covariate amplifying patterns A-F. Archetype: STMP comp committee.

Patterns A, B, C, E are specific events. D is a regime detection. F is structural. G is a multiplier.

## 3. High-Level Architecture

```
EDGAR + datamule
        |
        v
  ingest/  ----->  raw/ (parquet of filing metadata + SGML/HTML blobs)
        |
        v
  parse/   ----->  parsed/ (structured grants, comp tables, deal timelines)
        |
        v
  label/   ----->  labeled/ (positive examples from merger backgrounds)
        |
        v
  features/ ---->  features/ (per-grant feature frame, per-company governance frame)
        |
        v
  score/   ----->  scores/ (heuristic v1, logistic v2, Bayesian v3 outputs)
        |
        +---> backtest/ (forward-return analysis vs benchmarks)
        |
        +---> watchlist/ (current flags + manual annotations)
        |
        v
   alert/ (cron-driven email/Slack notifications on new high-score filings)
```

Storage layer is parquet + DuckDB. No need for a real RDBMS at this scale. Each module reads parquet, writes parquet. Reproducibility comes from versioning the parsing/feature code and re-running.

## 4. Data Sources

### SEC filings (via datamule)

| Filing | Purpose | Volume estimate |
|--------|---------|-----------------|
| Form 4 | Insider transactions, PSU grants, vesting conditions in footnotes | ~500k/year |
| DEF 14A | Annual proxy: CD&A, comp tables, comp committee composition | ~6k/year |
| DEFM14A / S-4 | Merger proxies with Background of the Merger | ~200/year |
| 8-K (Item 5.02) | New employment agreements, comp arrangements | ~5k/year |
| 8-K (Item 8.01, 1.01) | Cooperation agreements, buyback authorizations | ~30k/year |
| SC 13D / 13D-A | Activist stakes, ownership cap amendments | ~3k/year |
| 10-K, 10-Q | Stock-based comp footnotes, share repurchases | ~30k/year |

Datamule's tar archive covers all of this. Estimated one-time pull cost for full historical corpus 2010-present: under $50.

### Market data

Whatever you have wired up for the CBB project price source. Need: daily OHLC + volume, sector classification, total return for abnormal-return calculation. Russell 3000 universe minimum; ideally include delisted tickers for survivorship-free backtests.

### Reference data

Sector/industry mapping (GICS), company-to-CIK mapping (EDGAR provides), CIK-to-ticker mapping. Director CIK linkage across companies (extracted from Form 3/4 reporting-owner CIKs).

## 5. Repository Layout

```
dark-arts-tracker/
├── pyproject.toml              # uv-managed
├── ruff.toml
├── .devcontainer/
├── README.md
├── docs/
│   ├── plan.md                 # this document
│   ├── feature_spec.md
│   ├── labeling_protocol.md
│   └── decisions/              # ADR-style decision log
├── src/dark_arts/
│   ├── ingest/                 # datamule wrappers, scheduling
│   │   ├── form4.py
│   │   ├── proxies.py
│   │   ├── eight_k.py
│   │   └── activist.py
│   ├── parse/                  # filing-specific parsers
│   │   ├── form4_footnotes.py  # LLM-assisted PSU hurdle extraction
│   │   ├── cda.py              # CD&A + comp committee composition
│   │   ├── merger_background.py
│   │   └── cooperation.py
│   ├── label/                  # build labeled positive set
│   │   ├── deal_timeline.py
│   │   └── grant_window_match.py
│   ├── features/
│   │   ├── grant_timing.py     # spring-load / bullet-dodge features
│   │   ├── grant_terms.py      # hurdle premium, IRR, COC trigger
│   │   ├── governance.py       # comp committee hygiene score
│   │   └── activist.py         # 13D + cap raise features
│   ├── graph/                  # director cross-company graph
│   │   ├── build.py
│   │   └── proximity_score.py
│   ├── score/
│   │   ├── heuristic.py        # v1
│   │   ├── logistic.py         # v2
│   │   └── bayesian.py         # v3, pymc
│   ├── backtest/
│   │   ├── forward_returns.py
│   │   ├── decile.py
│   │   └── deal_recall.py
│   ├── watchlist/
│   └── alert/
├── notebooks/                  # exploratory work
├── scripts/                    # entry points for cron and manual runs
│   ├── refresh_filings.py
│   ├── rebuild_features.py
│   ├── score_today.py
│   └── send_alerts.py
├── tests/
└── data/                       # gitignored
    ├── raw/
    ├── parquet/
    ├── labeled/
    └── duckdb/
```

Same general shape as your CBB repo. Jupyter notebooks for prototyping, code in `src/` for production paths, scripts as the cron entry points.

## 6. Phased Build Plan

Each phase ships something usable on its own. If you stop after any phase, you still have value.

### Phase 0: Scaffolding (week 1)

- uv project init, ruff config, devcontainer, GitHub repo private.
- pyproject pinning datamule, doc2dict, polars, duckdb, pymc, plotly, anthropic.
- Scratch notebook successfully pulls a single Form 4 via datamule and parses it.
- One ADR written: "Why parquet + DuckDB instead of Postgres."

**Deliverable:** repo skeleton + ability to pull one Form 4.

### Phase 1: Form 4 ingestion and base parsing (weeks 2-4)

- Bulk pull Form 4 universe 2015-present via datamule-tar.
- Parse Form 4 XML into structured grants frame: ticker, CIK, reporting owner CIK, grant date, transaction code, security type, shares, price, footnote text.
- Stand up a "case study" subset notebook reproducing the 9 named tickers from Walker and Mike (GME, EKSO, VAC, RPD, KODK, STMP, LHCG, TWTR, GSKY) and visually confirm grants you expect to see are in the parsed frame.
- Initial Form 4 footnote extractor using Claude API: extract grant type, vesting conditions, stock price hurdles, change-of-control flags, time-to-vest. Cache by accession number. Spot-check 100 random extractions for accuracy.

**Deliverable:** `grants.parquet` with one row per grant, structured fields filled where parseable.

### Phase 2: Merger background labeled dataset (weeks 5-7)

This is the load-bearing phase. Without good labels, everything downstream is heuristic guesswork.

- Pull all DEFM14A and S-4 filings 2015-present (small volume, easy).
- LLM extraction of the Background of the Merger section. Output schema: deal_id, target_cik, acquirer_name, first_contact_date, first_offer_date, signed_date, announced_date, plus a list of dated milestones.
- Validation: cross-check 50 randomly sampled extractions manually. If accuracy below 95% on date extraction, iterate prompts.
- Cross-reference Form 4 grants with extracted deal timelines: for each grant, compute days_to_announce, days_after_first_contact, days_after_first_offer.
- Label any grant occurring in `[first_contact, announced - 1d]` as a positive MNPI-adjacent example. Annotate with severity (post-offer is stronger than post-first-contact).
- Build a parallel negative set: random Form 4 grants from companies with no M&A event in the following 18 months.

**Deliverable:** `labeled_grants.parquet` with probably 500-1500 positives and a much larger negative pool. Plus a per-deal timeline frame reusable for other analyses.

### Phase 3: Feature engineering (weeks 8-9)

Implement the feature spec from Section 7. Produce a wide grant-level feature frame and a separate company-level governance frame.

- Grant timing features: offsets to nearest earnings/8-K, abnormal returns in pre/post windows.
- Grant terms features: hurdle premium, implied IRR, COC trigger, strike vs market.
- Cadence break features: deviation from company's historical grant pattern.
- Governance features parsed from DEF 14A: comp committee size, meeting count, consultant engagement, chair tenure and independence.
- Activist features: time since 13D, cap raise events.

**Deliverable:** `grant_features.parquet`, `company_governance.parquet`, plus a notebook visualizing the labeled examples in feature space. You should be able to look at a 2-D projection and see the positives clustering.

### Phase 4: Heuristic scorer + first backtest (weeks 10-11)

- Implement a weighted heuristic score using domain knowledge from the blogs. Walker and Mike are essentially the prior.
- Backtest forward returns at 30, 90, 180, 365 days vs sector benchmark.
- Decile analysis: does the top decile of heuristic score outperform?
- Recall analysis on the labeled positive set: how many of them does the heuristic flag at threshold X?

**Deliverable:** First answer to "does this work?" If decile-1 outperforms by a clean margin out of sample, continue. If not, diagnose: bad features, bad labels, or genuinely no alpha.

### Phase 5: Statistical model v2 (weeks 12-13)

- Fit a logistic regression on the labeled set predicting "MNPI-adjacent or positive forward return at 90 days." Use it to learn feature weights.
- Compare to heuristic on backtest metrics.
- Calibration: if the model says 60% probability, do those grants in fact have a 60% positive base rate?

**Deliverable:** v2 score + calibration plot.

### Phase 6: Bayesian model v3 (weeks 14-16)

This is where pymc earns its keep.

- Hierarchical structure: grant -> sector -> governance-hygiene-tier. Pool partial information across sectors for noisy features like hurdle premium.
- Use the merger-background labels as one likelihood, forward returns as a second likelihood, fit jointly. The "dark arts" latent variable is shared.
- Posterior predictive checks against held-out years.
- Output: posterior probability of each grant being a positive event, with credible intervals.

**Deliverable:** v3 model with proper uncertainty quantification.

### Phase 7: Director graph (weeks 17-18)

- Extract director-to-company edges from Form 3/4 reporting owners and DEF 14A director tables.
- Build the graph in NetworkX or a polars-friendly representation.
- Compute "dark artist proximity" features: for each new grant, how many degrees of separation from a director with a flagged history.
- Add this as a feature to v3 and re-fit. Test whether it improves out-of-sample fit.

**Deliverable:** director graph + updated model.

### Phase 8: Live monitoring and alerts (weeks 19-20)

- Daily cron pulling new Form 4s, DEF 14As, 8-Ks, 13Ds.
- Run scoring pipeline on new filings.
- Email or Slack alert when a new filing scores above some posterior probability threshold.
- Watchlist webpage (Streamlit or static HTML) showing current top flags with annotation fields.

**Deliverable:** running system that surfaces new flags daily.

Total: roughly 20 weekends. Realistic for a working professional. Phases 1-4 alone (10 weekends) get you to a working prototype with answers about whether the thesis holds.

## 7. Feature Specification

### Grant-level features (key=accession_number, role)

**Timing features**
- `days_to_next_earnings` — signed; negative means grant before earnings
- `days_from_prev_earnings`
- `days_to_next_8k_material` — for items 1.01, 5.02, 8.01
- `abnormal_return_minus_90_to_minus_1` — vs sector
- `abnormal_return_minus_30_to_minus_1`
- `abnormal_return_plus_1_to_plus_30`
- `abnormal_return_plus_1_to_plus_90`
- `v_pattern_score` — Daines-style V detection in the 90d window

**Terms features**
- `grant_type` — RSU / option / PSU / other
- `strike_price`
- `strike_premium_to_market` — for options; `(strike - close) / close`
- `psu_low_hurdle`, `psu_mid_hurdle`, `psu_high_hurdle`
- `psu_hurdle_premium_to_market` — using mid hurdle
- `psu_implied_irr_low`, `psu_implied_irr_mid` — given vest period
- `change_of_control_trigger` — bool
- `time_to_vest_years`
- `grant_size_dollars`
- `grant_size_pct_outstanding`
- `grant_size_vs_company_history` — z-score vs prior 3 years

**Cadence features**
- `days_off_expected_grant_date` — based on company's historical pattern
- `grant_type_changed_from_prior` — bool
- `is_first_grant_post_ceo_change`
- `is_first_grant_post_13d`
- `is_first_grant_post_cooperation_amendment`

**Recipient features**
- `is_executive` / `is_director`
- `recipient_role` — CEO / CFO / COO / director / other officer
- `recipient_tenure_years`

### Company-level features (key=cik, fiscal_year)

**Governance hygiene**
- `comp_committee_size`
- `comp_committee_meeting_count`
- `comp_consultant_engaged` — bool
- `comp_chair_independence` — categorical
- `comp_chair_is_founder_or_sponsor` — bool
- `unanimous_written_consent_used` — bool
- `governance_hygiene_score` — composite

**Strategic state**
- `days_since_ceo_change`
- `days_since_cfo_change`
- `active_13d_filer_present` — bool
- `top_13d_ownership_pct`
- `recent_cooperation_amendment` — bool, 90-day window

### Director-level features (graph)

- `boards_served_count`
- `prior_flagged_grants_count` — number of times this director was on the comp committee for a flagged grant
- `dark_artist_proximity` — graph distance to nearest known practitioner

## 8. Labeled Dataset Strategy

### Positive examples

Each row: `(cik, accession_number, grant_date, deal_id, days_after_first_contact, days_before_announce, severity)`.

Severity tiers:
- **Tier 1:** grant occurred after a written acquisition offer was received. LHCG-style.
- **Tier 2:** grant occurred after substantive deal discussions had begun (advisors retained, multiple meetings).
- **Tier 3:** grant occurred during preliminary expressions of interest.

Tier 1 are the cleanest training signal. Tier 3 are noisier but more numerous.

### Secondary positives: forward-return labeled

For grants where no M&A event occurred, label by 90-day forward abnormal return percentile. Top 10% positive, bottom 10% negative. Noisier than M&A labels but vastly more data. Use as a second likelihood in the Bayesian model rather than as the primary label.

### Negatives

Random Form 4 grants from companies with no M&A in the following 18 months and forward returns within +/- 1 standard deviation of sector. Sample to roughly 5x positive count to avoid extreme imbalance.

### Validation holdouts

Time-based: train on grants through 2023, validate on 2024-2025, test on 2026 forward. M&A is regime-dependent (deal volume varies with rates and market conditions), so random splits will leak.

## 9. Scoring Approach

### v1: Heuristic

Hand-weighted linear combination based on the patterns in Section 2. Use Walker's and Mike's case studies as the implicit teacher. Sanity check: each named case study from the blogs should score near the top of its filing year's distribution. If EKSO's PSU grant doesn't score in the top 1% of November 2025 grants, the heuristic is wrong.

### v2: Logistic regression

Feature weights learned from labeled data. Regularized (L2). Calibrated via Platt or isotonic. Useful as a benchmark for the Bayesian model and as a fallback when the Bayesian model is too slow for live scoring.

### v3: Hierarchical Bayesian

```
for each sector s:
    for each governance_tier g:
        feature weights ~ Normal(global_weight, sector_sigma)
        latent dark_arts score = sum(weight * feature)
        P(label=1) = sigmoid(score)
```

Partial pooling across sectors handles the fact that a 30% strike premium means something different in biotech versus utilities. Governance tier captures the multiplier effect of poor comp committee hygiene.

Joint likelihood: `log_lik = w1 * log_lik_mnpi_label + w2 * log_lik_forward_return`.

Tune `w1, w2` on validation.

## 10. Backtesting Framework

### Metrics

- **Decile analysis:** mean forward 90-day abnormal return by score decile, with confidence intervals from the label distribution.
- **Sharpe by decile:** if you imagine equal-weighted long top-decile and short bottom-decile, what is the realized Sharpe?
- **MNPI label recall:** at threshold X, what fraction of known M&A-window grants do you flag?
- **Hit rate on tier-1 positives:** narrow precision on the cleanest label class.
- **Time-to-event:** for flagged grants, distribution of days until subsequent material event.

### Pitfalls to handle

- **Survivorship.** Use a delisting-aware price source.
- **Look-ahead.** When computing features, never use information from after the grant date. Especially relevant for "abnormal return after grant" features which can only be inputs to backtest evaluation, not to scoring.
- **Multiple grants per company per year.** Don't double-count. When evaluating forward returns, dedupe at the company-month level.
- **Selection bias from blog cases.** The 9 named tickers are positive cases by selection. Don't use them in validation; use them only for sanity checks of the heuristic.

## 11. Watchlist and Alerts

Watchlist is a polars frame: ticker, current_score, conviction (manual 1-5), thesis_summary, position (none/tracking/long/short), entry_date.

Alert rules:
- New Form 4 with score above v3 posterior probability of 0.7.
- New 8-K Item 5.02 from a watchlist ticker.
- New 13D amendment from a watchlist ticker.
- Form 4 grant date is more than 30 days before the next scheduled earnings AND score above 0.5 (the spring-load setup window).

Channel: email digest morning + Slack webhook for high-urgency.

## 12. Risks, Limitations, and Open Questions

### Known limitations

- **Footnote variability.** PSU vesting conditions in Form 4 footnotes are free-text. LLM extraction will have failure modes; some hurdles are simply not disclosed in Form 4 (RPD case) and only show up later in the proxy or never at all.
- **Filing latency.** Form 4s are filed within 2 business days of the transaction. By the time you score, the market has often already absorbed some signal. The edge is in patterns the market has not yet recognized, not in being faster than other algorithmic readers.
- **Selection bias in case studies.** Walker and Mike write about wins. Survivorship and selection bias in their case archive are real. The merger-background labeled set partially addresses this by giving a less-biased positive sample.
- **Regulatory regime changes.** SEC updated 10b5-1 rules in late 2022 (cooling-off periods, certifications). This shifts the base rate of spring-load behavior. Model should include time-varying intercepts.
- **Sector heterogeneity.** Biotech grant patterns are wildly different from industrials. Hierarchical pooling helps but won't fully fix this.
- **PSUs with undisclosed hurdles.** RPD's Form 4 didn't disclose hurdles. Proxy didn't either. Some signals are just not extractable.

### Open questions

- Universe scope: Russell 3000, Russell 2000, or all listed? Smaller-cap names have weaker coverage but cleaner alpha.
- Inclusion of foreign issuers (20-F filers): probably out of scope for v1.
- Short signals (Pattern F): include or focus on long? My instinct: include as flags but don't trade off them v1.
- Position sizing rules: deliberately out of scope. This is a flagging system, not a portfolio construction system. Keep them separate, the way your CBB model is separate from bet sizing.
- Whether to publish: there's a decision to make eventually about whether this becomes a substack or stays private. That affects how you build the watchlist UI and what you retain in disclosure logs.

## 13. Concrete First Sprint (next 2 weekends)

The highest-leverage starting point is the case study subset.

**Weekend 1:**
1. uv init the repo, scaffold per Section 5.
2. Pin datamule, doc2dict, polars, duckdb, anthropic, plotly, pymc.
3. Pull Form 4 filings for the 9 case study tickers via datamule.
4. Parse the XML into a grants frame. Drop into a notebook and verify the EKSO November 2025 grant, the STMP 2019 grant, and the KODK July 2020 grants are present and structured correctly.

**Weekend 2:**
1. Pull DEFM14A for LHC Group and Twitter (both have known deal backgrounds).
2. Build the LLM extraction prompt for Background of the Merger. Iterate until the extracted timelines match the dates in Mike's posts.
3. Cross-reference: confirm that the LHCG March 1, 2022 grant falls in the `[first_contact, announce - 1]` window from the extracted timeline.
4. Write that up as the first ADR proving the labeling approach works end-to-end on a known case.

After that, scale up to the full Form 4 corpus and the full M&A deal universe.

## Appendix: Decisions to Revisit

- Whether to use datamule's paid tar archive or stick with free pip-package downloads through SEC. Decision will be cost-driven once we know pull volume.
- Whether to fine-tune a small model on the SEC-EDGAR HuggingFace dataset for footnote extraction, vs. paying Claude API per call. Probably not worth it for v1; revisit if extraction costs become material.
- Whether to incorporate Form 144 (proposed insider sales) as a complementary signal. Worth exploring but likely lower-signal than Form 4.
- Whether to build the activist 13D parser before or after governance hygiene parsing. Currently sequenced governance first because it amplifies all other signals.
