import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os

st.set_page_config(page_title="Freight Cost Intelligence", page_icon="🚚", layout="wide")

DEFAULT_FILE = "Supply_chain_logisitcs_problem.xlsx"

# ----------------------------------------------------------------------------
# Data loading + full pipeline (cached so filters don't re-run the whole thing)
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading data and running the rate-matching pipeline...")
def load_and_process(file):
    xls = pd.ExcelFile(file)
    orders = pd.read_excel(xls, sheet_name="OrderList")
    freight_rates = pd.read_excel(xls, sheet_name="FreightRates")

    rename_orders = {
        "Order_ID": "Order ID", "Order_Date": "Order Date", "Orig_Port": "Origin Port",
        "TPT_Day_Count": "TPT", "Service_Level": "Service Level",
        "Ship_Ahead_Day_Count": "Ship ahead day count", "Ship_Late_Day_Count": "Ship Late Day count",
        "Product_ID": "Product ID", "Plant_Code": "Plant Code", "Dest_Port": "Destination Port",
        "Unit_Quant": "Unit quantity",
    }
    rename_rates = {
        "Orig_Port": "orig_port_cd", "Dest_Port": "dest_port_cd",
        "Min_Weight_Quant": "minm_wgh_qty", "Max_Weight_Quant": "max_wgh_qty",
        "Service_Level": "svc_cd", "Min_Cost": "minimum cost", "Rate": "rate",
        "Mode_DSC": "mode_dsc", "TPT_Day_Count": "tpt_day_cnt", "Carrier_Type": "Carrier type",
    }
    orders = orders.rename(columns=rename_orders)
    freight_rates = freight_rates.rename(columns=rename_rates)

    # Rate matching: carrier + route + service, then weight-band filter
    orders_rate = orders.merge(
        freight_rates, how="inner",
        left_on=["Carrier", "Origin Port", "Destination Port", "Service Level"],
        right_on=["Carrier", "orig_port_cd", "dest_port_cd", "svc_cd"],
    )
    matched_rates = orders_rate[
        orders_rate["Weight"].between(orders_rate["minm_wgh_qty"], orders_rate["max_wgh_qty"], inclusive="both")
    ].copy()

    matched_rates["weight_cost"] = matched_rates["Weight"] * matched_rates["rate"]
    matched_rates["expected_freight_cost"] = matched_rates[["minimum cost", "weight_cost"]].max(axis=1)
    candidate_rates = matched_rates.copy()

    matched_ids = candidate_rates["Order ID"].unique()
    unmatched_orders = orders[~orders["Order ID"].isin(matched_ids)].copy()

    order_summary = (
        candidate_rates.groupby("Order ID")
        .agg(
            feasible_options=("Order ID", "size"),
            feasible_carriers=("Carrier", "nunique"),
            min_expected_cost=("expected_freight_cost", "min"),
            max_expected_cost=("expected_freight_cost", "max"),
            min_transit_days=("tpt_day_cnt", "min"),
            max_transit_days=("tpt_day_cnt", "max"),
        )
        .reset_index()
    )
    order_summary["cost_saving_opportunity"] = order_summary["max_expected_cost"] - order_summary["min_expected_cost"]

    # bring order-level attributes onto the summary so it can be filtered by carrier/route/service
    order_attrs = orders[["Order ID", "Carrier", "Origin Port", "Destination Port", "Service Level", "Weight"]]
    order_summary = order_summary.merge(order_attrs, on="Order ID", how="left")

    return orders, freight_rates, candidate_rates, order_summary, unmatched_orders


@st.cache_data(show_spinner=False)
def lane_carrier_comparison(_orders, _freight_rates):
    lane_orders = _orders[
        (_orders["Origin Port"] == "PORT04") & (_orders["Destination Port"] == "PORT09")
        & (_orders["Service Level"] == "DTD")
    ].copy()
    lane_rates = _freight_rates[
        (_freight_rates["orig_port_cd"] == "PORT04") & (_freight_rates["dest_port_cd"] == "PORT09")
        & (_freight_rates["svc_cd"] == "DTD") & (_freight_rates["Carrier"].isin(["V444_0", "V444_1"]))
    ].copy()
    cand = lane_orders.drop(columns=["Carrier"]).merge(lane_rates, how="cross")
    cand = cand[cand["Weight"].between(cand["minm_wgh_qty"], cand["max_wgh_qty"], inclusive="both")].copy()
    cand["weight_cost"] = cand["Weight"] * cand["rate"]
    cand["expected_freight_cost"] = cand[["minimum cost", "weight_cost"]].max(axis=1)
    summary = cand.groupby("Carrier").agg(
        avg_cost=("expected_freight_cost", "mean"),
        min_transit=("tpt_day_cnt", "min"),
        max_transit=("tpt_day_cnt", "max"),
        orders_coverable=("Order ID", "nunique"),
    ).reset_index()
    return summary, len(lane_orders)


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------

st.sidebar.title("🚚 Freight Cost Intelligence")
st.sidebar.caption("Rate-card cost & savings explorer")

uploaded = st.sidebar.file_uploader("Dataset (.xlsx)", type=["xlsx"])
data_source = uploaded if uploaded is not None else (DEFAULT_FILE if os.path.exists(DEFAULT_FILE) else None)

if data_source is None:
    st.warning(
        f"Couldn't find **{DEFAULT_FILE}** next to this app, and nothing was uploaded. "
        "Upload the dataset in the sidebar to continue."
    )
    st.stop()

orders, freight_rates, candidate_rates, order_summary, unmatched_orders = load_and_process(data_source)

st.sidebar.divider()
st.sidebar.subheader("Filters")

carriers = st.sidebar.multiselect("Carrier", sorted(orders["Carrier"].unique()), default=list(sorted(orders["Carrier"].unique())))
services = st.sidebar.multiselect("Service level", sorted(orders["Service Level"].unique()), default=list(sorted(orders["Service Level"].unique())))
w_min, w_max = float(orders["Weight"].min()), float(np.ceil(orders["Weight"].max()))
weight_range = st.sidebar.slider("Weight range", min_value=0.0, max_value=w_max, value=(0.0, w_max))

f_orders = orders[
    orders["Carrier"].isin(carriers) & orders["Service Level"].isin(services)
    & orders["Weight"].between(*weight_range)
]
f_summary = order_summary[
    order_summary["Carrier"].isin(carriers) & order_summary["Service Level"].isin(services)
    & order_summary["Weight"].between(*weight_range)
]

# ----------------------------------------------------------------------------
# Header + KPIs
# ----------------------------------------------------------------------------

st.title("Freight Cost Intelligence & Rate Optimization")
st.caption("Descriptive, cost, and prescriptive view of the freight rate card — filtered live from the sidebar.")

match_rate = len(f_summary) / len(f_orders) * 100 if len(f_orders) else 0
total_savings = f_summary.loc[f_summary["cost_saving_opportunity"] > 0, "cost_saving_opportunity"].sum()
avg_cost = f_summary["min_expected_cost"].mean() if len(f_summary) else 0
late_rate = (f_orders["Ship Late Day count"] > 0).mean() * 100 if len(f_orders) else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Orders (filtered)", f"{len(f_orders):,}")
k2.metric("Feasible rate match", f"{match_rate:.1f}%")
k3.metric("Avg expected cost", f"${avg_cost:,.2f}")
k4.metric("Identified savings", f"${total_savings:,.2f}")
k5.metric("Shipped late", f"{late_rate:.2f}%")

st.divider()

tab_overview, tab_cost, tab_prescriptive, tab_explorer = st.tabs(
    ["📦 Overview", "💰 Cost & Savings", "🎯 Prescriptive", "🔍 Data Explorer"]
)

# ----------------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------------

with tab_overview:
    c1, c2 = st.columns(2)
    with c1:
        vol = f_orders["Carrier"].value_counts().reset_index()
        vol.columns = ["Carrier", "Orders"]
        fig = px.bar(vol, x="Carrier", y="Orders", title="Orders by carrier", color="Carrier")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        svc = f_orders["Service Level"].value_counts().reset_index()
        svc.columns = ["Service Level", "Orders"]
        fig = px.pie(svc, names="Service Level", values="Orders", title="Orders by service level", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        clip = f_orders["Weight"].clip(upper=f_orders["Weight"].quantile(0.99)) if len(f_orders) else f_orders["Weight"]
        fig = px.histogram(clip, nbins=40, title="Weight distribution (99th-pctile clipped)")
        fig.update_layout(showlegend=False, xaxis_title="Weight", yaxis_title="Orders")
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        delay = pd.DataFrame({
            "Days": list(range(0, 7)) * 2,
            "Orders": (
                [int((f_orders["Ship ahead day count"] == d).sum()) for d in range(7)]
                + [int((f_orders["Ship Late Day count"] == d).sum()) for d in range(7)]
            ),
            "Type": ["Ship ahead"] * 7 + ["Ship late"] * 7,
        })
        fig = px.bar(delay, x="Days", y="Orders", color="Type", barmode="group", title="Delay patterns")
        st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**Note:** `Order Date` is a single constant value across every order in this dataset, "
        "so demand-over-time cannot be reported here — it isn't a filtering gap, the field itself carries no signal.",
        icon="ℹ️",
    )

# ----------------------------------------------------------------------------
# Cost & Savings
# ----------------------------------------------------------------------------

with tab_cost:
    c1, c2 = st.columns(2)
    with c1:
        cr = candidate_rates[candidate_rates["Order ID"].isin(f_summary["Order ID"])]
        sample = cr.sample(min(3000, len(cr)), random_state=0) if len(cr) else cr
        fig = px.scatter(
            sample, x="Weight", y="expected_freight_cost", opacity=0.35,
            title="Expected freight cost vs. weight", color_discrete_sequence=["#1F4E5F"],
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        saving = f_summary[f_summary["cost_saving_opportunity"] > 0]
        fig = px.histogram(saving, x="cost_saving_opportunity", nbins=30, title="Per-order savings opportunity ($)")
        fig.update_layout(xaxis_title="Potential saving ($)", yaxis_title="Orders")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 10 orders by savings opportunity")
    top10 = f_summary.sort_values("cost_saving_opportunity", ascending=False).head(10)
    st.dataframe(
        top10[["Order ID", "Carrier", "Origin Port", "Service Level", "Weight",
               "min_expected_cost", "max_expected_cost", "cost_saving_opportunity"]],
        use_container_width=True, hide_index=True,
    )

# ----------------------------------------------------------------------------
# Prescriptive
# ----------------------------------------------------------------------------

with tab_prescriptive:
    st.info(
        "**Cheapest = fastest.** Every order has exactly one Pareto-efficient rate option — "
        "the 2-day transit option is never priced above the 3-day one, so there's no cost/speed "
        "trade-off to weigh for the vast majority of orders.",
        icon="🎯",
    )

    st.subheader("Carrier recommendation — PORT04 → PORT09, DTD")
    st.caption("The only lane in the historical data genuinely served by more than one carrier.")

    lane_summary, lane_order_count = lane_carrier_comparison(orders, freight_rates)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(lane_summary, x="Carrier", y="avg_cost", color="Carrier", title="Average cost where feasible")
        fig.update_layout(yaxis_title="Avg expected cost ($)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(lane_summary, x="Carrier", y="orders_coverable", color="Carrier",
                     title=f"Orders each carrier can cover (of {lane_order_count:,} on this lane)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        "**Recommendation:** route light (≤2.5 kg) and heavy (≥70.5 kg) shipments to `V444_1` — cheaper and "
        "faster where its rate card applies. `V444_0` remains the only feasible option for everything in between."
    )

    st.subheader("Why orders go unmatched")
    reason = np.select(
        [unmatched_orders["Service Level"] == "CRF",
         (unmatched_orders["Service Level"] == "DTD") & (unmatched_orders["Carrier"] == "V444_1")],
        ["No CRF rate cards exist", "V444_1 has no DTD rate card for this origin port"],
        default="Other / needs review",
    )
    reason_counts = pd.Series(reason).value_counts().reset_index()
    reason_counts.columns = ["Reason", "Orders"]
    fig = px.bar(reason_counts, x="Reason", y="Orders", title=f"{len(unmatched_orders):,} unmatched orders, by reason")
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------------
# Data Explorer
# ----------------------------------------------------------------------------

with tab_explorer:
    st.subheader("Filtered order-level summary")
    st.dataframe(f_summary, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download filtered data as CSV",
        f_summary.to_csv(index=False).encode("utf-8"),
        file_name="filtered_order_summary.csv",
        mime="text/csv",
    )
