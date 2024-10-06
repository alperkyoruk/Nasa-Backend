from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from flask_cors import CORS


# Load environment variables from .env file
load_dotenv()
API_KEY = os.getenv("API_KEY")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///soil_data.db'
db = SQLAlchemy(app)
CORS(app)


# Database model for storing soil data
class SoilData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    nitrogen = db.Column(db.Float, nullable=False)
    nitrogen_uncertainty = db.Column(db.Float, nullable=False)  # Uncertainty column
    ph = db.Column(db.Float, nullable=False)
    moisture = db.Column(db.Float, nullable=False)
    cec = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)  # New temperature column
    humidity = db.Column(db.Float, nullable=False)  # New humidity column
    recommendations = db.Column(db.String, nullable=False)
    predictions = db.Column(db.String, nullable=False)
    date_recorded = db.Column(db.DateTime, default=datetime.now(timezone.utc))  # New date column

# Initialize the database
with app.app_context():
    db.create_all()

# Function to get soil data from SoilGrids API
def get_soil_data(lat, lon):
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&depth=0-5cm"
    response = requests.get(url)
    
    if response.status_code == 200:
        soil_data = response.json()['properties']['layers']
        
        # Check for null values in the soil data
        if all(value is None for layer in soil_data for value in layer.values()):
            return {"error": "Data returned is null. Please try again later."}
        
        return soil_data
    else:
        return {"error": f"Failed to fetch data: {response.status_code}"}

# Function to get weather data
def get_weather_data(lat, lon):
    weather_url = f"https://api.weatherapi.com/v1/forecast.json?key={API_KEY}&q={lat},{lon}&days=5&aqi=no&alerts=no"
    response = requests.get(weather_url)
    if response.status_code == 200:
        return response.json()['forecast']['forecastday']
    else:
        return None

# Function to generate recommendations
def generate_recommendations(soil_data, weather_data):
    nitrogen = soil_data.get('nitrogen', 0)
    moisture = soil_data.get('wv0010', 0)
    ph = soil_data.get('phh2o', 0) / 10
    cec = soil_data.get('cec', 0)
    recommendations = set()
    
    if nitrogen < 100:
        recommendations.add("Consider adding nitrogen-based fertilizers.")
    if moisture < 0.2:
        recommendations.add("Soil moisture is low. Increase irrigation.")
    if 6 < ph < 7.5:
        recommendations.add("Soil pH is within the optimal range.")
    elif ph < 6:
        recommendations.add("Consider adding lime to raise the pH.")
    elif ph > 7.5:
        recommendations.add("Consider adding sulfur to lower the pH.")
    if cec >= 10:
        recommendations.add("CEC is within the optimal range.")
    
    if weather_data:
        avg_rain = sum(day['day']['daily_chance_of_rain'] for day in weather_data) / len(weather_data)
        avg_wind = sum(day['day']['maxwind_kph'] for day in weather_data) / len(weather_data)
        if avg_rain > 50:
            recommendations.add(f"High average chance of rain ({avg_rain:.1f}%). Delay irrigation.")
        if avg_wind > 20:
            recommendations.add(f"Strong winds expected ({avg_wind:.1f} kph). Protect crops.")
    
    return list(recommendations)

# Helper function to find closest coordinates in the database
def find_closest_coordinates(lat, lon, threshold=0.5):
    records = SoilData.query.all()
    for record in records:
        if abs(record.lat - lat) <= threshold and abs(record.lon - lon) <= threshold:
            return record
    return None

# Route to handle GET request and analyze soil data
@app.route('/api/analyze', methods=['GET'])
def analyze_soil():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))

    # Check if similar coordinates exist
    existing_record = find_closest_coordinates(lat, lon)
    if existing_record:
        if existing_record.date_recorded.tzinfo is None:
            existing_record.date_recorded = existing_record.date_recorded.replace(tzinfo=timezone.utc)
        # Check if the record is older than 2 days
        if datetime.now(timezone.utc) - existing_record.date_recorded > timedelta(days=2):
            db.session.delete(existing_record)  # Delete the old record
            db.session.commit()  # Commit the deletion
        else:
            return jsonify({
                'status': 'found',
                'message': 'Using existing data from the database.',
                'soil_data': {
                    'nitrogen': f"{existing_record.nitrogen} g/kg",
                    'nitrogen_uncertainty': f"{existing_record.nitrogen_uncertainty} ",
                    'ph': f"{existing_record.ph} pH",
                    'moisture': f"{existing_record.moisture} cm³/cm³",
                    'cec': f"{existing_record.cec} cmol(c)/kg",
                    'temperature': f"{existing_record.temperature} °C",
                    'humidity': f"{existing_record.humidity} %"
                },
                'predictions': existing_record.predictions,
                'recommendations': existing_record.recommendations
            })

    # Fetch soil data and weather data
    soil_data = get_soil_data(lat, lon)
    weather_data = get_weather_data(lat, lon)
    if not soil_data or not weather_data:
        return jsonify({'error': 'Failed to fetch data.'}), 500

    nitrogen_layer = next((layer for layer in soil_data if layer['name'] == 'nitrogen'), None)
    phh2o_layer = next((layer for layer in soil_data if layer['name'] == 'phh2o'), None)
    wv0010_layer = next((layer for layer in soil_data if layer['name'] == 'wv0010'), None)
    cec_layer = next((layer for layer in soil_data if layer['name'] == 'cec'), None)

    # Retrieve nitrogen values
    if nitrogen_layer:
        nitrogen_values = nitrogen_layer['depths'][0]['values']
        nitrogen = nitrogen_values.get('mean')
        nitrogen_uncertainty = nitrogen_values.get('uncertainty', 0)  # Extracting uncertainty directly from values
    else:
        nitrogen = None
        nitrogen_uncertainty = None

    # Retrieve phh2o, wv0010, and cec values
    phh2o = phh2o_layer['depths'][0]['values'].get('mean') if phh2o_layer else None
    wv0010 = wv0010_layer['depths'][0]['values'].get('mean') if wv0010_layer else None
    cec = cec_layer['depths'][0]['values'].get('mean') if cec_layer else None

    # Store the new record in the database
    new_record = SoilData(
        lat=lat,
        lon=lon,
        nitrogen=nitrogen,
        nitrogen_uncertainty=nitrogen_uncertainty,
        ph=phh2o,
        moisture=wv0010,
        temperature=weather_data[0]['day']['avgtemp_c'],
        humidity=weather_data[0]['day']['avghumidity'],
        cec=cec,
        recommendations="; ".join(generate_recommendations({
            'nitrogen': nitrogen,
            'wv0010': wv0010,
            'phh2o': phh2o,
            'cec': cec
        }, weather_data)),
        predictions="",  # Add prediction logic if needed
        date_recorded=datetime.now(timezone.utc)
    )
    
    db.session.add(new_record)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'soil_data': {
            'nitrogen': f"{nitrogen} g/kg",
            'nitrogen_uncertainty': f"{nitrogen_uncertainty} ",
            'ph': f"{phh2o/10} pH",
            'moisture': f"{wv0010} cm³/cm³",
            'cec': f"{cec} cmol(c)/kg",
            'temperature': f"{weather_data[0]['day']['avgtemp_c']} °C",
            'humidity': f"{weather_data[0]['day']['avghumidity']} %"
        },
        'recommendations': new_record.recommendations
    })

if __name__ == '__main__':
    app.run(debug=True)
