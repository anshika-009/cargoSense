"""
CargoSense | geo_utils.py
Purpose: geocode a destination city, measure geodesic distance from Delhi and map the country to
a training Market value.
Input: city and optional state; coordinates as (latitude, longitude).
Output: (latitude, longitude, country_code), distance in km, Market string.
Notes: Nominatim is free but rate limited and needs a user agent, so results are cached in memory.
A failed lookup raises GeocodeError; nothing is guessed. Market has almost no effect on the model
(late rate 0.543 to 0.554 across markets) and is never shown in the UI. It is kept because the
model was trained with it; every Indian destination maps to Pacific Asia.
Used by: the API.
"""
from geopy.distance import geodesic
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim

ORIGIN_COORDS = (28.7041, 77.1025)
USER_AGENT = "cargosense-supply-chain-demo"
TIMEOUT_SECONDS = 6
DEFAULT_MARKET = "Pacific Asia"
MARKET_BY_COUNTRY = {
    "in": "Pacific Asia", "cn": "Pacific Asia", "jp": "Pacific Asia", "kr": "Pacific Asia",
    "sg": "Pacific Asia", "th": "Pacific Asia", "id": "Pacific Asia", "au": "Pacific Asia",
    "us": "USCA", "ca": "USCA",
    "gb": "Europe", "de": "Europe", "fr": "Europe", "es": "Europe", "it": "Europe", "nl": "Europe",
    "br": "LATAM", "mx": "LATAM", "ar": "LATAM", "co": "LATAM", "cl": "LATAM", "pe": "LATAM",
    "za": "Africa", "ng": "Africa", "ke": "Africa", "eg": "Africa", "ma": "Africa",
}
_CACHE = {}


class GeocodeError(Exception):
    pass


def clear_cache():
    _CACHE.clear()


def make_geocoder():
    return Nominatim(user_agent=USER_AGENT, timeout=TIMEOUT_SECONDS)


def geocode_destination(city, state=None, geocoder=None):
    key = (city.strip().lower(), (state or "").strip().lower())
    if key in _CACHE:
        return _CACHE[key]
    query = ", ".join(part for part in (city.strip(), (state or "").strip(), "India") if part)
    try:
        location = (geocoder or make_geocoder()).geocode(query, addressdetails=True, country_codes="in")
    except (GeopyError, OSError) as error:
        raise GeocodeError(f"geocoding service failed: {error.__class__.__name__}") from error
    if location is None:
        raise GeocodeError(f"could not locate '{query}'")
    country = location.raw.get("address", {}).get("country_code", "in")
    result = (location.latitude, location.longitude, country)
    _CACHE[key] = result
    return result


def distance_km(origin, destination):
    return round(geodesic(origin, destination).km, 1)


def market_for_country(country_code):
    return MARKET_BY_COUNTRY.get((country_code or "").lower(), DEFAULT_MARKET)
