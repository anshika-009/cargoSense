"""CargoSense | states_cities.py
Purpose: the 28 Indian states, their destination cities and coordinates, plus geodesic distance
from Delhi HQ. Holds no weather or risk values; those come from the API.
Used by: app.py.
"""

from geopy.distance import geodesic

ORIGIN_HUB = "Delhi Hub (North HQ)"
DELHI_HQ_COORDS = [77.1025, 28.7041]  # [lon, lat]

INDIA_STATES_CITIES = {
    "Andhra Pradesh": [
        {
            "city": "Visakhapatnam",
            "coords": [83.2185, 17.6868],
            "label_pos": [52, 4],
        },
        {
            "city": "Vijayawada",
            "coords": [80.6480, 16.5062],
            "label_pos": [48, 4],
        },
    ],
    "Arunachal Pradesh": [
        {
            "city": "Itanagar",
            "coords": [93.6053, 27.0844],
            "label_pos": [48, -6],
        },
    ],
    "Assam": [
        {
            "city": "Guwahati",
            "coords": [91.7362, 26.1445],
            "label_pos": [48, 2],
        },
        {
            "city": "Dibrugarh",
            "coords": [94.9120, 27.4728],
            "label_pos": [50, -4],
        },
    ],
    "Bihar": [
        {
            "city": "Patna",
            "coords": [85.1376, 25.5941],
            "label_pos": [42, -4],
        },
        {
            "city": "Gaya",
            "coords": [85.0002, 24.7914],
            "label_pos": [40, 4],
        },
    ],
    "Chhattisgarh": [
        {
            "city": "Raipur",
            "coords": [81.6296, 21.2514],
            "label_pos": [44, 2],
        },
        {
            "city": "Bhilai",
            "coords": [81.4285, 21.2094],
            "label_pos": [-46, 4],
        },
    ],
    "Goa": [
        {
            "city": "Panaji",
            "coords": [73.8278, 15.4909],
            "label_pos": [-46, 4],
        },
    ],
    "Gujarat": [
        {
            "city": "Ahmedabad",
            "coords": [72.5714, 23.0225],
            "label_pos": [-60, -4],
        },
        {
            "city": "Surat",
            "coords": [72.8311, 21.1702],
            "label_pos": [-46, 4],
        },
    ],
    "Haryana": [
        {
            "city": "Gurugram",
            "coords": [77.0266, 28.4595],
            "label_pos": [-56, 8],
        },
        {
            "city": "Faridabad",
            "coords": [77.3178, 28.4089],
            "label_pos": [48, 8],
        },
    ],
    "Himachal Pradesh": [
        {
            "city": "Shimla",
            "coords": [77.1734, 31.1048],
            "label_pos": [44, -6],
        },
    ],
    "Jharkhand": [
        {
            "city": "Ranchi",
            "coords": [85.3096, 23.3441],
            "label_pos": [44, 0],
        },
        {
            "city": "Jamshedpur",
            "coords": [86.2029, 22.8046],
            "label_pos": [54, 4],
        },
    ],
    "Karnataka": [
        {
            "city": "Bengaluru",
            "coords": [77.5946, 12.9716],
            "label_pos": [-66, 4],
        },
        {
            "city": "Mysuru",
            "coords": [76.6394, 12.2958],
            "label_pos": [-46, 4],
        },
    ],
    "Kerala": [
        {
            "city": "Kochi",
            "coords": [76.2673, 9.9312],
            "label_pos": [-42, 4],
        },
        {
            "city": "Thiruvananthapuram",
            "coords": [76.9366, 8.5241],
            "label_pos": [-76, 6],
        },
    ],
    "Madhya Pradesh": [
        {
            "city": "Bhopal",
            "coords": [77.4126, 23.2599],
            "label_pos": [42, -2],
        },
        {
            "city": "Indore",
            "coords": [75.8577, 22.7196],
            "label_pos": [-44, 4],
        },
    ],
    "Maharashtra": [
        {
            "city": "Mumbai",
            "coords": [72.8777, 19.0760],
            "label_pos": [-74, -8],
        },
        {
            "city": "Pune",
            "coords": [73.8567, 18.5204],
            "label_pos": [-42, 4],
        },
        {
            "city": "Nagpur",
            "coords": [79.0882, 21.1458],
            "label_pos": [46, 0],
        },
    ],
    "Manipur": [
        {
            "city": "Imphal",
            "coords": [93.9368, 24.8170],
            "label_pos": [44, 2],
        },
    ],
    "Meghalaya": [
        {
            "city": "Shillong",
            "coords": [91.8933, 25.5788],
            "label_pos": [48, -4],
        },
    ],
    "Mizoram": [
        {
            "city": "Aizawl",
            "coords": [92.7176, 23.7271],
            "label_pos": [44, 2],
        },
    ],
    "Nagaland": [
        {
            "city": "Kohima",
            "coords": [94.1086, 25.6751],
            "label_pos": [46, -2],
        },
    ],
    "Odisha": [
        {
            "city": "Bhubaneswar",
            "coords": [85.8245, 20.2961],
            "label_pos": [62, 0],
        },
        {
            "city": "Cuttack",
            "coords": [85.8830, 20.4625],
            "label_pos": [46, -6],
        },
    ],
    "Punjab": [
        {
            "city": "Ludhiana",
            "coords": [75.8573, 30.9010],
            "label_pos": [50, -4],
        },
        {
            "city": "Amritsar",
            "coords": [74.8723, 31.6340],
            "label_pos": [-48, -4],
        },
    ],
    "Rajasthan": [
        {
            "city": "Jaipur",
            "coords": [75.7873, 26.9124],
            "label_pos": [-50, -6],
        },
        {
            "city": "Udaipur",
            "coords": [73.7125, 24.5854],
            "label_pos": [-46, 4],
        },
    ],
    "Sikkim": [
        {
            "city": "Gangtok",
            "coords": [88.6065, 27.3389],
            "label_pos": [46, -4],
        },
    ],
    "Tamil Nadu": [
        {
            "city": "Chennai",
            "coords": [80.2707, 13.0827],
            "label_pos": [54, 4],
        },
        {
            "city": "Coimbatore",
            "coords": [76.9558, 11.0168],
            "label_pos": [-56, 4],
        },
    ],
    "Telangana": [
        {
            "city": "Hyderabad",
            "coords": [78.4867, 17.3850],
            "label_pos": [52, 2],
        },
    ],
    "Tripura": [
        {
            "city": "Agartala",
            "coords": [91.2868, 23.8315],
            "label_pos": [46, 2],
        },
    ],
    "Uttar Pradesh": [
        {
            "city": "Lucknow",
            "coords": [80.9462, 26.8467],
            "label_pos": [48, -2],
        },
        {
            "city": "Varanasi",
            "coords": [82.9739, 25.3176],
            "label_pos": [48, 2],
        },
    ],
    "Uttarakhand": [
        {
            "city": "Dehradun",
            "coords": [78.0322, 30.3165],
            "label_pos": [48, -4],
        },
    ],
    "West Bengal": [
        {
            "city": "Kolkata",
            "coords": [88.3639, 22.5726],
            "label_pos": [52, 0],
        },
        {
            "city": "Siliguri",
            "coords": [88.3953, 26.7271],
            "label_pos": [46, -4],
        },
    ],
}


def compute_distance_km(coords_a, coords_b):
    """Return geodesic distance in km between [lon, lat] pairs."""
    return round(geodesic((coords_a[1], coords_a[0]), (coords_b[1], coords_b[0])).km, 1)


def get_hub_record(state, city):
    """Return a normalized hub dictionary for the selected state and city."""
    city_list = INDIA_STATES_CITIES.get(state, [])
    selected = None
    for item in city_list:
        if item["city"] == city:
            selected = item
            break
    if selected is None and city_list:
        selected = city_list[0]
    if selected is None:
        return None

    record = dict(selected)
    record["state"] = state
    record["origin"] = ORIGIN_HUB
    record["dist"] = compute_distance_km(DELHI_HQ_COORDS, record["coords"])
    record.setdefault("label_pos", [0, -14])
    return record


def get_all_city_records():
    """Return a flat list of all state+city corridor records across all 28 states."""
    all_records = []
    for state_name in sorted(INDIA_STATES_CITIES.keys()):
        for item in INDIA_STATES_CITIES[state_name]:
            rec = get_hub_record(state_name, item["city"])
            if rec is not None:
                all_records.append(rec)
    return all_records