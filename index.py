# /index.py
# -*- coding: utf-8 -*-
"""
Traceability Tool Dashboard for Vercel
"""

# =================
# 1. Libraries
# =================

from dash import Dash, html, dcc, callback, Output, Input
from dash.dependencies import Input, Output, State
import dash_leaflet as dl
from dash_extensions.javascript import assign
import plotly.express as px
import pandas as pd
import requests
import json
import geopandas as gpd
import rasterio
from shapely.geometry import Point

# =================
# 2. Data Loading (Simulated for Vercel)
# =================
# IMPORTANT: Vercel's serverless environment is ephemeral.
# You cannot save files locally like in a traditional server.
# Data should be loaded from a remote source (API, S3 bucket, etc.)
# For this example, we will continue to fetch from the Kobo API.
# The local file access for shapefiles and rasters will need to be replaced.
# A common pattern is to host these files on a service like Amazon S3,
# GitHub (for smaller files), or another cloud storage provider and
# provide a public URL to access them.

# Kobo Info
KOBO_TOKEN = "036d4c8aeb6a0c011630339e605e7e8bb5500c7b"
ASSET_UID = "aNkj5BVuLuqGfqustJMNaM"
KOBO_API_URL = f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_UID}/data.json/"
HEADERS = {"Authorization": f"Token {KOBO_TOKEN}"}

# Fetch data
try:
    response = requests.get(KOBO_API_URL, headers=HEADERS)
    response.raise_for_status() # Raise an exception for bad status codes
    data_kobo = response.json().get('results', [])
except requests.exceptions.RequestException as e:
    print(f"Error fetching Kobo data: {e}")
    data_kobo = []
except json.JSONDecodeError:
    print("Error decoding JSON from Kobo API")
    data_kobo = []


# --- Data Placeholder for local files ---
# In a real Vercel deployment, you would replace these local paths
# with URLs to the raw files hosted elsewhere (e.g., GitHub, S3).
# For now, this will cause an error on Vercel, but it preserves the logic.
# You will need to replace these paths with URLs.
try:
    # --- STEP 1: Define the URLs to your raw data files ---
    peatland_url = 'https://github.com/rizkaameliads/traceability-mockup-dashplotly/raw/refs/heads/main/assets/INDONESIA%20PEATLAND%202017.zip'
    protected_areas_url = 'https://github.com/rizkaameliads/traceability-mockup-dashplotly/raw/refs/heads/main/assets/Protected_Areas_Generalized.zip'
    defor_year_url = 'https://github.com/rizkaameliads/traceability-mockup-dashplotly/raw/refs/heads/main/assets/Deforestation_Year_TMF.tif'

    # --- STEP 2: Read the vector data (like shapefiles) using GeoPandas ---
    # GeoPandas can read directly from a URL.
    peatland_khGambut_gdf = gpd.read_file(peatland_url)
    peatland_khGambut_gdf = peatland_khGambut_gdf.to_crs(epsg=4326)

    protected_areas_gdf = gpd.read_file(protected_areas_url)
    protected_areas_gdf = protected_areas_gdf.to_crs(epsg=4326)

    # --- STEP 3: Read the raster data (like .tif files) ---
    # Rasterio needs a bit more help. We first get the file content with 'requests',
    # then open it from memory.
    response_raster = requests.get(defor_year_url)
    response_raster.raise_for_status()
    with rasterio.io.MemoryFile(response_raster.content) as memfile:
        deforYear = memfile.open()

except Exception as e:
    print(f"Error loading local data files: {e}")
    print("Please replace local file paths with URLs for Vercel deployment.")
    peatland_khGambut_gdf = gpd.GeoDataFrame([], geometry=[], crs="EPSG:4326")
    protected_areas_gdf = gpd.GeoDataFrame([], geometry=[], crs="EPSG:4326")
    deforYear = None

# Pop Up (handle empty dataframes)
if not peatland_khGambut_gdf.empty:
    peatland_khGambut_gdf['popup_html'] = peatland_khGambut_gdf.apply(
        lambda row: f"<b>Peatland</b><br>Name: {row.get('NAMA_KHG', 'N/A')}",
        axis=1
    )

if not protected_areas_gdf.empty:
    for col in protected_areas_gdf.columns:
        if pd.api.types.is_datetime64_any_dtype(protected_areas_gdf[col]):
            protected_areas_gdf[col] = protected_areas_gdf[col].astype(str)
    protected_areas_gdf['popup_html'] = protected_areas_gdf.apply(
        lambda row: f"<b>Protected Area</b><br>Name: {row.get('NAMOBJ', 'N/A')}",
        axis=1
    )

# WMS Layer URL
wms_url = "https://ies-ows.jrc.ec.europa.eu/iforce/tmf_v1/wms.py?"
wms_layer_name = "DeforestationYear"


## =========================
## 3. Layer Management
## =========================
on_each_feature = assign("""
    function(feature, layer) {
        if (feature.properties && feature.properties.popup_html) {
            layer.bindPopup(feature.properties.popup_html);
        }
    }
""")

geojson_layer1 = dl.GeoJSON(
    data=json.loads(peatland_khGambut_gdf.to_json()) if not peatland_khGambut_gdf.empty else {"type": "FeatureCollection", "features": []},
    options=dict(style=dict(color="#4E7254", fillColor="#4E7254", opacity=0.8, fillOpacity=0.5, weight=2), onEachFeature=on_each_feature),
    zoomToBounds=True, id='layer1'
)

style_handle = assign("""
    function(feature) {
        const category = feature.properties.NAMOBJ;
        let color = "gray";
        if (category === "Hutan Lindung") color = "#9D900180";
        else if (category === "Taman Wisata Alam") color = "#B3242980";
        else if (category === "Hutan Suaka Alam dan Wisata") color = "#E6D69080";
        else if (category === "Cagar Alam") color = "#927A6C80";
        else if (category === "Taman Buru") color = "#4A192C80";
        else if (category === "Taman Nasional") color = "#31572080";
        else if (category === "Taman Hutan Raya") color = "#474B4E80";
        else if (category === "Suaka Margasatwa") color = "#82422D80";
        else if (category === "Kawasan Suaka Alam/Kawasan Pelestarian Alam") color = "#1B558380";
        return { color: color, weight: 2, fillOpacity: 0.5, fillColor: color };
    }
""")

geojson_layer2 = dl.GeoJSON(
    data=json.loads(protected_areas_gdf.to_json()) if not protected_areas_gdf.empty else {"type": "FeatureCollection", "features": []},
    options=dict(style=style_handle, onEachFeature=on_each_feature),
    zoomToBounds=True, id='layer2'
)

wms_layer = dl.WMSTileLayer(url=wms_url, layers=wms_layer_name, format="image/png", transparent=True, opacity=0.7)

## =========================
## 4. Legend and Lists
## =========================
protected_area_legend_data = {
    "Hutan Lindung": "#9D900180", "Taman Wisata Alam": "#B3242980",
    "Hutan Suaka Alam dan Wisata": "#E6D69080", "Cagar Alam": "#927A6C80",
    "Taman Buru": "#4A192C80", "Taman Nasional": "#31572080",
    "Taman Hutan Raya": "#474B4E80", "Suaka Margasatwa": "#82422D80",
    "Kawasan Suaka Alam/Kawasan Pelestarian Alam": "#1B558380"
}
survey_data_legend_data = {"Safe": "black", "In Deforested Area": "orange", "In Protected Area": "red"}

def create_legend():
    protected_area_items = [html.Div([html.Div(style={'width': '10px', 'height': '10px', 'backgroundColor': color, 'marginRight': '5px', 'borderRadius': '30%'}), html.Span(name, style={'fontSize': '12px'})], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '5px'}) for name, color in protected_area_legend_data.items()]
    survey_data_items = [html.Div([html.Div(style={'width': '10px', 'height': '10px', 'backgroundColor': color, 'marginRight': '5px', 'borderRadius': '50%'}), html.Span(name, style={'fontSize': '12px'})], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '5px'}) for name, color in survey_data_legend_data.items()]
    return html.Div([
        html.H4("Map Legend", id='legend-toggle-button', style={'fontSize': '12px', 'cursor': 'pointer', 'margin': '0 0 5px 0'}),
        html.Div(id='legend-items-container', children=[
            html.Div([html.B("Survey Data", style={'fontSize': '12px'}), html.Div(children=survey_data_items)]),
            html.Div([html.B("Protected Areas (2021)", style={'fontSize': '12px'}), html.Div(children=protected_area_items)]),
            html.Div([html.Div(style={'width': '10px', 'height': '10px', 'backgroundColor': '#4E725480', 'marginRight': '5px', 'borderRadius': '30%'}), html.B("Southeast Asia Peatland", style={'fontSize': '12px'})], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '5px'})
        ], style={'display': 'none'})
    ], style={'position': 'absolute', 'bottom': '10px', 'left': '20px', 'backgroundColor': 'rgba(255, 255, 255, 0.9)', 'padding': '10px', 'borderRadius': '5px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.2)', 'zIndex': '1000'})

def create_household_list(df):
    household_cards = []
    for _, row in df.iterrows():
        dot_color = 'red' if row.get('in_protected_area', False) else ('orange' if row.get('in_deforested_area', False) else 'black')
        dt_str = pd.to_datetime(row['Data_collection_date']).strftime('%m/%d/%Y, %I:%M %p')
        household_cards.append(html.Div([
            html.Div([html.Span(className='list-item-dot', style={'backgroundColor': dot_color}), html.Span(f"Data Collection Date {dt_str}")], className='list-item-header'),
            html.Div([html.B("Farmer Name "), html.Span(row.get('A1_Producer_farmer_name_first_name', 'N/A'))]),
            html.Div([html.B("Farmer ID "), html.Span(row.get('A3_Farmer_ID', 'N/A'))]),
            html.Div([html.B("Group/Cooperative "), html.Span(row.get('A13_Farmer_group_cooperative', 'N/A'))])
        ], className='list-item'))
    return household_cards if household_cards else [html.P("No household data to display.")]

def create_deforested_areas_list(df):
    filtered_df = df[df.get('in_deforested_area', pd.Series(False, index=df.index)) == True]
    if filtered_df.empty:
        return [html.P("No survey points in deforested areas.", style={'fontStyle': 'italic', 'color': '#555'})]
    return [html.Div([html.Span(className='alert-item-dot', style={'backgroundColor': 'orange'}), html.Span(f"Farmer ID {row.get('A3_Farmer_ID', 'N/A')} is in deforested areas!")], className='alert-item') for _, row in filtered_df.iterrows()]

def create_protected_areas_list(df):
    filtered_df = df[df.get('in_protected_area', pd.Series(False, index=df.index)) == True]
    if filtered_df.empty:
        return [html.P("No survey points in protected areas.", style={'fontStyle': 'italic', 'color': '#555'})]
    return [html.Div([html.Span(className='alert-item-dot', style={'backgroundColor': 'red'}), html.Span(f"Farmer ID {row.get('A3_Farmer_ID', 'N/A')} is in protected areas!")], className='alert-item') for _, row in filtered_df.iterrows()]


## =========================
## 5. App and Layout
## =========================
app = Dash(__name__)
server = app.server # Expose server for Vercel (Gunicorn)

# Filter options
name_map = {"kub_jaya_abadi": "KUB Jaya Abadi", "kub_sejahtera_bahagia": "KUB Sejahtera Bahagia", "kub_tani_jaya": "KUB Tani Jaya"}
if data_kobo:
    all_groups = pd.DataFrame(data_kobo)['A13_Farmer_group_cooperative'].dropna().unique()
    farmer_group_options = [{'label': name_map.get(group, group), 'value': group} for group in all_groups]
else:
    farmer_group_options = []

app.layout = html.Div(style={'display': 'grid', 'gridTemplateColumns': '10% 10% 13.3% 13.3% 13.3% 12% 8% 20%', 'gridTemplateRows': '6% 4% 5% 10% 5% 10% 5% 25% 5% 25%', 'gap': '10px', 'height': '100vh', 'width': '100vw', 'position': 'relative'}, children=[
    dcc.Store(id='survey-data-store', data=data_kobo),
    html.Img(src='/assets/RCT_Logo.png', className='header-logo', style={'gridRow': 'span 2'}),
    html.H2('Traceability Tool', className='main-title', style={'gridColumn': 'span 4'}),
    html.Div([html.B('Select Farmer Group', className='control-title'), dcc.Checklist(id='farmer-group-filter', options=farmer_group_options, style={'fontSize': '12px'})], className='filter-container', style={'gridRow': 'span 2', 'gridColumn': 'span 2'}),
    html.Div([html.Div("Update the survey records:", className='control-title'), html.Button('Refresh', id='manual-refresh-button', className='refresh-button')], className='refresh-container', style={'gridRow': 'span 2'}),
    html.Div("Let's trace for a better, sustainable farm practice and management © 2025 ReClimaTech", className='sub-title', style={'gridColumn': 'span 4'}),
    html.B("Average Plot Area (ha)", className='indicator-title'),
    html.B("Average Synthetic Fertilizer (kg/ha)", className='indicator-title'),
    html.B("Pesticides Application", className='chart-title'),
    html.B("Herbicides Application", className='chart-title'),
    html.B("Agroforestry Practice", className='chart-title'),
    html.B("Education Level", className='chart-title', style={'gridColumn': 'span 2'}),
    html.B("Farmer Gender", className='chart-title'),
    html.H2(id='indicator-1', className='indicator-value'),
    html.H2(id='indicator-2', className='indicator-value'),
    html.Div(dcc.Graph(id='pie-chart-1', style={'height': '100%', 'width': '100%'}), style={'gridRow': 'span 3'}),
    html.Div(dcc.Graph(id='pie-chart-2', style={'height': '100%', 'width': '100%'}), style={'gridRow': 'span 3'}),
    html.Div(dcc.Graph(id='pie-chart-3', style={'height': '100%', 'width': '100%'}), style={'gridRow': 'span 3'}),
    html.Div(dcc.Graph(id='pie-chart-4', style={'height': '100%', 'width': '100%'}), style={'gridRow': 'span 3', 'gridColumn': 'span 2'}),
    html.Div(dcc.Graph(id='pie-chart-5', style={'height': '100%', 'width': '100%'}), style={'gridRow': 'span 3'}),
    html.B("Average Crop Productivity (kg/ha)", className='indicator-title'),
    html.B("Average Organic Fertilizer (kg/ha)", className='indicator-title'),
    html.H2(id='indicator-3', className='indicator-value'),
    html.H2(id='indicator-4', className='indicator-value'),
    html.Div(dl.Map([
        dl.TileLayer(url='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'),
        dl.LocateControl(locateOptions={'enableHighAccuracy': True}),
        dl.LayersControl([
            dl.BaseLayer(dl.TileLayer(), name="Base Map", checked=True),
            dl.Overlay(geojson_layer1, name="Southeast Asia Peatland", checked=False),
            dl.Overlay(geojson_layer2, name="Protected Areas (2021)", checked=False),
            dl.Overlay(wms_layer, name="Deforestation Year", checked=False),
            dl.Overlay(dl.LayerGroup(id='map-markers'), name="Survey Data", checked=True),
        ], position='topright')
    ], center=[-4, 118.79907798885809], zoom=4, style={'height': '100%'}, id='main_map'), className='map-container', style={'gridColumn': 'span 5', 'gridRow': 'span 4'}),
    html.B("⚠️ Alerts Deforestation", className='list-title'),
    html.B(id='alert1-counter', className='list-title'),
    html.B("Household List", className='list-title'),
    html.Div(id='alert1-list-container', style={'overflowY': 'auto', 'fontSize': '12px', 'gridColumn': 'span 2'}),
    html.Div(id='household-list-container', style={'overflowY': 'auto', 'fontSize': '12px', 'gridRow': 'span 3'}),
    html.B("🚨 Alerts Protected Area", className='list-title'),
    html.B(id='alert2-counter', className='list-title'),
    html.Div(id='alert2-list-container', style={'overflowY': 'auto', 'fontSize': '12px', 'gridColumn': 'span 2'}),
    create_legend()
])

## =========================
## 6. Callbacks
## =========================
@app.callback(Output('survey-data-store', 'data'), Input('manual-refresh-button', 'n_clicks'), prevent_initial_call=True)
def refresh_data(n_clicks):
    try:
        response = requests.get(KOBO_API_URL, headers=HEADERS)
        response.raise_for_status()
        return response.json().get('results', [])
    except requests.exceptions.RequestException as e:
        print(f"Error refreshing Kobo data: {e}")
        return []

@app.callback(
    [Output('map-markers', 'children'), Output('household-list-container', 'children'),
     Output('alert1-counter', 'children'), Output('alert1-list-container', 'children'),
     Output('alert2-counter', 'children'), Output('alert2-list-container', 'children'),
     Output('indicator-1', 'children'), Output('indicator-2', 'children'),
     Output('indicator-3', 'children'), Output('indicator-4', 'children'),
     Output('pie-chart-1', 'figure'), Output('pie-chart-2', 'figure'),
     Output('pie-chart-3', 'figure'), Output('pie-chart-4', 'figure'),
     Output('pie-chart-5', 'figure')],
    [Input('survey-data-store', 'data'), Input('farmer-group-filter', 'value')]
)
def update_dashboard(data_kobo, selected_groups):
    if not data_kobo:
        empty_fig = {'layout': {'xaxis': {'visible': False}, 'yaxis': {'visible': False}, 'annotations': [{'text': 'No data', 'showarrow': False}]}}
        return [], [html.P("No data available.")], "0 points", [], "0 points", [], "N/A", "N/A", "N/A", "N/A", empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    df = pd.DataFrame(data_kobo)
    df.dropna(subset=['B2_Plot_location'], inplace=True)
    df = df[df['B2_Plot_location'].str.contains(' ')]

    if selected_groups:
        filtered_df = df[df['A13_Farmer_group_cooperative'].isin(selected_groups)].copy()
    else:
        filtered_df = df.copy()

    if filtered_df.empty:
        empty_fig = {'layout': {'xaxis': {'visible': False}, 'yaxis': {'visible': False}, 'annotations': [{'text': 'No data for selection', 'showarrow': False}]}}
        return [], [html.P("No data for selected filter.")], "0 points", [], "0 points", [], "N/A", "N/A", "N/A", "N/A", empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    # --- Geographic Analysis ---
    filtered_df[['lat', 'lon']] = filtered_df['B2_Plot_location'].str.split(' ', expand=True).iloc[:, :2].astype(float)
    
    # NOTE: This part will not work on Vercel without loading the actual geospatial data from a URL.
    # The logic is kept for completeness, but it will default to False.
    filtered_df['in_protected_area'] = False
    filtered_df['in_deforested_area'] = False

    if not protected_areas_gdf.empty:
        filtered_gdf = gpd.GeoDataFrame(filtered_df, geometry=gpd.points_from_xy(filtered_df['lon'], filtered_df['lat']), crs=protected_areas_gdf.crs)
        points_inside = gpd.sjoin(filtered_gdf, protected_areas_gdf, how="inner", predicate="intersects")
        protected_ids = set(points_inside['_id'])
        filtered_df['in_protected_area'] = filtered_df['_id'].isin(protected_ids)

    # Deforestation check would also need the raster file loaded from a URL
    # For now, this logic is placeholder.
    # if deforYear:
    #     coords = [(p.x, p.y) for p in filtered_gdf.geometry]
    #     defor_values = [val[0] for val in deforYear.sample(coords)]
    #     year_map = {0: 2020, 1: 2021, 2: 2022, 3: 2023, 4: 2024}
    #     filtered_df['deforestation_year'] = [year_map.get(val) for val in defor_values]
    #     filtered_df['in_deforested_area'] = filtered_df['deforestation_year'].notna()

    # --- Create Components ---
    new_markers = []
    for _, row in filtered_df.iterrows():
        color = 'red' if row['in_protected_area'] else ('orange' if row['in_deforested_area'] else 'black')
        popup_content = html.Div([
            html.B("Farmer ID: "), html.Span(row.get('A3_Farmer_ID', 'N/A')), html.Br(),
            html.B("Plot Area (ha): "), html.Span(f"{row.get('plot_area', 0):.2f}" if pd.notna(row.get('plot_area')) else 'N/A')
        ])
        new_markers.append(dl.CircleMarker(center=[row['lat'], row['lon']], radius=3, color=color, children=[dl.Tooltip(f"Farmer ID: {row.get('A3_Farmer_ID', 'N/A')}"), dl.Popup(popup_content)]))

    household_list = create_household_list(filtered_df)
    alert1_counter = f"{filtered_df['in_deforested_area'].sum()} points"
    alert1_list = create_deforested_areas_list(filtered_df)
    alert2_counter = f"{filtered_df['in_protected_area'].sum()} points"
    alert2_list = create_protected_areas_list(filtered_df)

    # Indicators and Charts
    numeric_cols = ["plot_area", "C2_Total_synthetic_ast_year_on_farm_kg", "main_crop_productivity", "C1_Organic_fertiliz_ast_year_on_farm_kg"]
    for col in numeric_cols:
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')

    indi_1 = f'{filtered_df["plot_area"].mean():.2f}' if not filtered_df["plot_area"].isnull().all() else "N/A"
    indi_2 = f'{filtered_df["C2_Total_synthetic_ast_year_on_farm_kg"].mean():.2f}' if not filtered_df["C2_Total_synthetic_ast_year_on_farm_kg"].isnull().all() else "N/A"
    indi_3 = f'{filtered_df["main_crop_productivity"].mean():.2f}' if not filtered_df["main_crop_productivity"].isnull().all() else "N/A"
    indi_4 = f'{filtered_df["C1_Organic_fertiliz_ast_year_on_farm_kg"].mean():.2f}' if not filtered_df["C1_Organic_fertiliz_ast_year_on_farm_kg"].isnull().all() else "N/A"

    name_mappings = {
        "Are_you_applying_chemical_pest": {'yes': 'Yes', 'no': 'No'},
        "Are_you_applying_chemical_herb": {'yes': 'Yes', 'no': 'No'},
        "C5_Type_of_agroforestry_practice": {'fully_implement': 'Full', 'partially_implement': 'Partial', 'no': 'None'},
        "A6_Last_education_level": {'none': 'None', 'primary_school': 'Primary', 'secondary_school': 'Secondary', 'tertiary_school': 'Tertiary'},
        "A4_Gender": {'male': 'Male', 'female': 'Female'}
    }
    figures_pie = []
    for column, mapping in name_mappings.items():
        if column in filtered_df.columns:
            summary_df = filtered_df[column].value_counts().reset_index()
            summary_df.columns = ['Answer', 'Count']
            summary_df['Answer'] = summary_df['Answer'].map(mapping).fillna(summary_df['Answer'])
            fig = px.pie(summary_df, values='Count', names='Answer', hole=0.3)
            fig.update_traces(textposition='inside', textinfo='percent+label')
        else:
            fig = px.pie(pd.DataFrame({'Answer': ['No Data'], 'Count': [1]}), values='Count', names='Answer', hole=0.3)
            fig.update_traces(textinfo='none')
        
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=False, uniformtext_minsize=8, uniformtext_mode='hide', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        figures_pie.append(fig)
    
    return new_markers, household_list, alert1_counter, alert1_list, alert2_counter, alert2_list, indi_1, indi_2, indi_3, indi_4, *figures_pie

@app.callback(Output('legend-items-container', 'style'), Input('legend-toggle-button', 'n_clicks'), State('legend-items-container', 'style'), prevent_initial_call=True)
def toggle_overall_legend(n_clicks, current_style):
    return {'display': 'block'} if current_style['display'] == 'none' else {'display': 'none'}

# This is for local testing. Vercel will use the 'server' object.
if __name__ == '__main__':
    app.run_server(debug=True)
```json
// /vercel.json
{
  "version": 2,
  "builds": [
    {
      "src": "index.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "15mb",
        "runtime": "python3.9"
      }
    },
    {
      "src": "assets/**",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/assets/(.*)",
      "dest": "/assets/$1"
    },
    {
      "src": "/(.*)",
      "dest": "index.py"
    }
  ]
}
```text
# /requirements.txt
dash
dash-leaflet
dash-extensions
plotly
pandas
requests
geopandas
rasterio
shapely
gunicorn
```html
<!-- /assets/index.html -->
<!DOCTYPE html>
<html>
    <head>
        <title>Traceability Tool Dashboard</title>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
```css
/* /assets/style.css */
body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f8f9fa;
    color: #333;
}

.main-title {
    grid-column: span 4;
    color: #003366;
    margin: auto 0;
    font-size: 24px;
}

.sub-title {
    grid-column: span 4;
    font-size: 12px;
    color: #555;
    margin-top: -5px;
}

.header-logo {
    grid-row: span 2;
    width: 100px; /* Adjust size as needed */
    height: auto;
    margin: auto;
}

.filter-container, .refresh-container {
    grid-row: span 2;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 5px;
    background-color: #fff;
    border-radius: 5px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.control-title {
    font-weight: bold;
    font-size: 12px;
    margin-bottom: 5px;
}

.refresh-button {
    padding: 8px 12px;
    font-size: 12px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.refresh-button:hover {
    background-color: #0056b3;
}

.indicator-title, .chart-title, .list-title {
    font-weight: bold;
    font-size: 14px;
    color: #333;
    text-align: center;
    align-self: end;
}

.indicator-value {
    font-size: 28px;
    font-weight: bold;
    color: #003366;
    text-align: center;
    align-self: start;
    margin-top: 5px;
}

.map-container {
    grid-column: span 5;
    grid-row: span 4;
    border-radius: 5px;
    overflow: hidden; /* Ensures the map corners are rounded */
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

#household-list-container, #alert1-list-container, #alert2-list-container {
    background-color: #fff;
    border-radius: 5px;
    padding: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.list-item, .alert-item {
    border-bottom: 1px solid #eee;
    padding: 8px 5px;
    font-size: 11px;
}

.list-item:last-child, .alert-item:last-child {
    border-bottom: none;
}

.list-item-header {
    font-weight: bold;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
}

.list-item-dot, .alert-item-dot {
    height: 8px;
    width: 8px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
}

.alert-item {
    display: flex;
    align-items: center;
    color: #555;
}

/* Add your custom styles here */
