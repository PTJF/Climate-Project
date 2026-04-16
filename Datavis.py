# Import Packages
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, ctx

# =========================================================
# 1. SETTINGS & CONSTANTS
# =========================================================
START_YEAR = 1860
END_YEAR = 2020 

# =========================================================
# 2. LOAD & UNIFY DATA
# =========================================================
map_df = pd.read_csv("co2-emissions-by-fuel-line.csv")
fuel_cols = ["Coal", "Oil", "Gas", "Cement", "Flaring", "Other industry"]
map_df["Year"] = pd.to_numeric(map_df["Year"], errors="coerce")

for col in fuel_cols:
    map_df[col] = pd.to_numeric(map_df[col], errors="coerce")

map_df = map_df[(map_df["Year"] >= START_YEAR) & (map_df["Year"] <= END_YEAR)].copy()
map_df = map_df.dropna(subset=["Code"]).copy()
map_df = map_df[~map_df["Code"].isin(["OWID_WRL"])].copy()
map_df["Total"] = map_df[fuel_cols].sum(axis=1, min_count=1)

# Skeleton Logic
all_countries = map_df[['Entity', 'Code']].drop_duplicates()
all_years = pd.DataFrame({'Year': range(int(START_YEAR), int(END_YEAR) + 1)})
skeleton = all_countries.assign(key=1).merge(all_years.assign(key=1), on='key').drop('key', axis=1)
map_df = pd.merge(skeleton, map_df, on=['Entity', 'Code', 'Year'], how='left')
map_df["Year"] = map_df["Year"].astype(int)

fuel_df = map_df.copy()

# Temperature
temp_df = pd.read_csv("temperature-anomaly.csv")
for col in ["Year", "Average", "Lower bound", "Upper bound"]:
    temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
temp_world = temp_df[temp_df["Entity"] == "World"].copy().sort_values("Year")

# Sea Ice
arctic_ice_df = pd.read_csv("climate-change-arctic-sea-ice-extent.csv")
antarctic_ice_df = pd.read_csv("climate-change-antarctic-sea-ice-extent.csv")
for df in [arctic_ice_df, antarctic_ice_df]:
    for col in ["Year", "February", "September"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_values("Year", inplace=True)

# Sea Level
sea_df = pd.read_csv("sea-level.csv")
sea_df["Day"] = pd.to_datetime(sea_df["Day"], errors="coerce")
sea_df["Year"] = sea_df["Day"].dt.year
sea_col = "Average of Church and White (2011) and UHSLC"
sea_df[sea_col] = pd.to_numeric(sea_df[sea_col], errors="coerce")

# =========================================================
# 3. FORMATTING & CATEGORIES
# =========================================================
def format_total_co2(x):
    if pd.isna(x) or x <= 0: return "No data"
    elif x >= 1_000_000_000: return f"{x / 1_000_000_000:.2f} billion tonnes"
    elif x >= 1_000_000: return f"{x / 1_000_000:.2f} million tonnes"
    else: return f"{x:,.0f} tonnes"

bins = [1, 10_000_000, 50_000_000, 100_000_000, 500_000_000, 1_000_000_000, 5_000_000_000, float("inf")]
emission_labels = ["< 10M tonnes", "10M – 50M tonnes", "50M – 100M tonnes", "100M – 500M tonnes", "500M – 1B tonnes", "1B – 5B tonnes", "> 5B tonnes"]
labels = ["No Data Recorded"] + emission_labels
color_map = {"No Data Recorded": "#bdbdbd", "< 10M tonnes": "#fff5f0", "10M – 50M tonnes": "#fee0d2", "50M – 100M tonnes": "#fcbba1", "100M – 500M tonnes": "#fc9272", "500M – 1B tonnes": "#fb6a4a", "1B – 5B tonnes": "#de2d26", "> 5B tonnes": "#a50f15"}

temp_total_calc = pd.to_numeric(map_df["Total"], errors="coerce").fillna(-1)
map_df["CO2_category"] = pd.cut(temp_total_calc, bins=bins, labels=emission_labels)
map_df["CO2_category"] = map_df["CO2_category"].cat.add_categories("No Data Recorded").fillna("No Data Recorded")
map_df["CO2_category"] = pd.Categorical(map_df["CO2_category"], categories=labels, ordered=True)
map_df["CO2_label"] = map_df["Total"].apply(format_total_co2)

# Indicators Styling
ice_color_map = {"No data": "#bdbdbd", "< 3": "#08544B", "3-10": "#10A291", "> 10": "#20E9D2"}
ice_order = ["No data", "< 3", "3-10", "> 10"]
sea_level_color_map = {"No data": "#bdbdbd", "< -100": "#deebf7", "-100 to -50": "#9ecae1", "-50 to 0": "#6baed6", "0 to 50": "#3182bd", "50+": "#08519c"}
sea_level_order = ["No data", "< -100", "-100 to -50", "-50 to 0", "0 to 50", "50+"]

# =========================================================
# 4. MAP HELPERS (GHOSTS, MARKERS, THERMOMETER)
# =========================================================
def get_sea_ice_points(selected_year):
    rows = []
    regions = [{"Region": "Arctic", "lat": 77, "lon": 0, "df": arctic_ice_df}, {"Region": "Antarctic", "lat": -65, "lon": 0, "df": antarctic_ice_df}]
    for r in regions:
        row = r["df"][r["df"]["Year"] == selected_year]
        base_row = r["df"][r["df"]["Year"] == 1979]
        month = "February" if r["Region"] == "Arctic" else "September"
        if selected_year < 1979 or row.empty or pd.isna(row[month].iloc[0]):
            rows.append({"Region": r["Region"], "lat": r["lat"], "lon": r["lon"], "value": None, "value_label": "No data", "size": 12, "base_size": 12, "ice_cat": "No data", "series_type": "sea_ice", "inside_text": "", "pct_text": "No data"})
        else:
            v = row[month].iloc[0]
            base_v = base_row[month].iloc[0] if not base_row.empty else v
            pct = (v - base_v) / base_v * 100
            rows.append({"Region": r["Region"], "lat": r["lat"], "lon": r["lon"], "value": v, "value_label": f"{v:.2f} million km²", "size": max(10, v * 3.0), "base_size": max(10, base_v * 3.0), "ice_cat": "< 3" if v < 3 else "3-10" if v < 10 else "> 10", "series_type": "sea_ice", "inside_text": "Arctic<br>Ice" if r["Region"] == "Arctic" else "Antarctic<br>Ice", "pct_text": f"{'↓' if pct < 0 else '↑'} {abs(pct):.0f}%"})
    return pd.DataFrame(rows)

def get_sea_level_point(selected_year):
    yr_rows = sea_df[sea_df["Year"] == selected_year]
    if yr_rows.empty: return pd.DataFrame([{"Name": "Global sea level", "lat": -20, "lon": -122, "value": None, "value_label": "No data", "sea_cat": "No data", "series_type": "sea_level", "inside_text": "", "pct_text": "No data", "size": 75}])
    v = yr_rows[sea_col].mean()
    base_v = sea_df[sea_df["Year"] == 1880][sea_col].mean()
    cat = "< -100" if v < -100 else "-100 to -50" if v < -50 else "-50 to 0" if v < 0 else "0 to 50" if v < 50 else "50+"
    return pd.DataFrame([{"Name": "Global sea level", "lat": -20, "lon": -122, "value": v, "value_label": f"{v:.1f} mm", "sea_cat": cat, "series_type": "sea_level", "inside_text": "Sea Level", "pct_text": f"{v - base_v:+.1f} mm vs 1880", "size": 75}])

def make_map(selected_year):
    year_df = map_df[map_df["Year"] == selected_year].copy()
    
    # 1. Create the base map
    fig = px.choropleth(
        year_df, 
        locations="Code", 
        color="CO2_category", 
        hover_name="Entity", 
        custom_data=["CO2_label", "Year", "Code"], 
        category_orders={"CO2_category": labels}, 
        color_discrete_map=color_map, 
        title=f"Global CO₂ Emissions & Climate Indicators in {selected_year}"
    )
    
    # 2. HIDE THE AUTOMATIC TRACE ITEMS
    fig.update_traces(showlegend=False, selector=dict(type='choropleth'))

    # 3. FIX: EXPLICITLY REMOVE THE LEGEND TITLE
    # This kills the "CO2_category" text at the top of the legend box
    fig.update_layout(legend_title_text="")

    fig.update_traces(
        hovertemplate="<b>%{hovertext}</b><br>Total CO2: %{customdata[0]}<br>Year: %{customdata[1]}<extra></extra>",
        selector=dict(type='choropleth')
    )

    # --- Manual Legends (Your custom groups) ---
    for i, cat in enumerate(labels):
        fig.add_trace(go.Scattergeo(
            lon=[None], lat=[None], mode="markers", 
            marker=dict(size=10, color=color_map.get(cat)), 
            name=cat, 
            legendgroup="CO2", 
            legendgrouptitle_text="<b>TOTAL CO2 EMISSIONS</b>" if i == 0 else "", 
            showlegend=True, 
            hoverinfo="skip"
        ))
    
    ice_disp = {"No data": "No Data Recorded", "< 3": "< 3M km²", "3-10": "3M–10M km²", "> 10": "> 10M km²"}
    for i, cat in enumerate(ice_order):
        fig.add_trace(go.Scattergeo(
            lon=[None], lat=[None], mode="markers", 
            marker=dict(size=10, color=ice_color_map[cat]), 
            name=ice_disp[cat], 
            legendgroup="ICE", 
            legendgrouptitle_text="<b>SEA ICE EXTENT</b>" if i == 0 else None, 
            showlegend=True, 
            hoverinfo="skip"
        ))

    sea_disp = {"No data": "No Data Recorded", "< -100": "< -100 mm", "-100 to -50": "-100 to -50 mm", "-50 to 0": "-50 to 0 mm", "0 to 50": "0 to 50 mm", "50+": "> 50 mm"}
    for i, cat in enumerate(sea_level_order):
        fig.add_trace(go.Scattergeo(
            lon=[None], lat=[None], mode="markers", 
            marker=dict(size=10, color=sea_level_color_map[cat]), 
            name=sea_disp[cat], 
            legendgroup="LEVEL", 
            legendgrouptitle_text="<b>SEA LEVEL CHANGE</b>" if i == 0 else None, 
            showlegend=True, 
            hoverinfo="skip"
        ))

    # --- Markers & Indicators ---
    ice_pts = get_sea_ice_points(selected_year)
    fig.add_trace(go.Scattergeo(
        lon=ice_pts["lon"], lat=ice_pts["lat"], mode="markers", 
        marker=dict(size=ice_pts["base_size"], color="rgba(128,128,128,0.3)", line=dict(color="black", width=1.5, dash="dot")), 
        showlegend=False, hoverinfo="skip"
    ))

    for cat in ice_order:
        sub = ice_pts[ice_pts["ice_cat"] == cat]
        if not sub.empty:
            fig.add_trace(go.Scattergeo(
                lon=sub["lon"], lat=sub["lat"], mode="markers+text", 
                text=sub["inside_text"], textposition="middle center", 
                customdata=sub[["Region", "value_label", "pct_text", "series_type"]].values, 
                marker=dict(size=sub["size"], color=ice_color_map[cat], line=dict(color="navy", width=1)), 
                textfont=dict(color="black", size=10), showlegend=False, 
                hovertemplate="<b>%{customdata[0]}</b><br>Peak extent: %{customdata[1]}<br>Change vs 1979: %{customdata[2]}<br>Click to view detail<extra></extra>"
            ))

    sea_pt = get_sea_level_point(selected_year)
    fig.add_trace(go.Scattergeo(
        lon=sea_pt["lon"], lat=sea_pt["lat"], mode="markers+text", 
        text=sea_pt["inside_text"], textposition="middle center", 
        customdata=sea_pt[["Name", "value_label", "pct_text", "series_type"]].values, 
        marker=dict(size=sea_pt["size"], symbol="square", color=[sea_level_color_map[c] for c in sea_pt["sea_cat"]], line=dict(color="navy", width=2)), 
        textfont=dict(color="black", size=12), showlegend=False, 
        hovertemplate="<b>%{customdata[0]}</b><br>Level: %{customdata[1]}<br>%{customdata[2]}<br>Click to view detail<extra></extra>"
    ))

    # --- Thermometer ---
    tr = temp_world[temp_world["Year"] == selected_year]
    tv = tr["Average"].iloc[0] if not tr.empty else None
    x0, x1, y0, y1 = 0.04, 0.053, 0.28, 0.63
    fig.add_shape(type="rect", xref="paper", yref="paper", x0=x0, x1=x1, y0=y0, y1=y1, line=dict(color="#333333", width=1.8), fillcolor="white")
    fig.add_shape(type="circle", xref="paper", yref="paper", x0=0.031, x1=0.062, y0=y0-0.04, y1=y0, line=dict(color="black", width=2), fillcolor="white")
    
    if tv is not None:
        ratio = max(0, min(1, (tv - (-0.5)) / (1.5 - (-0.5))))
        fc = "#9ecae1" if tv < -0.2 else "#c7e9c0" if tv < 0.2 else "#fdd49e" if tv < 0.6 else "#fdbb84" if tv < 1.0 else "#fc8d59" if tv < 1.4 else "#d7301f"
        fig.add_shape(type="rect", xref="paper", yref="paper", x0=x0+0.004, x1=x1-0.004, y0=y0, y1=y0+ratio*(y1-y0), line=dict(width=0), fillcolor=fc)
        fig.add_shape(type="circle", xref="paper", yref="paper", x0=0.031+0.004, x1=0.062-0.004, y0=y0-0.04+0.004, y1=y0-0.004, line=dict(width=0), fillcolor=fc)
        fig.add_annotation(x=x1-0.045, y=y1+0.045, xref="paper", yref="paper", text=f"<b>Temperature</b><br>{tv:+.2f}°C", showarrow=False, bgcolor="rgba(255,255,255,0.92)", bordercolor="#444444", borderwidth=1, font=dict(size=8))
    
    fig.add_trace(go.Scattergeo(
        lon=[-163], lat=[-56], mode="markers", 
        marker=dict(size=14, color="rgba(0,0,0,0)"), 
        customdata=[["Temperature", "special"]], 
        showlegend=False, 
        hovertemplate=f"<b>Temperature</b><br>Year: {selected_year}<br>Anomaly: {tv:+.2f}°C<br>Click bulb to view detail<extra></extra>"
    ))

    fig.update_geos(
        showcountries=True, countrycolor="black", showocean=True, oceancolor="#d6f2ff", 
        lataxis_range=[-90, 90], lonaxis_range=[-180, 180], projection_type="equirectangular"
    )
    
    # Final layout: Adjusting legend box positioning
    fig.update_layout(
        margin=dict(l=10, r=10, t=180, b=10), height=750, 
        legend=dict(
            yanchor="top", y=0.87, xanchor="left", x=1.01, 
            bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="#444444", 
            borderwidth=1, traceorder="grouped", itemsizing="constant", font=dict(size=10)
        )
    )
    
    return fig

# =========================================================
# 5. DETAIL HELPERS (TABLES & PLOTS)
# =========================================================
def make_empty_detail(selected_year):
    fig = go.Figure()
    fig.add_annotation(text=f"Interaction with Country, Arctic/Antartic,<br> Sea Level and Temperature", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=16))
    fig.update_layout(title="Detail chart", height=420, xaxis_visible=False, yaxis_visible=False)
    return fig

def make_global_table(selected_year):
    df = fuel_df[fuel_df["Year"] == selected_year].sort_values("Total", ascending=False)
    fig = go.Figure(data=[go.Table(header=dict(values=["<b>Country</b>", "<b>Coal</b>", "<b>Oil</b>", "<b>Gas</b>", "<b>Total (Tonnes)</b>"], fill_color='#2c3e50', align='left', font=dict(size=12, color='white')),
        cells=dict(values=[df.Entity, [f"{x:,.0f}" for x in df.Coal], [f"{x:,.0f}" for x in df.Oil], [f"{x:,.0f}" for x in df.Gas], [f"{x:,.0f}" for x in df.Total]], fill_color='#f8f9fa', align='left', font=dict(size=11), height=25))])
    fig.update_layout(title=f"Global CO2 Emissions Ranking ({selected_year})", height=400, margin=dict(l=10, r=10, t=50, b=10))
    return fig

def make_country_history_table(country_code, selected_year):
    df = fuel_df[(fuel_df["Code"] == country_code) & (fuel_df["Year"] <= selected_year)].sort_values("Year", ascending=False)
    fig = go.Figure(data=[go.Table(header=dict(values=["<b>Year</b>", "<b>Total CO2 Emissions (tonnes)</b>"], fill_color='#2c3e50', align='left', font=dict(size=12, color='white')),
        cells=dict(values=[df.Year, [f"{x:,.0f}" for x in df.Total]], fill_color='#f8f9fa', align='left'))])
    fig.update_layout(title=f"Historical Total Emissions: {df['Entity'].iloc[0] if not df.empty else ''}", height=400)
    return fig

def make_temperature_table(selected_year):
    df = temp_world[temp_world["Year"] <= selected_year].sort_values("Year", ascending=False)
    fig = go.Figure(data=[go.Table(header=dict(values=["<b>Year</b>", "<b>Avg Anomaly (°C)</b>", "<b>Lower Bound</b>", "<b>Upper Bound</b>"], fill_color='#2c3e50', align='left', font=dict(size=12, color='white')),
        cells=dict(values=[df.Year, [f"{x:+.3f}°C" for x in df.Average], [f"{x:+.3f}°C" for x in df["Lower bound"]], [f"{x:+.3f}°C" for x in df["Upper bound"]]], fill_color='#f8f9fa', align='left'))])
    fig.update_layout(title=f"Global Temperature Anomaly Data (up to {selected_year})", height=420)
    return fig

def make_sea_ice_bar(region, selected_year):
    df = arctic_ice_df if region == "Arctic" else antarctic_ice_df
    row = df[df["Year"] == selected_year]
    
    if selected_year < 1979:
        fig = go.Figure()
        fig.add_annotation(text="Sea ice data begins in 1979", showarrow=False, font=dict(size=16))
        fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=440)
        return fig
    
    if row.empty:
        return make_empty_detail(selected_year)
    
    if region == "Arctic":
        vals, labs = [row["September"].iloc[0], row["February"].iloc[0]], ["Minimum (September)", "Maximum (February)"]
    else:
        vals, labs = [row["February"].iloc[0], row["September"].iloc[0]], ["Minimum (February)", "Maximum (September)"]
    
    fig = go.Figure([
        go.Bar(
            x=[vals[0]], 
            y=[labs[0]], 
            orientation="h", 
            marker_color="indianred", 
            text=[f"{vals[0]:.2f} million km²"],  # Changed to million km²
            textposition="outside", 
            cliponaxis=False,                     # Let text go outside border
            name="Min"
        ),
        go.Bar(
            x=[vals[1]], 
            y=[labs[1]], 
            orientation="h", 
            marker_color="steelblue", 
            text=[f"{vals[1]:.2f} million km²"], 
            textposition="outside", 
            cliponaxis=False,               
            name="Max"
        )
    ])
    
    fig.update_layout(
        title=f"{region} sea ice extent in {selected_year}", 
        xaxis_title="Sea ice extent (million km²)", 
        height=440, 
        showlegend=False, 
        xaxis_range=[0, max(vals) * 1.35],     
        margin=dict(r=120)                   
    )
    return fig

def make_sea_ice_table(region, selected_year):
    df = arctic_ice_df if region == "Arctic" else antarctic_ice_df
    if selected_year < 1979:
        fig = go.Figure(); fig.add_annotation(text="Sea ice data begins in 1979", showarrow=False, font=dict(size=16))
        fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=420); return fig
    df_f = df[df["Year"] <= selected_year].sort_values("Year", ascending=False)
    mx, mn = ("February", "September") if region == "Arctic" else ("September", "February")
    fig = go.Figure(data=[go.Table(header=dict(values=["<b>Year</b>", f"<b>Max Extent ({mx})</b>", f"<b>Min Extent ({mn})</b>"], fill_color='#2c3e50', font=dict(color='white')),
        cells=dict(values=[df_f.Year, [f"{x:.2f} M km²" for x in df_f[mx]], [f"{x:.2f} M km²" for x in df_f[mn]]], fill_color='#f8f9fa'))])
    fig.update_layout(title=f"{region} Sea Ice Data Table (up to {selected_year})", height=420)
    return fig

def make_sea_level_table(selected_year):
    df = sea_df[sea_df["Year"] <= selected_year]
    if df.empty:
        fig = go.Figure(); fig.add_annotation(text="Sea level data begins in 1880", showarrow=False, font=dict(size=16))
        fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=420); return fig
    df_y = df.groupby("Year")[sea_col].mean().reset_index().sort_values("Year", ascending=False)
    fig = go.Figure(data=[go.Table(header=dict(values=["<b>Year</b>", "<b>Sea Level (mm)</b>"], fill_color='#2c3e50', font=dict(color='white')),
        cells=dict(values=[df_y.Year, [f"{x:+.1f} mm" for x in df_y[sea_col]]], fill_color='#f8f9fa'))])
    fig.update_layout(title=f"Global Sea Level Historical Data (up to {selected_year})", height=420)
    return fig

def make_sea_level_line(selected_year):
    df = sea_df[sea_df["Year"] <= selected_year]
    if df.empty:
        fig = go.Figure(); fig.add_annotation(text="Sea level data begins in 1880", showarrow=False, font=dict(size=16))
        fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=420); return fig
    df_y = df.groupby("Year")[sea_col].mean().reset_index()
    fig = px.line(df_y, x="Year", y=sea_col, title="Global sea level over time")
    fig.add_vline(x=selected_year, line_dash="dash", line_color="black")
    fig.update_layout(yaxis_title="Sea level (mm)", height=420)
    return fig

# [Rest of make_source_area, make_pie, make_total_line, make_temperature_line helpers included similarly...]
def make_source_area(country_code, selected_year):
    df = fuel_df[(fuel_df["Code"] == country_code) & (fuel_df["Year"] <= selected_year)].melt(id_vars=["Year", "Entity"], value_vars=fuel_cols, var_name="Source", value_name="Value")
    fig = px.area(df, x="Year", y="Value", color="Source", title=f"CO2 Source Distribution over time: {df['Entity'].iloc[0] if not df.empty else ''}")
    fig.add_vline(x=selected_year, line_dash="dash", line_color="black")
    fig.update_layout(margin=dict(l=20, r=20, t=55, b=20), height=320)
    return fig

def make_pie(country_code, selected_year):
    row = fuel_df[(fuel_df["Code"] == country_code) & (fuel_df["Year"] == selected_year)]
    if row.empty: return px.pie(title="No data").update_layout(height=320)
    df = pd.DataFrame({"Source": fuel_cols, "Value": [row[col].iloc[0] for col in fuel_cols]}).dropna()
    fig = px.pie(df[df["Value"] > 0], names="Source", values="Value", title=f"CO2 source types in {row['Entity'].iloc[0]} ({selected_year})", hole=0.35)
    fig.update_traces(textinfo="percent+label", hovertemplate="<b>%{label}</b><br>%{value:,.0f} tonnes<br>%{percent}<extra></extra>")
    fig.update_layout(margin=dict(l=20, r=20, t=55, b=20), height=320)
    return fig

def make_total_line(country_code, selected_year):
    df = fuel_df[(fuel_df["Code"] == country_code) & (fuel_df["Year"] <= selected_year)]
    fig = px.line(df, x="Year", y="Total", title=f"Total Annual CO2 Emissions: {df['Entity'].iloc[0] if not df.empty else ''}")
    fig.add_vline(x=selected_year, line_dash="dash", line_color="red")
    fig.update_layout(margin=dict(l=20, r=20, t=55, b=20), height=320)
    return fig

def make_temperature_line(selected_year):
    df = temp_world[temp_world["Year"] <= selected_year]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Year"], y=df["Upper bound"], mode="lines", line_width=0, showlegend=False))
    fig.add_trace(go.Scatter(x=df["Year"], y=df["Lower bound"], mode="lines", fill="tonexty", name="Uncertainty band"))
    fig.add_trace(go.Scatter(x=df["Year"], y=df["Average"], mode="lines", name="Temperature anomaly", hovertemplate="Year: %{x}<br>Anomaly: %{y:.3f}°C<extra></extra>"))
    fig.add_vline(x=selected_year, line_dash="dash", line_color="black")
    fig.update_layout(title="Global temperature anomaly over time", xaxis_title="Year", yaxis_title="Temperature anomaly (°C)", height=320)
    return fig

def make_sea_ice_area(region, selected_year):
    df = arctic_ice_df if region == "Arctic" else antarctic_ice_df
    if selected_year < 1979:
        fig = go.Figure(); fig.add_annotation(text="Sea ice data begins in 1979", showarrow=False, font=dict(size=16))
        fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=420); return fig
    df_f = df[df["Year"] <= selected_year]
    fig = go.Figure([go.Scatter(x=df_f["Year"], y=df_f["February"], mode="lines", line_width=0, showlegend=False),
        go.Scatter(x=df_f["Year"], y=df_f["September"], mode="lines", fill="tonexty", name="Seasonal range (Feb–Sep)"),
        go.Scatter(x=df_f["Year"], y=df_f["February"], mode="lines", name="February extent"),
        go.Scatter(x=df_f["Year"], y=df_f["September"], mode="lines", name="September extent")])
    fig.add_vline(x=selected_year, line_dash="dash", line_color="black")
    fig.update_layout(title=f"{'Arctic' if region=='Arctic' else 'Antarctic'} sea ice extent over time", yaxis_title="Sea ice extent (million km²)", height=420)
    return fig

# =========================================================
# 6. APP LAYOUT
# =========================================================
app = Dash(__name__)
server = app.server 
app.layout = html.Div([
    html.H2("Climate Change: Drivers & Consequences", style={"textAlign": "center"}),
    html.Div([html.Button("Play", id="play-button", n_clicks=0, style={"marginRight": "10px"}), html.Button("Pause", id="pause-button", n_clicks=0)], style={"textAlign": "center", "marginBottom": "15px"}),
    dcc.Interval(id="play-interval", interval=250, disabled=True),
    html.Div([dcc.Slider(id="year-slider", min=START_YEAR, max=END_YEAR, step=1, value=END_YEAR, marks={y: str(y) for y in range(1860, 2021, 20)}, tooltip={"placement": "bottom", "always_visible": True})], style={"width": "90%", "margin": "20px auto"}),
    html.Div([
        html.Div([dcc.Graph(id="world-map", figure=make_map(END_YEAR), config={'displayModeBar': False})], style={"flex": "2"}),
        html.Div([
            html.Div([
                html.Div([html.Div([html.B(id="chart-mode-label", children="Country CO2 View:")]), dcc.RadioItems(id="chart-mode-main", options=[{"label": " Local Trend Line", "value": "total"}, {"label": " Local Data Table", "value": "local_table"}], value="total", labelStyle={"display": "block", "marginBottom": "5px"})], id="container-main", style={"flex": "1"}),
                html.Div(id="selector-divider", style={"width": "1px", "backgroundColor": "#e0e0e0", "height": "65px", "margin": "0 20px"}),
                html.Div([html.Div([html.B(id="chart-mode-sublabel", children="Source Breakdown:")]), dcc.RadioItems(id="chart-mode", options=[{"label": " Area Chart", "value": "area"}, {"label": " Pie Chart", "value": "pie"}, {"label": " Global Ranking", "value": "table"}], value=None, labelStyle={"display": "block", "marginBottom": "5px"})], id="container-sub", style={"flex": "1"}),
            ], style={"border": "1px solid #e0e0e0", "borderRadius": "8px", "padding": "15px", "backgroundColor": "#fcfcfc", "display": "flex", "alignItems": "center", "marginTop": "70px", "marginBottom": "20px"}),
            dcc.Graph(id="detail-chart", figure=make_empty_detail(END_YEAR)),
            html.Div([dcc.Graph(id="temperature-chart")], style={"display": "none"})
        ], style={"flex": "1", "paddingTop": "50px", "paddingLeft": "20px"})
    ], style={"display": "flex", "flexDirection": "row", "padding": "0 2%"}),
    dcc.Store(id="selected-country"), dcc.Store(id="selected-region"), dcc.Store(id="selected-special")
])

# =========================================================
# 7. CALLBACKS
# =========================================================
@app.callback(Output("play-interval", "disabled"), [Input("play-button", "n_clicks"), Input("pause-button", "n_clicks")], prevent_initial_call=True)
def control_play(p, s): return False if ctx.triggered_id == "play-button" else True

@app.callback(Output("year-slider", "value"), Input("play-interval", "n_intervals"), State("year-slider", "value"), State("play-interval", "disabled"))
def advance_year(n, current, disabled):
    if disabled: return current
    return START_YEAR if current >= END_YEAR else current + 1

@app.callback([Output("selected-country", "data"), Output("selected-region", "data"), Output("selected-special", "data")], Input("world-map", "clickData"), [State("selected-country", "data"), State("selected-region", "data"), State("selected-special", "data")], prevent_initial_call=True)
def store_click_target(clickData, curr_c, curr_r, curr_s):
    if not clickData: return curr_c, curr_r, curr_s
    pt = clickData["points"][0]
    cd = pt.get("customdata")
    if cd and len(cd) > 0 and "No data" in str(cd[0]) and "location" in pt: return curr_c, curr_r, curr_s
    if cd and len(cd) >= 4:
        if cd[3] == "sea_ice": return None, cd[0], None
        if cd[3] == "sea_level": return None, "Sea Level", None
    if cd and len(cd) >= 2 and cd[1] == "special": return None, None, cd[0]
    if "location" in pt: return pt["location"], None, None
    return curr_c, curr_r, curr_s

@app.callback([Output("chart-mode-label", "children"), Output("chart-mode-sublabel", "children"), Output("chart-mode", "options"), Output("container-main", "style"), Output("selector-divider", "style"), Output("container-sub", "style"), Output("chart-mode-main", "value"), Output("chart-mode", "value")], [Input("selected-country", "data"), Input("selected-region", "data"), Input("selected-special", "data"), Input("chart-mode-main", "value"), Input("chart-mode", "value")])
def update_ui(country, region, special, main_v, sub_v):
    tid = ctx.triggered_id
    show, hide = {"display": "block", "flex": "1"}, {"display": "none"}
    div = {"width": "1px", "backgroundColor": "#e0e0e0", "height": "40px", "margin": "0 15px"}
    if tid in ["selected-country", "selected-region", "selected-special"]: main_v, sub_v = "total", None
    if tid == "chart-mode-main" and main_v: sub_v = None
    elif tid == "chart-mode" and sub_v: main_v = None

    if special == "Temperature":
        opts = [{"label": " Line Chart", "value": "temp"}, {"label": " Data Table", "value": "temp_table"}]
        return "Global Temp View:", "Global Temperature View:", opts, hide, hide, {"display": "block"}, None, (sub_v if sub_v in ["temp", "temp_table"] else "temp")
    if region:
        title = "Sea Level View:" if region == "Sea Level" else f"{region} Ice Extent View:"
        opts = [{"label": " Line Chart", "value": "sea"}, {"label": " Data Table", "value": "sea_table"}] if region == "Sea Level" else [{"label": " Area Chart", "value": "area"}, {"label": " Bar Chart", "value": "bar"}, {"label": " Data Table", "value": "ice_table"}]
        return title, title, opts, hide, hide, {"display": "block"}, None, (sub_v if sub_v in [o['value'] for o in opts] else opts[0]['value'])
    return "Country CO2 View:", "Source Breakdown:", [{"label": " Area Chart", "value": "area"}, {"label": " Pie Chart", "value": "pie"}, {"label": " Global Ranking", "value": "table"}], show, div, {"display": "block", "flex": "2"}, main_v, sub_v

@app.callback(Output("world-map", "figure"), Input("year-slider", "value"))
def update_map(year): return make_map(year)

@app.callback(Output("detail-chart", "figure"), [Input("selected-country", "data"), Input("selected-region", "data"), Input("selected-special", "data"), Input("year-slider", "value"), Input("chart-mode", "value"), Input("chart-mode-main", "value")])
def update_detail(country, region, special, year, sub_m, main_m):
    if special == "Temperature": return make_temperature_table(year) if sub_m == "temp_table" else make_temperature_line(year)
    if region == "Sea Level": return make_sea_level_table(year) if sub_m == "sea_table" else make_sea_level_line(year)
    if region:
        if sub_m == "ice_table": return make_sea_ice_table(region, year)
        if sub_m == "bar": return make_sea_ice_bar(region, year)
        return make_sea_ice_area(region, year)
    if country:
        if sub_m == "table": return make_global_table(year)
        if sub_m == "area": return make_source_area(country, year)
        if sub_m == "pie": return make_pie(country, year)
        if main_m == "local_table": return make_country_history_table(country, year)
        return make_total_line(country, year)
    return make_empty_detail(year)

@app.callback(Output("temperature-chart", "figure"), [Input("year-slider", "value")])
def update_temp_sync(year): return make_temperature_line(year)

if __name__ == "__main__":
    app.run(debug=False)
