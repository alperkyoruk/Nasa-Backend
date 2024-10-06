# Flask Soil Data API

This API integrates data from the SoilGrids and Weather APIs to provide insights on soil conditions, weather predictions, and irrigation recommendations. It saves data to a local SQLite database to reduce repeated API calls for similar coordinates.

## Prerequisites

Before running the application, make sure you have the following installed:

- Python 3.7 or higher
- pip (Python package installer)
- SQLite (included with Python)
- API keys for:
  - [WeatherAPI](https://www.weatherapi.com/) (sign up to get an API key)

## Setting Up the Project

1. **Clone the Repository**

   Clone or download this repository to your local machine.

2. **Install Dependencies**

   Navigate to the project directory and install the required Python libraries by running:

   ```bash
   pip install flask flask_sqlalchemy requests python-dotenv flask-cors

3. **Configure Environment Variables**

    Create a .env file in the root of the project and add your WeatherAPI key:
    
    ```env
    API_KEY=your_weather_api_key_here

4. **Database Initialization**

    To initialize the SQLite database, open a Python shell in the project directory and run:

    ```python
    from app import db
    db.create_all()
    ```
    
    This will create the soil_data.db file in the root directory.

  ## How It Works

### Soil and Weather Data Retrieval

    The application retrieves soil data from the [SoilGrids API](https://soilgrids.org) and weather data from [WeatherAPI](https://www.weatherapi.com/) for a given latitude and longitude.

### Data Storage

    The application stores data locally in an SQLite database to avoid repeated API calls for nearby coordinates. It checks the database for data within a 0.5-degree range, and if the data is older than 2 days, it deletes the old entry and fetches new data.

### Recommendations

    Based on soil and weather data, the application provides recommendations such as whether irrigation is needed based on predicted rainfall.

## Running the Application

### Start the Flask Server

    In the project directory, start the Flask development server by running:

    ```bash
    python app.py
    
    The API will be accessible at http://127.0.0.1:5000.


### Testing the API

    You can test the API by sending a GET request to the following endpoint:

    http://127.0.0.1:5000/api/analyze?lat={latitude}&lon={longitude}


    Example:
        http://127.0.0.1:5000/api/analyze?lat=42.3601&lon=-71.0589

