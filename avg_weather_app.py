import streamlit as st
import streamlit.components.v1 as components
#import matplotlib.pyplot as plt
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.colors as pc
import plotly.graph_objects as go
from datetime import datetime
from meteostat import Point, Daily
import pandas as pd
#import kaleido
import requests
import io
import re
from prophet import Prophet
#from prophet.serialize import model_to_json, model_from_json


# Color map for variables
color_map = {
    'tavg': 'green',
    'tmax': 'red',
    'tmin': 'lightblue',
    'prcp': 'blue',
    'tsun': 'orange',
    'wspd': 'grey'
}

# --- Define Function ---
def get_weather_data(postcode, start_year, end_year, show_trends=False, show_errorbars=False):
    # Fetch coordinates
    res = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
    if res.status_code != 200 or res.json()['status'] != 200:
        st.error("Invalid postcode. Please try again.")
        return None, None

    pc_data = res.json()
    lat = pc_data['result']['latitude']
    long = pc_data['result']['longitude']
    st.success(f"Coordinates for {postcode}: {lat:.4f}, {long:.4f}")

    # Define location and date range
    loc = Point(lat, long)
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)

    # Add number of days in each month (non-leap year assumption)
    days_in_month = {
        'Jan': 31, 'Feb': 28, 'Mar': 31, 'Apr': 30,
        'May': 31, 'Jun': 30, 'Jul': 31, 'Aug': 31,
        'Sep': 30, 'Oct': 31, 'Nov': 30, 'Dec': 31
    }

    # Fetch daily data
    data = Daily(loc, start, end)
    data = data.fetch()

    if data.empty:
        st.error("No weather data available for this postcode.")
        return None, None

    # Process data
    data.index = pd.to_datetime(data.index)
    data['month'] = data.index.month
    monthly_means = data.groupby('month').agg({
        'tavg': 'mean',
        'tmin': 'mean',
        'tmax': 'mean',
        'prcp': 'sum',
        'tsun': 'sum',   # sum daily minutes into monthly total
        'wspd': 'mean'
    })

    monthly_means.index = monthly_means.index.map({
        1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun',
        7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'
    })

    # Convert total monthly sunshine (minutes) to average daily sunshine (min/day)
    if 'tsun' in monthly_means.columns:
        monthly_means['tsun'] = [
            monthly_means.loc[m, 'tsun'] / days_in_month[m]
            for m in monthly_means.index
        ]

    # Monthly max/min for all variables
    monthly_max_all = data.groupby(data.index.month).max(numeric_only=True)
    monthly_min_all = data.groupby(data.index.month).min(numeric_only=True)

    # Map numeric months to names
    month_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct',
                 11: 'Nov', 12: 'Dec'}
    monthly_max_all.index = monthly_max_all.index.map(month_map)
    monthly_min_all.index = monthly_min_all.index.map(month_map)


    # --- Compute monthly extremes for error bars (if requested) ---
    monthly_max = None
    monthly_min = None
    # We'll take tmax/tmin if available (preferred). Otherwise fall back to tavg extremes.
    try:
        if 'tmax' in data.columns and 'tmin' in data.columns:
            monthly_max = data.groupby(data.index.month)['tmax'].max()
            monthly_min = data.groupby(data.index.month)['tmin'].min()
        elif 'tavg' in data.columns:
            # fallback: use daily average max/min
            monthly_max = data.groupby(data.index.month)['tavg'].max()
            monthly_min = data.groupby(data.index.month)['tavg'].min()
        # convert numeric-month index to month names to match monthly_means index
        if monthly_max is not None:
            monthly_max.index = monthly_max.index.map({
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            })
            monthly_min.index = monthly_min.index.map({
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            })
            # align to monthly_means index order and fill missing months with NaN
            monthly_max = monthly_max.reindex(monthly_means.index)
            monthly_min = monthly_min.reindex(monthly_means.index)
    except Exception:
        # If anything goes wrong, ensure them None so later logic can skip error bars
        monthly_max = None
        monthly_min = None


    # --- Compute monthly extremes (max/min) for all variables ---
    monthly_max_all = data.groupby(data.index.month).max(numeric_only=True)
    monthly_min_all = data.groupby(data.index.month).min(numeric_only=True)

    # Convert numeric-month index to month names
    month_map = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    monthly_max_all.index = monthly_max_all.index.map(month_map)
    monthly_min_all.index = monthly_min_all.index.map(month_map)

    # Compute monthly min/max daily sunshine
    if 'tsun' in monthly_max_all.columns and 'tsun' in monthly_min_all.columns:
        monthly_max_all['tsun_daily'] = monthly_max_all['tsun'] / pd.Series(days_in_month)
        monthly_min_all['tsun_daily'] = monthly_min_all['tsun'] / pd.Series(days_in_month)


    # Calculate average daily sunshine (hours per day)
#    if 'tsun' in monthly_means.columns:
#        monthly_means['tsun_daily'] = [
#            monthly_means.loc[m, 'tsun'] / days_in_month[m] for m in monthly_means.index
#        ]
#    if 'tsun' in monthly_means.columns:
#        monthly_means = monthly_means.drop(columns=['tsun'])

    # --- Create combined and individual interactive plots ---
    plot_vars = {
        'tavg': 'Average Temperature (°C)',
        'tmin': 'Minimum Temperature (°C)',
        'tmax': 'Maximum Temperature (°C)',
        'prcp': 'Precipitation (mm/month)',
        'tsun': 'Average Daily Sunshine (min/day)',
        'wspd': 'Wind Speed (km/h)'
    }

    # Only include variables that actually exist in the monthly_means DataFrame
    available_vars = {
        k: v for k, v in plot_vars.items()
        if k in monthly_means.columns #and k != 'tsun_daily'
    }

    # Create combined grid layout
    fig = make_subplots(rows=3, cols=2, subplot_titles=list(available_vars.values()))
    row_col_map = {
        0: (1, 1), 1: (1, 2),
        2: (2, 1), 3: (2, 2),
        4: (3, 1), 5: (3, 2)
    }


    err_dict = {}
    for var in available_vars.keys():
        if var == 'tavg':
            # Existing tavg min/max logic
            if 'tmax' in monthly_max_all.columns and 'tmin' in monthly_min_all.columns:
                err_plus = (monthly_max_all['tmax'] - monthly_means['tavg']).clip(lower=0)
                err_minus = (monthly_means['tavg'] - monthly_min_all['tmin']).clip(lower=0)
                err_dict['tavg'] = (err_plus, err_minus)
#        elif var == 'tsun_daily':
#            # Error bars for sunshine
#            err_plus = (monthly_max_all['tsun_daily'] - monthly_means['tsun_daily']).clip(lower=0)
#            err_minus = (monthly_means['tsun_daily'] - monthly_min_all['tsun_daily']).clip(lower=0)
#            err_dict['tsun_daily'] = (err_plus, err_minus)
        else:
            # Other variables
            if var == 'prcp':
                # Align days with month names
                days = pd.Series(days_in_month).reindex(monthly_means.index)

                # Convert daily max/min to monthly sums
                err_plus = (monthly_max_all[var] * days / 1).clip(lower=0) - monthly_means[var]
                err_minus = monthly_means[var] - (monthly_min_all[var] * days / 1).clip(lower=0)
                err_dict[var] = (err_plus, err_minus)
            elif var == 'tsun':
                # Convert monthly max/min daily sunshine to same unit as monthly_means (min/day)
                days = pd.Series(days_in_month).reindex(monthly_means.index)
                tsun_max_daily = monthly_max_all['tsun'] / days
                tsun_min_daily = monthly_min_all['tsun'] / days
                err_plus = (tsun_max_daily - monthly_means['tsun']).clip(lower=0)
                err_minus = (monthly_means['tsun'] - tsun_min_daily).clip(lower=0)
                err_dict['tsun'] = (err_plus, err_minus)
            else:
                err_plus = (monthly_max_all[var] - monthly_means[var]).clip(lower=0)
                err_minus = (monthly_means[var] - monthly_min_all[var]).clip(lower=0)
                err_dict[var] = (err_plus, err_minus)


    mode_type = "lines+markers" if show_trends else "markers"

    for i, (col, label) in enumerate(available_vars.items()):
        if col not in monthly_means.columns:
            continue  # skip missing variables
        # Base trace
        trace_kwargs = dict(
            x=monthly_means.index,
            y=monthly_means[col],
            mode=mode_type,
            name=label,
            line=dict(color=color_map.get(col, None)),
            marker=dict(size=8, opacity=0.8)
        )

        # Add error bars if available
        if show_errorbars and col in err_dict:
            err_plus, err_minus = err_dict[col]
            trace_kwargs['error_y'] = dict(
                type='data',
                array=err_plus.values,
                arrayminus=err_minus.values,
                visible=True
            )

            # Add hover showing min/max values
            if col == 'tavg':
                # Existing tavg hover
                trace_kwargs['customdata'] = list(zip(monthly_min_all['tmin'], monthly_max_all['tmax']))
                trace_kwargs['hovertemplate'] = (
                    "<b>%{x}</b><br>"
                    "Avg Temp: %{y:.2f}<br>"
                    "Min Temp: %{customdata[0]:.2f}<br>"
                    "Max Temp: %{customdata[1]:.2f}"
                )
#            elif col == 'tsun_daily':
#                # New hover for sunshine
#               trace_kwargs['customdata'] = list(zip(monthly_min_all['tsun_daily'], monthly_max_all['tsun_daily']))
#                trace_kwargs['hovertemplate'] = (
#                    "<b>%{x}</b><br>"
#                    f"{label}<br>"
#                    "Avg: %{y:.2f}<br>"
#                    "Min: %{customdata[0]:.2f}<br>"
#                    "Max: %{customdata[1]:.2f}"
#                )
            else:
                # Hover for all other variables
                if col == 'prcp':
                    # Convert daily min/max to monthly sums (same as error bars)
                    days = pd.Series(days_in_month).reindex(monthly_means.index)
                    err_plus, err_minus = err_dict[col]

                    hover_max = monthly_means[col] + err_plus
                    hover_min = monthly_means[col] - err_minus
                else:
                    hover_min = monthly_min_all[col]
                    hover_max = monthly_max_all[col]

                trace_kwargs['customdata'] = list(zip(hover_min, hover_max))
                trace_kwargs['hovertemplate'] = (
                    f"<b>%{{x}}</b><br>{label}<br>"
                    "Avg: %{y:.2f}<br>"
                    "Min: %{customdata[0]:.2f}<br>"
                    "Max: %{customdata[1]:.2f}"
                )
        else:
            trace_kwargs['hovertemplate'] = "<b>%{x}</b><br>%{y:.2f}"

        fig.add_trace(
            go.Scatter(**trace_kwargs),
            row=row_col_map[i][0],
            col=row_col_map[i][1]
        )


    fig.update_layout(
        height=800,
        width=1000,
        title_text=f"Average Monthly Weather Overview for {postcode.upper()} ({start_year}-{end_year})",
        template="plotly_white",
        showlegend=False
    )

    # --- Create individual plots for each variable ---
    individual_figs = {}
    for var, label in available_vars.items():
        individual_figs[var] = px.line(
            monthly_means,
            x=monthly_means.index,
            y=var,
            title=f"{label} ({postcode.upper()})",
            template='plotly_white',
            color_discrete_sequence=[color_map[var]]
        )

        if show_trends:
            individual_figs[var].update_traces(mode="lines+markers")
        else:
            individual_figs[var].update_traces(mode="markers")

        if show_errorbars and var in err_dict:
            err_plus, err_minus = err_dict[var]
            if var == 'prcp':
                days = pd.Series(days_in_month).reindex(monthly_means.index)
                hover_min = (monthly_min_all[var] * days)
                hover_max = (monthly_max_all[var] * days)
            elif var == 'tavg':
                hover_min = monthly_min_all['tmin']
                hover_max = monthly_max_all['tmax']
            elif var == 'tsun':
                days = pd.Series(days_in_month).reindex(monthly_means.index)
                hover_min = monthly_min_all['tsun'] / days
                hover_max = monthly_max_all['tsun'] / days
            else:
                hover_min = monthly_min_all[var]
                hover_max = monthly_max_all[var]

            individual_figs[var].update_traces(
                error_y=dict(
                    type='data',
                    array=err_plus.values,
                    arrayminus=err_minus.values,
                    visible=True
                ),
                customdata=list(zip(hover_min, hover_max)),
                hovertemplate=(
                    f"<b>%{{x}}</b><br>{label}<br>"
                    "Avg: %{y:.2f}<br>"
                    "Min: %{customdata[0]:.2f}<br>"
                    "Max: %{customdata[1]:.2f}"
                )
            )

            # If this is the average temperature plot and error arrays are available, add error bars
            if var == 'tavg' and err_plus is not None and err_minus is not None:
                if var == 'prcp':
                    days = pd.Series(days_in_month).reindex(monthly_means.index)
                    err_plus, err_minus = err_dict[col]

                    hover_max = monthly_means[col] + err_plus
                    hover_min = monthly_means[col] - err_minus
                elif var == 'tavg':
                    hover_min = monthly_min_all['tmin']
                    hover_max = monthly_max_all['tmax']
                else:
                    hover_min = monthly_min_all[var]
                    hover_max = monthly_max_all[var]

                individual_figs[var].update_traces(
                    error_y=dict(
                        type='data',
                        array=err_plus.values,
                        arrayminus=err_minus.values,
                        visible=True
                    ),
                    customdata=list(zip(hover_min, hover_max)),
                    hovertemplate=(
                        f"<b>%{{x}}</b><br>{label}<br>"
                        "Avg: %{y:.2f}<br>"
                        "Min: %{customdata[0]:.2f}<br>"
                        "Max: %{customdata[1]:.2f}"
                    )
                )

        if not show_trends:
            individual_figs[var].update_traces(mode="markers")  # override line if needed



    # Return all data and figures
    return data, monthly_means, monthly_min, monthly_max, fig, plot_vars, individual_figs, color_map


# ----------------- Prophet forecast helpers -----------------
# Shared colour palette for variable ordering (used in charts + forecast)
FORECAST_COLORS = [
    "green",
    "red",
    "lightblue",
    "blue",
    "orange",
    "grey"
]
@st.cache_data(show_spinner=False)
def build_monthly_series_from_daily(daily_df, var='tavg'):
    """
    Build a monthly-resampled pandas Series (DatetimeIndex at month-end) from the daily DataFrame.
    daily_df: DataFrame with DatetimeIndex (your `data` variable)
    var: variable column name, e.g. 'tavg'
    """
    if var not in daily_df.columns:
        return pd.Series(dtype=float)
    monthly = daily_df[var].resample('M').mean()
    monthly = monthly.sort_index()
    # drop months with NaN (Prophet requires no missing ds/y pairs)
    monthly = monthly.dropna()
    monthly.index = pd.to_datetime(monthly.index)
    return monthly

# cache the forecast results so repeated clicks don't re-fit unless inputs change
@st.cache_data(show_spinner=False)
def fit_and_forecast_prophet(monthly_series, periods=12, yearly_seasonality=True):
    """
    monthly_series: pd.Series with DatetimeIndex (monthly end-of-month dates)
    returns: forecast DataFrame containing ds, yhat, yhat_lower, yhat_upper, and the model object
    """
    # prepare DataFrame for Prophet
    df = monthly_series.reset_index()
    df.columns = ['ds', 'y']  # force correct naming
    # if input series has no rows, return empty
    if df.empty:
        return pd.DataFrame(), None

    m = Prophet(yearly_seasonality=yearly_seasonality, weekly_seasonality=False, daily_seasonality=False)
    m.fit(df)

    future = m.make_future_dataframe(periods=periods, freq='M')
    fcst = m.predict(future)

    # Return forecast df and the fitted model
    return fcst[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy(), m

def plot_prophet_forecast(monthly_series, fcst_df, var_label="Average Temperature (°C)",
                          postcode="POSTCODE", forecast_only=True, color=None):
    """
    Plot forecast-only region (fcst_df must contain ds, yhat, yhat_lower, yhat_upper).
    color: hex or named color string for the median line.
    """
    fcst_df = fcst_df.copy()
    fcst_df['ds'] = pd.to_datetime(fcst_df['ds'])

    # find last historical date
    if monthly_series is not None and not monthly_series.empty:
        last_hist = pd.to_datetime(monthly_series.index.max())
    else:
        last_hist = fcst_df['ds'].min() - pd.DateOffset(days=1)

    # Keep only forecast rows (ds > last_hist)
    forecast_mask = fcst_df['ds'] > last_hist
    f_med = fcst_df.loc[forecast_mask]
    f_all = fcst_df.loc[forecast_mask].copy()

    # Choose color fallback
    if color is None:
        color = "royalblue"


    fig = go.Figure()

    # Forecast median
    fig.add_trace(go.Scatter(
        x=f_med['ds'],
        y=f_med['yhat'],
        mode='lines+markers',
        name='',
        line=dict(color=color),
        marker=dict(size=6),
        customdata=list(zip(f_all['yhat_lower'], f_all['yhat_upper'])),  # min/max
        hovertemplate=(
            "%{x|%b %Y}<br>"
            "Median: %{y:.2f}<br>"
            "Min: %{customdata[0]:.2f}<br>"
            "Max: %{customdata[1]:.2f}<extra></extra>"
        )
    ))

    # Confidence ribbon (forecast region only)
    if not f_all.empty and 'yhat_upper' in f_all.columns and 'yhat_lower' in f_all.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([f_all['ds'], f_all['ds'][::-1]]),
            y=pd.concat([f_all['yhat_upper'], f_all['yhat_lower'][::-1]]),
            fill='toself',
            fillcolor='rgba(173, 216, 230, 0.25)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo='skip',
            showlegend=True,
            name='Forecast 95% CI'
        ))

    fig.update_layout(
        title=f"{var_label}",
        xaxis_title="Date",
        yaxis_title=var_label,
        template="plotly_white",
        height=320,
        margin=dict(t=40, b=30, l=40, r=20),
        showlegend=False
    )
    return fig



# --- google analytics ---

GA_MEASUREMENT_ID = "G-2D4KH63P91"  # Replace with your GA Measurement ID

components.html(f"""
<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());

  gtag('config', '{GA_MEASUREMENT_ID}');
</script>
""", height=0)




# --- Streamlit UI ---
st.set_page_config(
    page_title="UK Weather Analysis",   # Title shown in browser tab
    page_icon="🌦️",                    # Emoji or image path (favicon)
    layout="wide",                      # 'centered' or 'wide'
    initial_sidebar_state="expanded"    # 'expanded' or 'collapsed'
)

st.title("UK Weather Pattern Analysis")
st.subheader("Analyse average monthly weather by postcode")
st.markdown("---")  # Horizontal divider line
st.caption("Data from Meteostat (2005–2025)")
st.caption("Note: data may be unavailable for some regions/years")

tab1, tab2, tab3, tab4 = st.tabs(["Charts", "Data Table", "Yearly Trends", "Forecast"])

st.sidebar.header("Settings ⚙️")

postcode = st.sidebar.text_input("Enter a UK Postcode", "---- ---")
if postcode:
    if not re.match(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", postcode, re.I):
        st.error("Invalid UK postcode")

year_range = st.sidebar.slider(
    "Select range of years to analyse",
    min_value=2005,
    max_value=2025,
    value=(2015, 2025),  # default range
    step=1,
    help="Select start and end year for historical data"
)

start_year, end_year = year_range



yearly_variable = st.sidebar.selectbox(
    "Select variable for yearly trends",
    [
        "Average Temperature (°C)",
        "Minimum Temperature (°C)",
        "Maximum Temperature (°C)",
        "Precipitation (mm/month)",
        "Average Daily Sunshine (min/day)",
        "Wind Speed (km/h)"
    ]
)

month_names = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

selected_months = st.sidebar.multiselect(
    "Select month(s) to display:",
    options=month_names,
    default=month_names  # default = all months
)


yearly_var_map = {
    "Average Temperature (°C)": "tavg",
    "Minimum Temperature (°C)": "tmin",
    "Maximum Temperature (°C)": "tmax",
    "Precipitation (mm/month)": "prcp",
    "Average Daily Sunshine (min/day)": "tsun",
    "Wind Speed (km/h)": "wspd"
}


with st.sidebar.expander("Advanced Options"):
    show_trends = st.checkbox("Show trend lines", value=True)
    show_errorbars = st.checkbox("Show monthly min/max as error bars", value=False)

    #Forecast options
    st.markdown("---")
    st.write("Forecast options")
    forecast_horizon = st.number_input("Forecast horizon (months)", min_value=1, max_value=24, value=12, step=1)



if st.sidebar.button("Run Analysis"):
    st.session_state['run'] = True
    with st.spinner("Fetching and processing weather data..."):
        data, monthly_means, monthly_min, monthly_max, fig, plot_vars, individual_figs, color_map = get_weather_data(postcode, start_year, end_year, show_trends, show_errorbars)

    if monthly_means is not None:
        # ---- Compute yearly averages for each month ----
        data['year'] = data.index.year
        data['month_num'] = data.index.month

        # Prepare dataframe: rows = years, columns = months
        year_month_df = data.groupby(['year', 'month_num']).mean(numeric_only=True)

        # Convert to an easier structure: dict of month → dataframe
        monthly_yearly = {}
        for m in range(1, 12 + 1):
            df_m = year_month_df.xs(m, level='month_num')[yearly_var_map[yearly_variable]].reset_index()
            df_m.columns = ['Year', yearly_variable]
            monthly_yearly[m] = df_m

        selected_var = yearly_var_map[yearly_variable]


        with tab2:
            # Remove unused columns
            columns_to_drop = ['snow', 'wdir', 'wpgt', 'pres']
            monthly_means = monthly_means.drop(columns=[c for c in columns_to_drop if c in monthly_means.columns])

            # Rename table headers before displaying
            readable_columns = {
                'tavg': 'Average Temp. (°C)',
                'tmin': 'Min Temp. (°C)',
                'tmax': 'Max Temp. (°C)',
                'prcp': 'Precipitation (mm/month)',
                'tsun': 'Sunshine (min/day)',
                'wspd': 'Wind Speed (km/h)'
            }

            display_df = monthly_means.rename(columns=readable_columns)
            st.dataframe(display_df.round(2))


            # download csv of data
            csv = monthly_means.to_csv().encode('utf-8')
            st.download_button(
                label="Download Monthly Averages as CSV file",
                data=csv,
                file_name=f"weather_summary_{postcode}.csv",
                mime="text/csv"
            )

        with tab3:
            st.subheader("Yearly Trends by Month")

            # Build a mapping: "January" -> 1, etc.
            month_to_num = {name: i + 1 for i, name in enumerate(month_names)}
            # Convert selected month names to numbers
            months_to_plot = [month_to_num[m] for m in selected_months]

            # Only plot selected months
            cols = st.columns(3)
            for i, m in enumerate(months_to_plot):
                with cols[i % 3]:
                    # fetch the dataframe for this month
                    df_m = monthly_yearly[m]

                    # filter by user-selected year range
                    df_m = df_m[(df_m['Year'] >= start_year) & (df_m['Year'] <= end_year)]

                    # ----- YEARLY ERROR BARS (inside for-loop, per month) -----
                    if show_errorbars:
                        # Compute yearly min/max for the selected variable
                        yearly_min = data.groupby(['year', 'month_num'])[selected_var].min().reset_index()
                        yearly_max = data.groupby(['year', 'month_num'])[selected_var].max().reset_index()

                        # Extract min/max for this month
                        df_min = yearly_min[yearly_min['month_num'] == m]
                        df_max = yearly_max[yearly_max['month_num'] == m]

                        # Merge into df_m for alignment
                        df_m = df_m.merge(
                            df_min[['year', selected_var]],
                            left_on='Year',
                            right_on='year',
                            how='left'
                        ).rename(columns={selected_var: 'min_val'})

                        df_m = df_m.merge(
                            df_max[['year', selected_var]],
                            left_on='Year',
                            right_on='year',
                            how='left'
                        ).rename(columns={selected_var: 'max_val'})

                        # Calculate error bar arrays
                        err_plus = (df_m['max_val'] - df_m[yearly_variable]).clip(lower=0)
                        err_minus = (df_m[yearly_variable] - df_m['min_val']).clip(lower=0)


                    fig_m = px.line(
                        df_m,
                        x="Year",
                        y=yearly_variable,
                        markers=True,
                        title=month_names[m - 1],
                        template="plotly_white",
                        color_discrete_sequence=[color_map.get(selected_var, "black")]
                    )
                    fig_m.update_traces(
                        hovertemplate=f"(%{{x}}): %{{y:.2f}}"
                    )
                    if show_errorbars:
                        fig_m.update_traces(
                            error_y=dict(
                                type="data",
                                array=err_plus,
                                arrayminus=err_minus,
                                visible=True
                            ),
                            customdata=list(zip(df_m['min_val'], df_m['max_val'])),
                            hovertemplate="<b>%{x}</b><br>Avg: %{y:.2f}<br>Min: %{customdata[0]:.2f}<br>Max: %{customdata[1]:.2f}"
                        )
                    fig_m.update_layout(height=250)
                    st.plotly_chart(fig_m, use_container_width=True)
            st.info("You can download the plot as a PNG directly from the chart's toolbar.")

        with tab1:
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    'displayModeBar': True,
                    'modeBarButtonsToAdd': ['downloadImage'],  # <-- browser-based PNG download
                }
            )
            st.info("You can download the plot as a PNG directly from the chart's toolbar (top right).")
        # ----------------- Forecast tab (ALL VARIABLES) -----------------
        with tab4:
            st.subheader(f"{forecast_horizon}-month Forecast")

            full_var_map = {
                "Average Temperature (°C)": "tavg",
                "Minimum Temperature (°C)": "tmin",
                "Maximum Temperature (°C)": "tmax",
                "Precipitation (mm/month)": "prcp",
                "Average Daily Sunshine (min/day)": "tsun",
                "Wind Speed (km/h)": "wspd"
            }

            # We'll collect per-variable forecast DataFrames into a dict
            forecasts = {}
            failed_vars = []

            # iterate and compute forecasts
            for label, col in full_var_map.items():
                monthly_series = build_monthly_series_from_daily(data, var=col)
                monthly_series.name = col  # ensure name exists for caching key / clarity

                if monthly_series.empty:
                    failed_vars.append((label, col))
                    # produce an empty forecast DataFrame with ds to keep alignment
                    forecasts[col] = pd.DataFrame(columns=['ds','yhat','yhat_lower','yhat_upper'])
                    continue

                with st.spinner(f"Simulating Predictions for {label}..."):
                    fcst_df, model = fit_and_forecast_prophet(monthly_series, periods=forecast_horizon)

                if fcst_df is None or fcst_df.empty:
                    failed_vars.append((label, col))
                    forecasts[col] = pd.DataFrame(columns=['ds','yhat','yhat_lower','yhat_upper'])
                    continue

                forecasts[col] = fcst_df  # store full forecast (history+future)

            # Show quick message for any missing forecasts
            if failed_vars:
                missing_labels = ", ".join([f[0] for f in failed_vars])
                st.warning(f"No sufficient historical data to forecast: {missing_labels}")

            # ---------------- Render forecasts in 2x3 layout using color_map ----------------
            # We'll use 2 columns and 3 rows. Order is:
            # row1: indices 0,1 | row2: indices 2,3 | row3: indices 4,5
            labels_cols = list(full_var_map.items())

            for row_idx in range(3):
                cols = st.columns(2)  # 2 columns per row
                for col_idx in range(2):
                    idx = row_idx * 2 + col_idx
                    if idx >= len(labels_cols):
                        with cols[col_idx]:
                            st.write("")  # empty placeholder
                        continue

                    label, col = labels_cols[idx]
                    fcst_df = forecasts.get(col, pd.DataFrame())

                    plot_color = color_map.get(col, None)

                    with cols[col_idx]:
                        if fcst_df.empty:
                            st.info("No forecast (insufficient data).")
                        else:
                            hist_series = build_monthly_series_from_daily(data, var=col)
                            fig_fcst = plot_prophet_forecast(
                                monthly_series=hist_series,
                                fcst_df=fcst_df,
                                var_label=label,
                                postcode=postcode,
                                forecast_only=True,
                                color=plot_color
                            )
                            st.plotly_chart(fig_fcst, use_container_width=True)

                if row_idx < 2:
                    st.markdown("<div style='margin-bottom:12px'></div>", unsafe_allow_html=True)


            # Build combined forecast table for CSV
            # We want columns (in exact order and lowercase):
            # month, average temp, min temp, max temp, precipitation, sunshine, wind speed
            # We'll extract the forecast rows (future only) from each fcst DF and join on ds.

            # first pick the ds / future dates from any non-empty forecast (prefer tavg)
            ds_series = None
            for preferred in ['tavg', 'tmin', 'tmax', 'prcp', 'tsun', 'wspd']:
                if preferred in forecasts and not forecasts[preferred].empty:
                    df_pref = forecasts[preferred]
                    last_hist_date = pd.to_datetime(data.index.max()) if not data.empty else None
                    # future rows are ds > last_hist_date
                    if last_hist_date is not None:
                        future_rows = df_pref[df_pref['ds'] > last_hist_date]
                    else:
                        future_rows = df_pref.copy()
                    ds_series = future_rows['ds'].reset_index(drop=True)
                    break

            if ds_series is None or ds_series.empty:
                st.error("No forecast dates available to build CSV (all forecasts failed).")
            else:
                combined = pd.DataFrame({'ds': ds_series})


                # For each variable add the forecast median (yhat) aligned to combined['ds']
                for label, col in full_var_map.items():
                    dfc = forecasts[col]
                    if dfc.empty:
                        combined[col] = [pd.NA] * len(combined)
                        continue

                    last_hist_date = pd.to_datetime(data.index.max()) if not data.empty else None
                    if last_hist_date is not None:
                        df_future = dfc[dfc['ds'] > last_hist_date].reset_index(drop=True)
                    else:
                        df_future = dfc.reset_index(drop=True)

                    # If number of rows mismatches, reindex to combined by date (safer)
                    df_future = df_future.set_index('ds')
                    combined = combined.set_index('ds')
                    combined[col] = df_future['yhat']
                    combined = combined.reset_index()

                # Round all numeric values to 2 decimal places
                combined = combined.round(2)

                # Format month column as YYYY-MM (string) and reorder & rename columns to required headings
                combined['month'] = combined['ds'].dt.strftime('%Y-%m')
                combined['month'] = pd.to_datetime(combined['month'], format='%Y-%m')  # adjust format if needed
                combined['month'] = combined['month'].dt.strftime('%b %Y')  # e.g., "Jan 2025"
                # map column order & names exactly as requested
                ordered = pd.DataFrame()
                ordered['month'] = combined['month']
                ordered['average temp'] = combined.get('tavg', pd.Series([pd.NA]*len(combined)))
                ordered['min temp'] = combined.get('tmin', pd.Series([pd.NA]*len(combined)))
                ordered['max temp'] = combined.get('tmax', pd.Series([pd.NA]*len(combined)))
                ordered['precipitation'] = combined.get('prcp', pd.Series([pd.NA]*len(combined)))
                ordered['sunshine'] = combined.get('tsun', pd.Series([pd.NA]*len(combined)))
                ordered['wind speed'] = combined.get('wspd', pd.Series([pd.NA]*len(combined)))


                ordered = ordered.rename(columns={
                    'average temp': 'Average Temp. (°C)',
                    'min temp': 'Min Temp. (°C)',
                    'max temp': 'Max Temp. (°C)',
                    'precipitation': 'Precipitation (mm/month)',
                    'sunshine': 'Sunshine(min/day)',
                    'wind speed': 'Wind Speed (km/h)'
                })

                # Show the CSV table in the UI
                st.subheader("Data Table")
                st.dataframe(ordered.fillna('N/A'))

                # Create CSV bytes with exact header order and lowercase names
                csv = ordered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download forecast CSV",
                    data=csv,
                    file_name=f"forecast_combined_{postcode}.csv",
                    mime="text/csv"
                )

                st.info("Missing entries indicate insufficient historical data for that variable.")



st.markdown(
    """
    <hr>
    <p style='text-align: center; font-size: 14px; color: grey;'>
    © 2025 | Data sourced via Meteostat API
    </p>
    """,
    unsafe_allow_html=True
)


#   cd /Users/cam/Documents/python/weather_app
#   streamlit run avg_weather_app.py

#   streamlit run /Users/cam/Documents/python/weather_app/avg_weather_app.py



## ------------------------ push to gh --------------------------------------------


#cd /Users/cam/Documents/python/weather_app
#git add .
#git status
#git commit -m "..................."
#git push