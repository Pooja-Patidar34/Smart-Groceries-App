from rest_framework.views import exception_handler
import math


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        # Rename the default "detail" field to "error" and add "ok": False
        detail = response.data.get('detail')
        if detail:
            response.data = {
                'ok': False,
                'error': detail
            }
        else:
            response.data['ok'] = False

    return response



def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in KM
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat/2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lon/2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# Example coordinates
# mumbai = (19.0760, 72.8777)
# delhi = (28.7041, 77.1025)

# distance_km = haversine(*mumbai, *delhi)
# print(f"Distance: {distance_km:.2f} km")
