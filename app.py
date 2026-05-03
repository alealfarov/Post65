from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

# ============================================================
# Page config
# ============================================================
st.set_page_config(
    page_title="Post65 Building Stock Dashboard",
    page_icon="🏛️",
    layout="wide",
)

# ============================================================
# Paths
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_public"

# Existing exported CSVs from PostgreSQL
NL_CSV = DATA_DIR / "bag_buildings_by_year_nl.csv"
PROVINCE_CSV = DATA_DIR / "bag_buildings_by_year_province.csv"
MUNICIPALITY_CSV = DATA_DIR / "bag_buildings_by_year_municipality.csv"
MONUMENTS_CSV = DATA_DIR / "rijksmonumenten_summary.csv"
MATCHED_MONUMENTS_CSV = DATA_DIR / "rijksmonumenten_matched.csv"
BUILDING_POINTS_CSV = DATA_DIR / "bag_buildings_public_points.csv"

# Heritage-status CSVs
POST65_NOMINATED_CSV = DATA_DIR / "post65_nominated_buildings.csv"
POST65_OBJECTS_CSV = DATA_DIR / "post65_objects.csv"
POST65_MATCHED_CSV = DATA_DIR / "post65_nominated_matched.csv"
MUNICIPAL_HERITAGE_CSV = DATA_DIR / "municipal_heritage_matched.csv"


# ============================================================
# Helpers
# ============================================================
@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV safely. Return empty dataframe if file does not exist."""
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.warning(f"Could not read {path.name}: {e}")
        return pd.DataFrame()


def clean_year_count(df: pd.DataFrame) -> pd.DataFrame:
    """Clean year-count tables with columns: year, building_count."""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "year" not in df.columns or "building_count" not in df.columns:
        return pd.DataFrame()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["building_count"] = pd.to_numeric(df["building_count"], errors="coerce").fillna(0)
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df


def clean_points(df: pd.DataFrame) -> pd.DataFrame:
    """Clean point datasets when they contain year/lat/lon."""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    for col in ["year", "bag_year", "bouwjaar", "lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "year" in df.columns:
        df = df.dropna(subset=["year"])
        df["year"] = df["year"].astype(int)

    if {"lat", "lon"}.issubset(df.columns):
        df = df.dropna(subset=["lat", "lon"], how="any")

    return df


def clean_postcode(value):
    if pd.isna(value):
        return None
    value = str(value).strip().upper().replace(" ", "")
    if value in ["", "NAN", "NONE", "NULL"]:
        return None
    return value


def fmt_int(x):
    if x is None or pd.isna(x):
        return "n/a"
    return f"{int(round(float(x))):,}".replace(",", ".")


def csv_button(df: pd.DataFrame, filename: str, label: str):
    if df.empty:
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


def make_period_summary(df: pd.DataFrame, group_cols, start_year: int, end_year: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    if "building_count" not in df.columns or "year" not in df.columns:
        return pd.DataFrame()

    total = (
        df.groupby(group_cols, as_index=False)["building_count"]
        .sum()
        .rename(columns={"building_count": "total_buildings"})
    )

    selected = (
        df[(df["year"] >= start_year) & (df["year"] <= end_year)]
        .groupby(group_cols, as_index=False)["building_count"]
        .sum()
        .rename(columns={"building_count": "selected_period_buildings"})
    )

    out = total.merge(selected, on=group_cols, how="left")
    out["selected_period_buildings"] = out["selected_period_buildings"].fillna(0)
    out["selected_period_percentage"] = (
        out["selected_period_buildings"] / out["total_buildings"].replace(0, pd.NA) * 100
    ).fillna(0)
    return out


def province_value_to_key(value):
    if pd.isna(value):
        return ""
    s = str(value).strip().lower()
    replacements = {
        "fryslân": "friesland",
        "fryslan": "friesland",
        "noord holland": "noord-holland",
        "zuid holland": "zuid-holland",
        "noord brabant": "noord-brabant",
    }
    return replacements.get(s, s)


def filter_by_province(df: pd.DataFrame, selected_province: str) -> pd.DataFrame:
    if df.empty or selected_province == "All Netherlands":
        return df

    province_cols = ["province_name", "province", "provincienaam"]
    selected_key = province_value_to_key(selected_province)

    for col in province_cols:
        if col in df.columns:
            return df[df[col].apply(province_value_to_key) == selected_key].copy()

    return df


def safe_nunique(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].dropna().nunique())


def normalize_postcode_columns(dfs):
    for df in dfs:
        if df.empty:
            continue
        for col in ["postcode", "postcode_norm", "bag_postcode"]:
            if col in df.columns:
                df[col] = df[col].apply(clean_postcode)


def choose_post65_source(df_objects: pd.DataFrame, df_raw: pd.DataFrame) -> pd.DataFrame:
    """Prefer the exported semantic view post65_objects.csv; otherwise use raw nominated CSV."""
    if not df_objects.empty:
        return df_objects
    return df_raw


def show_optional_dataframe(df: pd.DataFrame, label: str, filename: str):
    if df.empty:
        st.info(f"No {label} file found yet.")
    else:
        st.dataframe(df, use_container_width=True)
        csv_button(df, filename, f"Download {label} CSV")


# ============================================================
# Load data
# ============================================================
df_nl = clean_year_count(load_csv(NL_CSV))
df_prov = clean_year_count(load_csv(PROVINCE_CSV))
df_muni = clean_year_count(load_csv(MUNICIPALITY_CSV))

# These datasets may have heterogeneous schemas, so do not over-clean them.
df_mon = load_csv(MONUMENTS_CSV)
df_matched = load_csv(MATCHED_MONUMENTS_CSV)
df_points = clean_points(load_csv(BUILDING_POINTS_CSV))

# Post65: prefer post65_objects.csv semantic export; fallback to raw nominated file.
df_post65_raw = load_csv(POST65_NOMINATED_CSV)
df_post65_objects = load_csv(POST65_OBJECTS_CSV)
df_post65 = choose_post65_source(df_post65_objects, df_post65_raw)
df_post65_matched = load_csv(POST65_MATCHED_CSV)
df_municipal_heritage = load_csv(MUNICIPAL_HERITAGE_CSV)

normalize_postcode_columns([df_matched, df_post65, df_post65_matched, df_municipal_heritage])

# Clean coordinates only where they exist.
for df in [df_post65, df_post65_matched, df_municipal_heritage, df_matched]:
    if not df.empty:
        for col in ["lat", "lon", "year", "bag_year", "bouwjaar"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")


# ============================================================
# App title
# ============================================================
st.title("Post65 Building Stock & Heritage Protection in the Netherlands")
st.caption(
    "BAG provides construction year and building stock. "
    "Rijksmonumenten, Post65 nominated objects, and municipal datasets represent different heritage layers."
)

if df_nl.empty:
    st.error("Missing or invalid data_public/bag_buildings_by_year_nl.csv")
    st.stop()

min_year = int(df_nl["year"].min())
max_year = int(df_nl["year"].max())


# ============================================================
# Sidebar filters
# ============================================================
with st.sidebar:
    st.header("Filters")

    st.markdown("### Construction year range")
    col_a, col_b = st.columns(2)

    default_start = 1965 if min_year <= 1965 <= max_year else min_year
    default_end = 1990 if min_year <= 1990 <= max_year else max_year

    start_year = col_a.number_input(
        "Start year",
        min_value=min_year,
        max_value=max_year,
        value=default_start,
        step=1,
    )

    end_year = col_b.number_input(
        "End year",
        min_value=min_year,
        max_value=max_year,
        value=default_end,
        step=1,
    )

    if start_year > end_year:
        st.error("Start year must be before end year.")
        st.stop()

    province_options = ["All Netherlands"]
    if not df_prov.empty and "province_name" in df_prov.columns:
        province_options += sorted(df_prov["province_name"].dropna().unique().tolist())
    elif not df_post65.empty and "province" in df_post65.columns:
        province_options += sorted(df_post65["province"].dropna().unique().tolist())

    selected_province = st.selectbox("Province", province_options)


# ============================================================
# Global filtered datasets
# ============================================================
selected_nl = df_nl[(df_nl["year"] >= start_year) & (df_nl["year"] <= end_year)].copy()
total_buildings_nl = df_nl["building_count"].sum()
selected_buildings_nl = selected_nl["building_count"].sum()
selected_pct_nl = selected_buildings_nl / total_buildings_nl * 100 if total_buildings_nl else 0

filtered_points = df_points.copy()
if not filtered_points.empty and "year" in filtered_points.columns:
    filtered_points = filtered_points[
        (filtered_points["year"] >= start_year) &
        (filtered_points["year"] <= end_year)
    ].copy()
filtered_points = filter_by_province(filtered_points, selected_province)

filtered_matched = filter_by_province(df_matched, selected_province)
filtered_post65 = filter_by_province(df_post65, selected_province)
filtered_post65_matched = filter_by_province(df_post65_matched, selected_province)
filtered_municipal_heritage = filter_by_province(df_municipal_heritage, selected_province)

protected_total = None
if not df_mon.empty and "protected_monuments_total" in df_mon.columns:
    protected_total = df_mon["protected_monuments_total"].iloc[0]

national_matched_count = len(filtered_matched) if not filtered_matched.empty else 0
post65_candidate_count = len(filtered_post65_matched) if not filtered_post65_matched.empty else len(filtered_post65)
municipal_count = len(filtered_municipal_heritage) if not filtered_municipal_heritage.empty else 0


# ============================================================
# Tabs
# ============================================================
tabs = st.tabs([
    "Overview",
    "Year analysis",
    "Province comparison",
    "Municipality view",
    "Heritage status",
    "Protected monuments",
    "Post65 objects",
    "Building locations",
    "Downloads",
    "Method",
])


# ============================================================
# Tab 0: Overview
# ============================================================
with tabs[0]:
    st.subheader("National evidence summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total BAG buildings", fmt_int(total_buildings_nl))
    c2.metric(f"Buildings built {start_year}–{end_year}", fmt_int(selected_buildings_nl))
    c3.metric("Share of total BAG stock", f"{selected_pct_nl:.2f}%")
    c4.metric("Protected monuments in dataset", fmt_int(protected_total))

    st.markdown("### Copy-ready evidence sentence")
    sentence = (
        f"According to the BAG building-stock export, {fmt_int(selected_buildings_nl)} buildings "
        f"in the Netherlands were built between {start_year} and {end_year}, representing "
        f"{selected_pct_nl:.2f}% of the current registered building stock. "
        f"Heritage protection is represented separately through national rijksmonumenten, "
        f"Post65 nominated objects, and optional municipal heritage records."
    )
    st.text_area("Evidence text", sentence, height=130)

    summary = pd.DataFrame([{
        "start_year": start_year,
        "end_year": end_year,
        "total_bag_buildings": int(total_buildings_nl),
        "selected_period_buildings": int(selected_buildings_nl),
        "selected_period_percentage": selected_pct_nl,
        "protected_monuments_total": protected_total,
        "national_matched_records": national_matched_count,
        "post65_records": post65_candidate_count,
        "municipal_heritage_records": municipal_count,
    }])
    csv_button(summary, f"post65_summary_{start_year}_{end_year}.csv", "Download current summary CSV")


# ============================================================
# Tab 1: Year analysis
# ============================================================
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


# ============================================================
# Tab 2: Province comparison
# ============================================================
with tabs[2]:
    st.subheader("Province comparison")

    if df_prov.empty:
        st.warning("Missing data_public/bag_buildings_by_year_province.csv")
    else:
        prov_summary = make_period_summary(df_prov, ["province_name"], start_year, end_year)
        if selected_province != "All Netherlands":
            prov_summary = filter_by_province(prov_summary, selected_province)

        if prov_summary.empty:
            st.info("No province records found for current filter.")
        else:
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


# ============================================================
# Tab 3: Municipality view
# ============================================================
with tabs[3]:
    st.subheader("Municipality view")

    if df_muni.empty:
        st.warning("Missing data_public/bag_buildings_by_year_municipality.csv")
    else:
        muni_df = filter_by_province(df_muni.copy(), selected_province)

        group_cols = []
        if "province_name" in muni_df.columns:
            group_cols.append("province_name")
        if "municipality_name" in muni_df.columns:
            group_cols.append("municipality_name")
        elif "gemeentecode" in muni_df.columns:
            group_cols.append("gemeentecode")

        if not group_cols:
            st.warning("Municipality CSV needs municipality_name or gemeentecode.")
        else:
            muni_summary = make_period_summary(muni_df, group_cols, start_year, end_year)
            if muni_summary.empty:
                st.info("No municipality records found for current filter.")
            else:
                muni_summary = muni_summary.sort_values("selected_period_buildings", ascending=False)

                fig = px.bar(
                    muni_summary.head(30),
                    x=group_cols[-1],
                    y="selected_period_buildings",
                    color="selected_period_percentage",
                    title=f"Top municipalities: buildings built {start_year}–{end_year}",
                    labels={
                        group_cols[-1]: "Municipality",
                        "selected_period_buildings": "Buildings in selected period",
                        "selected_period_percentage": "Share (%)",
                    },
                )
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(muni_summary, use_container_width=True)
                csv_button(muni_summary, f"municipality_summary_{start_year}_{end_year}.csv", "Download municipality summary")


# ============================================================
# Tab 4: Heritage status
# ============================================================
with tabs[4]:
    st.subheader("Heritage status: national vs municipal")

    st.markdown("""
This tab implements Ana's requirement: **separate national heritage from municipal heritage**.

- **BAG** gives building stock, construction year, coordinates, and `pandstatus`.
- **Rijksmonumenten** are national protected monuments.
- **Post65 nominated objects** are a national RCE Post65 selection/candidate layer.
- **Gemeentelijke monumenten** are municipal heritage records and require a separate Kadaster/BRK or municipal source.

Important: BAG `pandstatus` is **not** a heritage-protection status.
""")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("National rijksmonument matches", fmt_int(national_matched_count))
    c2.metric("Post65 national objects", fmt_int(post65_candidate_count))
    c3.metric("Municipal heritage records", fmt_int(municipal_count))
    c4.metric("BAG records in selected period", fmt_int(len(filtered_points)))

    status_rows = [
        {
            "layer": "BAG building stock",
            "available": "Yes",
            "file/table": "bag_buildings_public_points / BAG exports",
            "role_in_app": "Denominator and spatial building stock by year",
            "heritage_level": "Not heritage status",
        },
        {
            "layer": "Rijksmonumenten",
            "available": "Yes, if CSV exported",
            "file/table": "rijksmonumenten_matched.csv / post65_public.rijksmonumenten_matched",
            "role_in_app": "National protected heritage",
            "heritage_level": "National",
        },
        {
            "layer": "Post65 nominated objects",
            "available": "Yes, if CSV exported",
            "file/table": "post65_objects.csv or post65_nominated_buildings.csv",
            "role_in_app": "Named RCE Post65 candidate/example layer",
            "heritage_level": "National candidate / nominated",
        },
        {
            "layer": "Gemeentelijke monumenten",
            "available": "Optional / not yet unless loaded",
            "file/table": "municipal_heritage_matched.csv / post65_public.municipal_heritage_matched",
            "role_in_app": "Local/municipal protected heritage",
            "heritage_level": "Municipal",
        },
    ]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True)

    st.markdown("### Heritage layer availability")
    availability = pd.DataFrame([
        {"dataset": "BAG stock", "records": len(df_points), "loaded": not df_points.empty},
        {"dataset": "Rijksmonumenten matched", "records": len(df_matched), "loaded": not df_matched.empty},
        {"dataset": "Post65 objects", "records": len(df_post65), "loaded": not df_post65.empty},
        {"dataset": "Post65 matched to BAG", "records": len(df_post65_matched), "loaded": not df_post65_matched.empty},
        {"dataset": "Municipal heritage", "records": len(df_municipal_heritage), "loaded": not df_municipal_heritage.empty},
    ])
    st.dataframe(availability, use_container_width=True)

    st.markdown("### Municipal heritage")
    if filtered_municipal_heritage.empty:
        st.info("""
Municipal heritage (`gemeentelijke monumenten`) is not loaded yet.

This layer must come from:
- Kadaster/BRK public-law restrictions, or
- municipal monument datasets.

It cannot be derived from BAG `pandstatus`.
""")
    else:
        st.dataframe(filtered_municipal_heritage, use_container_width=True)
        csv_button(filtered_municipal_heritage, "municipal_heritage_matched_filtered.csv", "Download municipal heritage matches")


# ============================================================
# Tab 5: Protected monuments
# ============================================================
with tabs[5]:
    st.subheader("Protected monuments dataset")

    if df_mon.empty:
        st.warning("Missing data_public/rijksmonumenten_summary.csv")
    else:
        st.dataframe(df_mon, use_container_width=True)

    st.markdown("### Matched national monument records")
    show_optional_dataframe(filtered_matched, "matched national monuments", "rijksmonumenten_matched_filtered.csv")

    if not filtered_matched.empty and "function_type" in filtered_matched.columns:
        function_summary = (
            filtered_matched.dropna(subset=["function_type"])
            .groupby("function_type", as_index=False)
            .size()
            .rename(columns={"size": "record_count"})
            .sort_values("record_count", ascending=False)
        )
        if not function_summary.empty:
            fig = px.bar(
                function_summary.head(30),
                x="function_type",
                y="record_count",
                title="National monument records by function type",
                labels={"function_type": "Function type", "record_count": "Records"},
            )
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Tab 6: Post65 objects
# ============================================================
with tabs[6]:
    st.subheader("Post65 heritage objects — national overview")

    if filtered_post65.empty and filtered_post65_matched.empty:
        st.warning(
            "Missing data_public/post65_objects.csv or data_public/post65_nominated_buildings.csv. "
            "Export the database view/table to CSV and place it in data_public."
        )
    else:
        # Show matched version if available; otherwise raw/semantic Post65 list.
        display_post65 = filtered_post65_matched if not filtered_post65_matched.empty else filtered_post65

        st.markdown("""
This tab shows the national Post65 object layer. These are curated Post65 examples or nominated objects from 1965–1990.
They are shown separately from BAG building-stock counts and from officially protected rijksmonumenten.
""")

        c1, c2, c3 = st.columns(3)
        c1.metric("Post65 objects", fmt_int(len(display_post65)))
        province_col = "province" if "province" in display_post65.columns else "province_name" if "province_name" in display_post65.columns else None
        typology_col = "typology" if "typology" in display_post65.columns else None
        c2.metric("Provinces represented", fmt_int(safe_nunique(display_post65, province_col) if province_col else 0))
        c3.metric("Typologies", fmt_int(safe_nunique(display_post65, typology_col) if typology_col else 0))

        if province_col:
            province_summary = (
                display_post65.dropna(subset=[province_col])
                .groupby(province_col, as_index=False)
                .size()
                .rename(columns={"size": "object_count", province_col: "province"})
                .sort_values("object_count", ascending=False)
            )
            if not province_summary.empty:
                fig = px.bar(
                    province_summary,
                    x="province",
                    y="object_count",
                    title="Post65 objects by province",
                    labels={"province": "Province", "object_count": "Number of Post65 objects"},
                )
                st.plotly_chart(fig, use_container_width=True)

        if typology_col:
            typology_summary = (
                display_post65.dropna(subset=[typology_col])
                .groupby(typology_col, as_index=False)
                .size()
                .rename(columns={"size": "object_count", typology_col: "typology"})
                .sort_values("object_count", ascending=False)
            )
            if not typology_summary.empty:
                fig = px.bar(
                    typology_summary,
                    x="typology",
                    y="object_count",
                    title="Post65 objects by typology",
                    labels={"typology": "Typology", "object_count": "Number of Post65 objects"},
                )
                st.plotly_chart(fig, use_container_width=True)

        # Map only if coordinates are present.
        if {"lat", "lon"}.issubset(display_post65.columns):
            map_df = display_post65.dropna(subset=["lat", "lon"]).copy()
            if not map_df.empty:
                fig = px.scatter_mapbox(
                    map_df,
                    lat="lat",
                    lon="lon",
                    hover_name="name" if "name" in map_df.columns else None,
                    color="heritage_scope" if "heritage_scope" in map_df.columns else None,
                    hover_data=[c for c in [
                        "year", "municipality", "province", "status", "typology",
                        "postcode", "pand_id", "pandstatus", "matched_to_bag"
                    ] if c in map_df.columns],
                    zoom=6,
                    height=550,
                    title="Post65 objects map",
                )
                fig.update_layout(mapbox_style="open-street-map")
                fig.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Post65 object table has coordinate columns, but no valid lat/lon values for the current filter.")
        else:
            st.info("No lat/lon columns available for Post65 objects yet. The table can still be used for national overview and typology analysis.")

        st.dataframe(display_post65, use_container_width=True)
        csv_button(display_post65, "post65_objects_filtered.csv", "Download filtered Post65 objects")


# ============================================================
# Tab 7: Building locations
# ============================================================
with tabs[7]:
    st.subheader("Building locations")

    if df_points.empty:
        st.warning("Missing data_public/bag_buildings_public_points.csv")
    else:
        st.write(f"Showing BAG building points constructed between {start_year} and {end_year}.")
        st.metric("Buildings in current filter", fmt_int(len(filtered_points)))

        csv_button(
            filtered_points,
            f"buildings_{start_year}_{end_year}_{selected_province}.csv".replace(" ", "_"),
            "Download selected building list as CSV",
        )

        if {"lat", "lon"}.issubset(filtered_points.columns):
            max_available = max(1000, min(50000, len(filtered_points)))
            default_points = min(10000, max_available)

            max_points = st.slider(
                "Maximum points to display on map",
                min_value=1000,
                max_value=max_available,
                value=default_points,
                step=1000,
            )

            map_df = filtered_points.head(max_points).dropna(subset=["lat", "lon"])
            if not map_df.empty:
                st.map(map_df, latitude="lat", longitude="lon")
            else:
                st.info("No valid coordinates found for the selected BAG records.")
        else:
            st.info("The BAG points file does not contain lat/lon columns.")

        display_cols = [c for c in [
            "pand_id", "year", "province_name", "municipality_name", "gemeentecode", "pandstatus", "lat", "lon"
        ] if c in filtered_points.columns]
        if display_cols:
            st.dataframe(filtered_points[display_cols], use_container_width=True)
        else:
            st.dataframe(filtered_points, use_container_width=True)


# ============================================================
# Tab 8: Downloads
# ============================================================
with tabs[8]:
    st.subheader("Download dashboard datasets")

    csv_button(df_nl, "bag_buildings_by_year_nl.csv", "Download national BAG by year")

    if not df_prov.empty:
        csv_button(df_prov, "bag_buildings_by_year_province.csv", "Download BAG by province/year")

    if not df_muni.empty:
        csv_button(df_muni, "bag_buildings_by_year_municipality.csv", "Download BAG by municipality/year")

    if not df_points.empty:
        csv_button(df_points, "bag_buildings_public_points.csv", "Download BAG public points")

    if not df_mon.empty:
        csv_button(df_mon, "rijksmonumenten_summary.csv", "Download monument summary")

    if not df_matched.empty:
        csv_button(df_matched, "rijksmonumenten_matched.csv", "Download matched national monuments")

    if not df_post65.empty:
        csv_button(df_post65, "post65_objects.csv", "Download Post65 objects")

    if not df_post65_matched.empty:
        csv_button(df_post65_matched, "post65_nominated_matched.csv", "Download matched Post65 nominated objects")

    if not df_municipal_heritage.empty:
        csv_button(df_municipal_heritage, "municipal_heritage_matched.csv", "Download municipal heritage records")


# ============================================================
# Tab 9: Method
# ============================================================
with tabs[9]:
    st.subheader("Method")

    st.markdown("""
**Core distinction**

- **BAG** is used for the denominator: total building stock, construction year, location, and `pandstatus`.
- **Rijksmonumenten** are used for the national protected heritage layer.
- **Post65 nominated objects** are loaded as a named national RCE Post65 selection/candidate layer.
- **Municipal heritage** requires a separate municipal/Kadaster/BRK source and should not be inferred from BAG.

**Main calculation**

```text
Selected-period share = BAG buildings built in selected year range / total BAG buildings
```

**Recommended matching logic**

```text
Post65 nominated object
→ normalize postcode/address
→ match with national BAG address data where available
→ preserve match status
```

**Important limitation**

BAG `pandstatus` is not a monument or heritage-protection status. It only describes the BAG lifecycle/status of a building object.

**Application-data separation**

The app reads exported CSVs from `data_public/`. Database matching and enrichment should happen in PostgreSQL first, then be exported as clean CSVs for Streamlit.
""")
