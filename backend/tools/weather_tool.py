from tool_server import tool
import requests

@tool(
    name="get_weather", 
    category="external_api", 
    tags=["weather", "api", "location"],
    requirements=["requests"]  # Required for Docker execution
)
def get_weather(city: str, country_code: str = "US") -> dict:
    """
    Get current weather for a city using Open-Meteo API (no API key required)
    
    Args:
        city: City name (e.g., "London", "New York")
        country_code: ISO 3166 country code (e.g., "US", "GB", "IN")
    
    Returns:
        dict: Weather information including temperature, description, humidity
    """
    try:
        # Step 1: Get coordinates for the city using Open-Meteo Geocoding API
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocode_params = {
            'name': city,
            'count': 1,
            'language': 'en',
            'format': 'json'
        }
        
        geo_response = requests.get(geocode_url, params=geocode_params, timeout=10)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data.get('results'):
            raise ValueError(f"City '{city}' not found")
        
        location = geo_data['results'][0]
        lat = location['latitude']
        lon = location['longitude']
        
        # Step 2: Get weather data using coordinates
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,pressure_msl',
            'temperature_unit': 'celsius',
            'wind_speed_unit': 'kmh'
        }
        
        weather_response = requests.get(weather_url, params=weather_params, timeout=10)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        
        # Map weather codes to descriptions
        weather_codes = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "foggy",
            48: "depositing rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            71: "slight snow",
            73: "moderate snow",
            75: "heavy snow",
            77: "snow grains",
            80: "slight rain showers",
            81: "moderate rain showers",
            82: "violent rain showers",
            85: "slight snow showers",
            86: "heavy snow showers",
            95: "thunderstorm",
            96: "thunderstorm with slight hail",
            99: "thunderstorm with heavy hail"
        }
        
        current = weather_data['current']
        weather_code = current.get('weather_code', 0)
        
        return {
            "city": location['name'],
            "country": location.get('country_code', country_code),
            "latitude": lat,
            "longitude": lon,
            "temperature": current['temperature_2m'],
            "humidity": current['relative_humidity_2m'],
            "description": weather_codes.get(weather_code, "unknown"),
            "wind_speed": current['wind_speed_10m'],
            "pressure": current['pressure_msl'],
            "weather_code": weather_code,
            "api": "Open-Meteo (free, no API key required)"
        }
    
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch weather data: {str(e)}")
    except KeyError as e:
        raise ValueError(f"Unexpected API response format: {str(e)}")
    except IndexError:
        raise ValueError(f"City '{city}' not found")


@tool(
    name="get_weather_forecast", 
    category="external_api",
    tags=["weather", "api", "forecast"],
    requirements=["requests"]
)
def get_weather_forecast(city: str, days: int = 3, country_code: str = "US") -> dict:
    """
    Get weather forecast for upcoming days using Open-Meteo API (no API key required)
    
    Args:
        city: City name
        days: Number of days (1-7, max 7 for free tier)
        country_code: ISO 3166 country code
    
    Returns:
        dict: Forecast data with daily predictions
    """
    try:
        # Limit days to 7 (Open-Meteo free tier limit)
        days = min(days, 7)
        
        # Step 1: Get coordinates for the city
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocode_params = {
            'name': city,
            'count': 1,
            'language': 'en',
            'format': 'json'
        }
        
        geo_response = requests.get(geocode_url, params=geocode_params, timeout=10)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data.get('results'):
            raise ValueError(f"City '{city}' not found")
        
        location = geo_data['results'][0]
        lat = location['latitude']
        lon = location['longitude']
        
        # Step 2: Get forecast data
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        forecast_params = {
            'latitude': lat,
            'longitude': lon,
            'daily': 'temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum',
            'temperature_unit': 'celsius',
            'forecast_days': days
        }
        
        forecast_response = requests.get(forecast_url, params=forecast_params, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        # Map weather codes to descriptions
        weather_codes = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "depositing rime fog",
            51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
            61: "slight rain", 63: "moderate rain", 65: "heavy rain",
            71: "slight snow", 73: "moderate snow", 75: "heavy snow",
            80: "rain showers", 81: "moderate rain showers", 82: "violent rain showers",
            95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail"
        }
        
        # Build forecast list
        daily = forecast_data['daily']
        forecast = []
        
        for i in range(len(daily['time'])):
            forecast.append({
                "date": daily['time'][i],
                "temp_max": daily['temperature_2m_max'][i],
                "temp_min": daily['temperature_2m_min'][i],
                "description": weather_codes.get(daily['weather_code'][i], "unknown"),
                "precipitation": daily['precipitation_sum'][i],
                "weather_code": daily['weather_code'][i]
            })
        
        return {
            "city": location['name'],
            "country": location.get('country_code', country_code),
            "latitude": lat,
            "longitude": lon,
            "forecast": forecast,
            "api": "Open-Meteo (free, no API key required)"
        }
    
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch forecast data: {str(e)}")
    except KeyError as e:
        raise ValueError(f"Unexpected API response format: {str(e)}")
    except IndexError:
        raise ValueError(f"City '{city}' not found")