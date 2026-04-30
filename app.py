from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Post65 Building Stock Dashboard",
    page_icon="🏛️",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_public"

NL_CSV = DATA_DIR / "bag_buildings_by_year_nl.csv"
PROVINCE_CSV = DATA_DIR / "bag_buildings_by_year_province.csv"
MUNICIPALITY_CSV = DATA_DIR / "bag_buildings_by_year_municipality.csv"
MONUMENTS_CSV = DATA_DIR / "rijksmonumenten_summary.csv"
MATCHED_MONUMENTS_CSV = DATA_DIR / "rijksmonumenten_matched.csv"
BUILDING_POINTS_CSV = DATA_DIR / "bag_buildings_public_points.csv"


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def clean_year_count(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["building_count"] = pd.to_numeric(df["building_count"], errors="coerce").fillna(0)
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df


def fmt_int(x):
    if pd.isna(x):
        return "n/a"
    return f"{int(x):,}".replace(",", ".")


def csv_button(df: pd.DataFrame, filename: str, label: str):
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


df_nl = clean_year_count(load_csv(NL_CSV))
df_prov = clean_year_count(load_csv(PROVINCE_CSV))
df_muni = clean_year_count(load_csv(MUNICIPALITY_CSV))
df_mon = load_csv(MONUMENTS_CSV)
df_matched = load_csv(MATCHED_MONUMENTS_CSV)
df_points = load_csv(BUILDING_POINTS_CSV)


st.title("Post65 Building Stock & Heritage Protection in the Netherlands")
st.caption("BAG provides construction year/building stock. Rijksmonumenten provides protected heritage status.")

if df_nl.empty:
    st.error("Missing data_public/bag_buildings_by_year_nl.csv")
    st.stop()

min_year = int(df_nl["year"].min())
max_year = int(df_nl["year"].max())

if not df_points.empty:
    df_points["year"] = pd.to_numeric(df_points["year"], errors="coerce")
    df_points["lat"] = pd.to_numeric(df_points["lat"], errors="coerce")
    df_points["lon"] = pd.to_numeric(df_points["lon"], errors="coerce")
    df_points = df_points.dropna(subset=["year", "lat", "lon"])
    df_points["year"] = df_points["year"].astype(int)

# -----------------------------
# NEW PRECISE YEAR FILTER
# -----------------------------
with st.sidebar:
    st.header("Filters")

    st.markdown("Construction year range")

    col_a, col_b = st.columns(2)

    start_year = col_a.number_input(
        "Start year",
        min_value=min_year,
        max_value=max_year,
        value=1965,
        step=1
    )

    end_year = col_b.number_input(
        "End year",
        min_value=min_year,
        max_value=max_year,
        value=1990,
        step=1
    )

    if start_year > end_year:
        st.error("Start year must be before end year.")
        st.stop()

    province_options = ["All Netherlands"]
    if not df_prov.empty and "province_name" in df_prov.columns:
        province_options += sorted(df_prov["province_name"].dropna().unique().tolist())

    selected_province = st.selectbox("Province", province_options)


filtered_points = df_points[
    (df_points["year"] >= start_year) &
    (df_points["year"] <= end_year)
].copy()

if selected_province != "All Netherlands" and not filtered_points.empty:
    filtered_points = filtered_points[
        filtered_points["province_name"] == selected_province
    ].copy()

# -----------------------------
# REST OF THE APP (unchanged)
# -----------------------------

total_buildings_nl = df_nl["building_count"].sum()
selected_nl = df_nl[(df_nl["year"] >= start_year) & (df_nl["year"] <= end_year)]
selected_buildings_nl = selected_nl["building_count"].sum()
selected_pct_nl = selected_buildings_nl / total_buildings_nl * 100 if total_buildings_nl else 0

protected_total = None
if not df_mon.empty and "protected_monuments_total" in df_mon.columns:
    protected_total = df_mon["protected_monuments_total"].iloc[0]

tabs = st.tabs([
    "Overview",
    "Year slider analysis",
    "Province comparison",
    "Protected monuments",
    "Building locations",
    "Downloads",
    "Method",
])

with tabs[0]:
    st.subheader("National evidence summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total BAG buildings", fmt_int(total_buildings_nl))
    c2.metric(f"Buildings built {start_year}–{end_year}", fmt_int(selected_buildings_nl))
    c3.metric("Share of total BAG stock", f"{selected_pct_nl:.2f}%")
    c4.metric("Protected monuments in dataset", fmt_int(protected_total))

    st.markdown("### Copy-ready petition sentence")

    sentence = (
        f"According to the BAG building-stock export, {fmt_int(selected_buildings_nl)} buildings "
        f"in the Netherlands were built between {start_year} and {end_year}, representing "
        f"{selected_pct_nl:.2f}% of the current registered building stock. "
        f"The Rijksmonumenten dataset is used separately to represent nationally protected heritage."
    )

    st.text_area("Evidence text", sentence, height=130)

    summary = pd.DataFrame([{
        "start_year": start_year,
        "end_year": end_year,
        "total_bag_buildings": int(total_buildings_nl),
        "selected_period_buildings": int(selected_buildings_nl),
        "selected_period_percentage": selected_pct_nl,
        "protected_monuments_total": protected_total,
    }])

    csv_button(summary, f"post65_summary_{start_year}_{end_year}.csv", "Download current summary CSV")

with tabs[1]:
    st.subheader("Building stock by construction year")

    chart_df = df_nl.copy()
    chart_df["period"] = chart_df["year"].apply(
        lambda y: f"Selected {start_year}–{end_year}" if start_year <= y <= end_year else "Other years"
    )

    fig = px.bar(
        chart_df,
        x="year",
        y="building_count",
        color="period",
        title=f"National BAG buildings by construction year ({start_year}–{end_year} selected)",
        labels={
            "year": "Construction year",
            "building_count": "Number of BAG buildings",
            "period": "Period",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(selected_nl, use_container_width=True)
    csv_button(selected_nl, f"bag_buildings_nl_{start_year}_{end_year}.csv", "Download selected national years")

with tabs[2]:
    st.subheader("Province comparison")

    if df_prov.empty:
        st.warning("Missing data_public/bag_buildings_by_year_province.csv")
    else:
        if selected_province != "All Netherlands":
            work = df_prov[df_prov["province_name"] == selected_province].copy()
        else:
            work = df_prov.copy()

        total_by_prov = (
            df_prov.groupby("province_name", as_index=False)["building_count"]
            .sum()
            .rename(columns={"building_count": "total_buildings"})
        )

        selected_by_prov = (
            df_prov[(df_prov["year"] >= start_year) & (df_prov["year"] <= end_year)]
            .groupby("province_name", as_index=False)["building_count"]
            .sum()
            .rename(columns={"building_count": "selected_period_buildings"})
        )

        prov_summary = total_by_prov.merge(selected_by_prov, on="province_name", how="left")
        prov_summary["selected_period_buildings"] = prov_summary["selected_period_buildings"].fillna(0)
        prov_summary["selected_period_percentage"] = (
            prov_summary["selected_period_buildings"] / prov_summary["total_buildings"] * 100
        )

        if selected_province != "All Netherlands":
            prov_summary = prov_summary[prov_summary["province_name"] == selected_province]

        fig = px.bar(
            prov_summary.sort_values("selected_period_percentage", ascending=False),
            x="province_name",
            y="selected_period_percentage",
            hover_data=["total_buildings", "selected_period_buildings"],
            title=f"Share of buildings built {start_year}–{end_year} by province",
            labels={
                "province_name": "Province",
                "selected_period_percentage": "Selected-period share (%)",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(prov_summary, use_container_width=True)
        csv_button(prov_summary, f"province_summary_{start_year}_{end_year}.csv", "Download province summary")

with tabs[3]:
    st.subheader("Protected monuments dataset")

    if df_mon.empty:
        st.warning("Missing data_public/rijksmonumenten_summary.csv")
    else:
        st.dataframe(df_mon, use_container_width=True)

    if not df_matched.empty:
        st.markdown("### Matched monument records")
        st.dataframe(df_matched, use_container_width=True)
        csv_button(df_matched, "rijksmonumenten_matched.csv", "Download matched monuments")
    else:
        st.info("No matched monuments file found. Optional: add data_public/rijksmonumenten_matched.csv")

with tabs[4]:
    st.subheader("Download dashboard datasets")

    csv_button(df_nl, "bag_buildings_by_year_nl.csv", "Download national BAG by year")

    if not df_prov.empty:
        csv_button(df_prov, "bag_buildings_by_year_province.csv", "Download BAG by province/year")

    if not df_muni.empty:
        csv_button(df_muni, "bag_buildings_by_year_municipality.csv", "Download BAG by municipality/year")

    if not df_mon.empty:
        csv_button(df_mon, "rijksmonumenten_summary.csv", "Download monument summary")


with tabs[5]:
    st.subheader("Building locations")

    if df_points.empty:
        st.warning("Missing data_public/bag_buildings_public_points.csv")
    else:
        st.write(
            f"Showing buildings constructed between {start_year} and {end_year}"
        )

        st.metric("Buildings in current map/filter", fmt_int(len(filtered_points)))

        csv_button(
            filtered_points,
            f"buildings_{start_year}_{end_year}_{selected_province}.csv",
            "Download selected building list as CSV"
        )

        max_points = st.slider(
            "Maximum points to display on map",
            min_value=1000,
            max_value=50000,
            value=10000,
            step=1000
        )

        map_df = filtered_points.head(max_points)

        st.map(
            map_df,
            latitude="lat",
            longitude="lon",
            size=2
        )

        st.dataframe(
            filtered_points[[
                "pand_id",
                "year",
                "province_name",
                "municipality_name",
                "pandstatus",
                "lat",
                "lon"
            ]],
            use_container_width=True
        )

with tabs[6]:
    st.subheader("Method")

    st.markdown("""
                
**Core distinction**

- BAG is used for the denominator: the total building stock and the construction year filter.
- Rijksmonumenten is used for the protected heritage layer.

**Main calculation**

```text
Selected-period share = BAG buildings built in selected year range / total BAG buildings
```
""")