#!/usr/bin/env python3
"""
Weather MCP Tool - Provides weather information using WeatherAPI with httpx
"""

import asyncio
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json
from fastmcp import FastMCP

# Initialize FastMCP
mcp = FastMCP("Weather Tool")

# Configuration
WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY")
WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1"

if not WEATHERAPI_KEY:
    raise ValueError("WEATHERAPI_KEY environment variable is required")

class WeatherClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def get_current_weather(self, location: str, aqi: bool = False) -> Dict[str, Any]:
        """Get current weather data"""
        url = f"{WEATHERAPI_BASE_URL}/current.json"
        params = {
            "key": self.api_key,
            "q": location,
            "aqi": "yes" if aqi else "no"
        }
        
        response = await self.client.get(url, params=params)
        if response.status_code == 400:
            error_data = response.json()
            raise ValueError(error_data.get("error", {}).get("message", "Invalid location"))
        response.raise_for_status()
        return response.json()
    
    async def get_forecast(self, location: str, days: int = 3, aqi: bool = False, alerts: bool = False) -> Dict[str, Any]:
        """Get weather forecast"""
        url = f"{WEATHERAPI_BASE_URL}/forecast.json"
        params = {
            "key": self.api_key,
            "q": location,
            "days": min(days, 10),
            "aqi": "yes" if aqi else "no",
            "alerts": "yes" if alerts else "no"
        }
        
        response = await self.client.get(url, params=params)
        if response.status_code == 400:
            error_data = response.json()
            raise ValueError(error_data.get("error", {}).get("message", "Invalid location"))
        response.raise_for_status()
        return response.json()
    
    async def get_search_locations(self, query: str) -> List[Dict[str, Any]]:
        """Search for locations"""
        url = f"{WEATHERAPI_BASE_URL}/search.json"
        params = {
            "key": self.api_key,
            "q": query
        }
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_astronomy(self, location: str, date: str = None) -> Dict[str, Any]:
        """Get astronomy data (sun/moon info)"""
        url = f"{WEATHERAPI_BASE_URL}/astronomy.json"
        params = {
            "key": self.api_key,
            "q": location
        }
        if date:
            params["dt"] = date
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

def get_location_string(location_data: Dict[str, Any]) -> str:
    """Get a clean location string"""
    name = location_data["name"]
    region = location_data.get("region", "")
    country = location_data["country"]
    
    if region and region != name:
        return f"{name}, {region}, {country}"
    return f"{name}, {country}"

def format_temperature(temp_c: float, temp_f: float, celsius_first: bool = True) -> str:
    """Format temperature with both units"""
    if celsius_first:
        return f"{temp_c}°C ({temp_f}°F)"
    return f"{temp_f}°F ({temp_c}°C)"

@mcp.tool()
async def get_current_weather(location: str) -> str:
    """
    Get current weather conditions for a specific location.
    Returns essential current weather information including temperature, conditions, and key metrics.
    
    Args:
        location: Location to get weather for (city name, coordinates, airport code, etc.)
    
    Returns:
        Current weather conditions
    """
    try:
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_current_weather(location)
            
            loc = data["location"]
            current = data["current"]
            condition = current["condition"]
            
            location_str = get_location_string(loc)
            temp_str = format_temperature(current["temp_c"], current["temp_f"])
            feels_like_str = format_temperature(current["feelslike_c"], current["feelslike_f"])
            
            return f"""Current weather in {location_str}:

{condition["text"]} • {temp_str}
Feels like {feels_like_str}

Humidity: {current["humidity"]}% • Wind: {current["wind_kph"]} kph {current["wind_dir"]}
Pressure: {current["pressure_mb"]} mb • Visibility: {current["vis_km"]} km
UV Index: {current["uv"]}

Last updated: {current["last_updated"]}"""
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Weather service error: {str(e)}"

@mcp.tool()
async def get_temperature(location: str) -> str:
    """
    Get just the current temperature for a location.
    Focused response for temperature-specific queries.
    
    Args:
        location: Location to get temperature for
    
    Returns:
        Current temperature information
    """
    try:
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_current_weather(location)
            
            loc = data["location"]
            current = data["current"]
            
            location_str = get_location_string(loc)
            temp_str = format_temperature(current["temp_c"], current["temp_f"])
            feels_like_str = format_temperature(current["feelslike_c"], current["feelslike_f"])
            
            return f"Temperature in {location_str}: {temp_str} (feels like {feels_like_str})"
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Weather service error: {str(e)}"

@mcp.tool()
async def will_it_rain(location: str, days: int = 1) -> str:
    """
    Check if it will rain in a specific location.
    Focused on precipitation forecast and rain probability.
    
    Args:
        location: Location to check for rain
        days: Number of days to check (1-3)
    
    Returns:
        Rain forecast and probability
    """
    try:
        days = min(max(days, 1), 3)  # Limit to 1-3 days for focused response
        
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_forecast(location, days=days)
            
            location_str = get_location_string(data["location"])
            forecast_days = data["forecast"]["forecastday"]
            
            if days == 1:
                day_data = forecast_days[0]
                day_info = day_data["day"]
                rain_chance = day_info["daily_chance_of_rain"]
                max_precip = day_info["totalprecip_mm"]
                condition = day_info["condition"]["text"]
                
                if rain_chance == 0:
                    return f"No rain expected in {location_str} today. Conditions: {condition}"
                elif rain_chance <= 30:
                    return f"Low chance of rain in {location_str} today ({rain_chance}%). Conditions: {condition}"
                elif rain_chance <= 60:
                    return f"Moderate chance of rain in {location_str} today ({rain_chance}%). Expected: {max_precip}mm. Conditions: {condition}"
                else:
                    return f"High chance of rain in {location_str} today ({rain_chance}%). Expected: {max_precip}mm. Conditions: {condition}"
            else:
                result = f"Rain forecast for {location_str}:\n"
                for day_data in forecast_days:
                    date = datetime.strptime(day_data["date"], "%Y-%m-%d")
                    day_name = "Today" if date.date() == datetime.now().date() else date.strftime("%A")
                    
                    day_info = day_data["day"]
                    rain_chance = day_info["daily_chance_of_rain"]
                    max_precip = day_info["totalprecip_mm"]
                    
                    if rain_chance == 0:
                        result += f"\n{day_name}: No rain expected"
                    else:
                        result += f"\n{day_name}: {rain_chance}% chance, up to {max_precip}mm"
                
                return result
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Weather service error: {str(e)}"

@mcp.tool()
async def get_weather_forecast(location: str, days: int = 3) -> str:
    """
    Get weather forecast for multiple days.
    Provides comprehensive forecast information.
    
    Args:
        location: Location to get forecast for
        days: Number of days to forecast (1-7)
    
    Returns:
        Multi-day weather forecast
    """
    try:
        days = min(max(days, 1), 7)
        
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_forecast(location, days=days)
            
            location_str = get_location_string(data["location"])
            forecast_days = data["forecast"]["forecastday"]
            
            result = f"{days}-day forecast for {location_str}:\n"
            
            for day_data in forecast_days:
                date = datetime.strptime(day_data["date"], "%Y-%m-%d")
                day_name = "Today" if date.date() == datetime.now().date() else date.strftime("%A %b %d")
                
                day_info = day_data["day"]
                condition = day_info["condition"]["text"]
                high_temp = format_temperature(day_info["maxtemp_c"], day_info["maxtemp_f"])
                low_temp = format_temperature(day_info["mintemp_c"], day_info["mintemp_f"])
                rain_chance = day_info["daily_chance_of_rain"]
                
                result += f"\n{day_name}: {condition}"
                result += f"\n  High: {high_temp} • Low: {low_temp}"
                if rain_chance > 0:
                    result += f" • Rain: {rain_chance}%"
                result += "\n"
            
            return result.strip()
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Weather service error: {str(e)}"

@mcp.tool()
async def compare_weather(locations: List[str]) -> str:
    """
    Compare current weather between multiple locations.
    Provides side-by-side weather comparison.
    
    Args:
        locations: List of locations to compare (2-5 locations)
    
    Returns:
        Weather comparison between locations
    """
    if len(locations) < 2:
        return "Need at least 2 locations to compare"
    if len(locations) > 5:
        return "Maximum 5 locations allowed for comparison"
    
    try:
        results = []
        
        async with WeatherClient(WEATHERAPI_KEY) as client:
            # Get weather data for all locations concurrently
            tasks = [client.get_current_weather(loc) for loc in locations]
            weather_data_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, (location, weather_data) in enumerate(zip(locations, weather_data_list)):
                if isinstance(weather_data, Exception):
                    results.append({"location": location, "error": str(weather_data)})
                else:
                    loc = weather_data["location"]
                    current = weather_data["current"]
                    
                    results.append({
                        "location": get_location_string(loc),
                        "temp_c": current["temp_c"],
                        "temp_f": current["temp_f"],
                        "condition": current["condition"]["text"],
                        "humidity": current["humidity"],
                        "wind_kph": current["wind_kph"]
                    })
        
        # Format comparison
        comparison = "Weather comparison:\n"
        for result in results:
            if "error" in result:
                comparison += f"\n❌ {result['location']}: {result['error']}"
            else:
                temp_str = format_temperature(result["temp_c"], result["temp_f"])
                comparison += f"\n📍 {result['location']}"
                comparison += f"\n   {result['condition']} • {temp_str}"
                comparison += f"\n   Humidity: {result['humidity']}% • Wind: {result['wind_kph']} kph\n"
        
        return comparison.strip()
    
    except Exception as e:
        return f"Comparison error: {str(e)}"

@mcp.tool()
async def get_air_quality(location: str) -> str:
    """
    Get air quality information for a location.
    Focused response for air quality queries.
    
    Args:
        location: Location to get air quality for
    
    Returns:
        Air quality index and pollutant levels
    """
    try:
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_current_weather(location, aqi=True)
            
            if "air_quality" not in data:
                return f"Air quality data not available for {get_location_string(data['location'])}"
            
            location_str = get_location_string(data["location"])
            aqi = data["air_quality"]
            
            result = f"Air quality in {location_str}:\n"
            result += f"\nPM2.5: {aqi.get('pm2_5', 'N/A')} μg/m³"
            result += f"\nPM10: {aqi.get('pm10', 'N/A')} μg/m³"
            result += f"\nCarbon Monoxide: {aqi.get('co', 'N/A')} μg/m³"
            result += f"\nNitrogen Dioxide: {aqi.get('no2', 'N/A')} μg/m³"
            result += f"\nOzone: {aqi.get('o3', 'N/A')} μg/m³"
            
            # Add basic interpretation
            pm25 = aqi.get('pm2_5', 0)
            if pm25 <= 12:
                result += f"\n\nAir quality: Good"
            elif pm25 <= 35:
                result += f"\n\nAir quality: Moderate"
            elif pm25 <= 55:
                result += f"\n\nAir quality: Unhealthy for sensitive groups"
            else:
                result += f"\n\nAir quality: Unhealthy"
            
            return result
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Air quality service error: {str(e)}"

@mcp.tool()
async def get_sunrise_sunset(location: str, date: str = None) -> str:
    """
    Get sunrise and sunset times for a location.
    Focused response for sun timing queries.
    
    Args:
        location: Location to get sun times for
        date: Date in YYYY-MM-DD format (optional, defaults to today)
    
    Returns:
        Sunrise and sunset times
    """
    try:
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_astronomy(location, date)
            
            location_str = get_location_string(data["location"])
            astro = data["astronomy"]["astro"]
            
            result = f"Sun times for {location_str}"
            if date:
                result += f" on {date}"
            result += f":\n\nSunrise: {astro['sunrise']}\nSunset: {astro['sunset']}"
            
            # Calculate daylight hours
            try:
                sunrise_time = datetime.strptime(astro['sunrise'], "%I:%M %p")
                sunset_time = datetime.strptime(astro['sunset'], "%I:%M %p")
                daylight_hours = sunset_time - sunrise_time
                result += f"\nDaylight hours: {daylight_hours}"
            except:
                pass  # Skip if time parsing fails
            
            return result
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Astronomy service error: {str(e)}"

@mcp.tool()
async def search_locations(query: str) -> str:
    """
    Search for locations to find exact names.
    Helpful when location queries fail or need clarification.
    
    Args:
        query: Search term for location
    
    Returns:
        List of matching locations
    """
    try:
        async with WeatherClient(WEATHERAPI_KEY) as client:
            locations = await client.get_search_locations(query)
            
            if not locations:
                return f"No locations found matching '{query}'"
            
            result = f"Locations matching '{query}':\n"
            for i, loc in enumerate(locations[:8], 1):  # Limit to 8 results
                location_str = get_location_string(loc)
                result += f"\n{i}. {location_str}"
                if loc.get("lat") and loc.get("lon"):
                    result += f" ({loc['lat']:.2f}, {loc['lon']:.2f})"
            
            return result
    
    except Exception as e:
        return f"Search error: {str(e)}"

@mcp.tool()
async def is_it_sunny(location: str) -> str:
    """
    Check if it's sunny in a specific location.
    Simple yes/no response with current conditions.
    
    Args:
        location: Location to check
    
    Returns:
        Whether it's sunny and current conditions
    """
    try:
        async with WeatherClient(WEATHERAPI_KEY) as client:
            data = await client.get_current_weather(location)
            
            location_str = get_location_string(data["location"])
            condition = data["current"]["condition"]["text"].lower()
            
            sunny_conditions = ["sunny", "clear", "partly cloudy"]
            is_sunny = any(sunny_word in condition for sunny_word in sunny_conditions)
            
            if is_sunny:
                return f"Yes, it's {data['current']['condition']['text'].lower()} in {location_str}"
            else:
                return f"No, it's {data['current']['condition']['text'].lower()} in {location_str}"
    
    except ValueError as e:
        return f"Location not found: {str(e)}"
    except Exception as e:
        return f"Weather service error: {str(e)}"

@mcp.resource("weather://help")
async def weather_help_resource() -> str:
    """Resource containing weather tool usage help"""
    return """
Weather Tool Usage Guide:

🌤️ Current Weather:
- get_current_weather("London") - Full current conditions
- get_temperature("New York") - Just temperature
- is_it_sunny("Tokyo") - Simple sunny/not sunny check

🌧️ Rain & Precipitation:
- will_it_rain("Paris") - Rain forecast for today
- will_it_rain("Miami", 3) - Rain forecast for 3 days

📅 Forecasts:
- get_weather_forecast("Sydney", 5) - 5-day forecast
- get_weather_forecast("Berlin") - 3-day forecast (default)

🌍 Comparisons:
- compare_weather(["London", "Paris", "Berlin"]) - Side-by-side comparison

🌬️ Air Quality:
- get_air_quality("Beijing") - Pollution levels and AQI

☀️ Sun Times:
- get_sunrise_sunset("Rome") - Today's sunrise/sunset
- get_sunrise_sunset("Cairo", "2024-12-25") - Specific date

🔍 Location Help:
- search_locations("Springfield") - Find exact location names

Location Formats Supported:
- City names: "London", "New York"
- City, State: "Austin, TX"
- Coordinates: "40.7128,-74.0060"
- Airport codes: "JFK", "LHR"
- Auto location: "auto:ip"
"""

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()