# 🌦️ UK Weather Analysis App

This Streamlit app provides a climatology analysis (temperature, precipitation, wind, etc.) for any UK postcode, for up to 20 years prior.

## 🚀 Features
- Input any UK postcode
- Automatically fetches coordinates using the postcodes.io API
- Collects 5-20 years of weather data using the Meteostat API
- Displays monthly averages and 3×2 weather plots
- Download results as CSV or PNG

## 🧭 How to Use
1. Go to the hosted app: (********)
2. Enter a UK postcode
3. Choose how many years of data to include
4. View the charts and download results

## 🧰 Local Setup (for developers)
To run locally:

```bash
git clone https://github.com/yourusername/weather-app.git
cd weather-app
pip install -r requirements.txt
streamlit run app.py
