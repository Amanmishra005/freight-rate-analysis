# Freight Cost Intelligence & Rate Optimization

Rate-card cost matching, savings-opportunity analysis, and carrier recommendations for a multi-carrier freight
network — built as an end-to-end pipeline from raw Excel data to an interactive Streamlit dashboard.

> Built on the *Brunel University London Supply Chain Logistics Problem* dataset (9,215 orders, 1,540 freight
> rate-card rows, 3 carriers, 46 customers, 772 products).

**[Live demo →](https://amanmishra005-freight-rate-analysis-app-kjrs33.streamlit.app/)** &nbsp;·&nbsp; **[Jupyter analysis →](notebooks/02_freight_cost_analysis_completed.ipynb)** &nbsp;·&nbsp; **[Dashboard code →](app.py)**

<!-- Replace the live demo link once deployed, e.g. on Streamlit Community Cloud -->

---

##  The problem

A shipper works with 3 carriers, each publishing a rate card of `(origin port, destination port, service level,
weight band) → price`. For any given order, several rate-card rows can legitimately apply — and they don't always
agree on price. The business questions this project answers:

1. **Which orders can even be priced?** Not every order has a matching rate-card entry.
2. **Where the rate cards disagree, are we being billed at the cheapest matching rate?**
3. **Is there a cost/speed trade-off** — does the cheapest option ever cost you transit time?
4. **On lanes served by more than one carrier, which carrier should actually be recommended?**

Approach

1. **Data quality pass** — duplicate/null checks, cardinality checks on carriers, ports, customers, products.
2. **Rate matching** — join orders to freight rates on `Carrier` + `Origin/Destination Port` + `Service Level`
   (deliberately **not** on transit-time fields, which describe the outcome, not the rate), then filter to rows
   whose weight band actually contains the shipment's weight.
3. **Cost calculation** — standard rate-card formula: `expected_freight_cost = max(minimum_cost, weight × rate)`.
4. **Savings analysis** — for orders that matched more than one rate row at different prices, the gap between the
   cheapest and most expensive matched rate is the identifiable savings opportunity.
5. **Prescriptive layer** — a Pareto-efficiency check across (cost, transit days) per order, plus a head-to-head
   carrier comparison on the one lane genuinely served by two carriers.
6. **Delivery** — clean order-level CSVs exported for Power BI, and the same pipeline reused live inside a
   Streamlit dashboard with sidebar filters (carrier, service level, weight range).

## 📊 Key findings

| Question | Finding |
|---|---|
| Rate-match coverage | **6,991 / 9,215 orders (75.9%)** matched at least one feasible rate-card option |
| Why orders go unmatched | **2,224 orders (24.1%)** unmatched — 854 have `Service Level = CRF`, for which no rate cards exist at all; 1,370 are `DTD` orders on a route `V444_1` doesn't publish a DTD rate for |
| Billing consistency | **727 orders (10.4%)** of matched orders had multiple feasible rate rows quoting different prices — the gap between best and worst matched rate is a real savings-opportunity signal |
| Cost vs. speed trade-off | **None** — every order's cheapest feasible rate option is also its fastest (or tied-fastest). "Pick cheapest" and "pick fastest" are the same instruction in this rate card |
| Carrier recommendation | On `PORT04 → PORT09` (`DTD`), the only lane genuinely served by 2 carriers: `V444_1` is cheaper (avg ≈$2.11 vs ≈$3.61) and faster (1–2 vs 2–3 days) — but its rate card only covers light (≤~2.5 kg) and heavy (≥~70.5 kg) shipments. `V444_0` is the only feasible option for everything in between |

> The dataset's monetary values are small/normalized (e.g. a single order's cheapest rate can be ~$1.30), so the
> headline dollar figures are modest in absolute terms — the value of this project is the **methodology**: a
> reusable pipeline for rate-match coverage, billing-consistency auditing, and carrier recommendation that scales
> to any size of rate card and order volume.

## 🖥️ Dashboard

The Streamlit app (`app.py`) reuses the exact same pipeline as the notebook and adds:

- **KPI strip**: filtered order count, feasible-match rate, average expected cost, identified savings, late-ship rate
- **Overview tab**: orders by carrier/service level, weight distribution, ship-ahead/ship-late patterns
- **Cost & Savings tab**: cost-vs-weight scatter, savings-opportunity distribution, top-10 orders by savings
- **Prescriptive tab**: the Pareto-efficiency finding, the carrier recommendation on the multi-carrier lane, and a
  breakdown of *why* unmatched orders are unmatched
- **Data Explorer tab**: the full filtered order-level summary, downloadable as CSV
- Sidebar filters for carrier, service level, and weight range — everything above updates live
- A file-uploader fallback, so the app also works with a different extract using the same sheet names/columns

<!-- Add a screenshot or GIF here once you have one, e.g.: -->
<!-- ![Dashboard overview](docs/screenshot-overview.png) -->

## 🛠️ Tech stack

- **Python** — pandas, numpy for the pipeline
- **Jupyter** — exploratory + final analysis notebooks
- **Plotly / Matplotlib** — visualization (Plotly in the dashboard, Matplotlib in the notebook)
- **Streamlit** — interactive dashboard
- **Power BI-ready exports** — clean, join-key-friendly CSVs for a BI tool of choice

## 📁 Repo structure

```
freight-cost-intelligence/
├── app.py                                        # Streamlit dashboard
├── requirements.txt
├── data/
│   └── Supply_chain_logisitcs_problem.xlsx        # source dataset
├── notebooks/
│   ├── 01_data_understanding.ipynb                # exploratory data analysis
│   └── 02_freight_cost_analysis_completed.ipynb   # full pipeline + findings + Power BI export
├── powerbi_exports/                               # generated CSVs (order summary, unmatched orders, etc.)
└── README.md
```

## ▶️ Getting started

```bash
git clone https://github.com/<your-username>/freight-cost-intelligence.git
cd freight-cost-intelligence
pip install -r requirements.txt
```

**Run the analysis notebook:**

```bash
jupyter notebook notebooks/02_freight_cost_analysis_completed.ipynb
```

**Run the dashboard:**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Place `Supply_chain_logisitcs_problem.xlsx` next to `app.py` (or in `data/`,
adjusting `DEFAULT_FILE` in `app.py`), or just upload a file with the same sheet names via the sidebar.

## 📦 Dataset

Source: *Brunel University London — Supply Chain Logistics Problem* dataset.

| Sheet | Rows | Used for |
|---|---|---|
| `OrderList` | 9,215 | Order-level shipment records (carrier, ports, service level, weight, ship timing) |
| `FreightRates` | 1,540 | Carrier rate cards by route, service level, and weight band |
| `WhCosts`, `WhCapacities`, `ProductsPerPlant`, `VmiCustomers`, `PlantPorts` | — | Loaded but not used in this analysis; natural extensions for a network/warehouse-cost optimization follow-up |

## ⚠️ Limitations & honest caveats

- **Single destination port** — all orders ship to `PORT09`, so this is a many-origins-to-one-hub network, not a
  general multi-lane optimization.
- **`Order Date` is constant** across every order in this extract, so no time-series / demand-over-time analysis
  is possible from this dataset.
- **Small monetary scale** — rate values appear normalized/synthetic rather than production billing data; treat
  dollar totals as illustrative of the method, not a real cost-recovery claim.
- **Only one lane has genuine multi-carrier competition** — the carrier-recommendation finding, while real, applies
  narrowly (`PORT04 → PORT09`, `DTD`); it isn't a general "always pick carrier X" rule.

## 🚀 Possible extensions

- Bring in `WhCosts` / `WhCapacities` for a joint transportation + warehousing cost model
- Turn the carrier recommendation into a proper linear-programming assignment (e.g. with `PuLP`) instead of a
  descriptive comparison
- Schedule the pipeline (e.g. with `Prefect` or a simple cron + script) to refresh the Power BI exports automatically

## 📄 License

This project is available under the [MIT License](LICENSE).

## 👤 Author

**Aman Mishra**
**[LinkedIn→](https://www.linkedin.com/in/aman-mishra5/)**
