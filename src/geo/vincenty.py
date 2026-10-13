"""Geodesic distance and bounding box calculations using the Vincenty formulas on WGS-84.

This module provides high-accuracy ellipsoidal geodesy routines:
- vincenty_direct: Computes destination coordinates given origin, bearing, and distance.
- vincenty_km: Computes ellipsoidal distance between two coordinates.
- bounding_box_vincenty: Computes the north/south/east/west bounding box rectangle.
"""

import math
from typing import Any, Dict, Tuple

# WGS-84 reference ellipsoid parameters
SEMI_MAJOR_AXIS_A: float = 6378137.0  # in meters
FLATTENING_F: float = 1 / 298.257223563
SEMI_MINOR_AXIS_B: float = (1 - FLATTENING_F) * SEMI_MAJOR_AXIS_A


def vincenty_direct(
    lat: float,
    lon: float,
    bearing_deg: float,
    distance_km: float,
) -> Tuple[float, float]:
    """Calculate destination coordinates from a point, bearing, and distance on the WGS-84 ellipsoid.

    Args:
        lat: Latitude of origin point in degrees.
        lon: Longitude of origin point in degrees.
        bearing_deg: Initial bearing in degrees (clockwise from north: 0=N, 90=E, 180=S, 270=W).
        distance_km: Distance along the geodesic in kilometers.

    Returns:
        A tuple of (destination_latitude, destination_longitude) in degrees.
    """
    a = SEMI_MAJOR_AXIS_A
    f = FLATTENING_F
    b = SEMI_MINOR_AXIS_B

    alpha1 = math.radians(bearing_deg)
    s = distance_km * 1000.0  # convert to meters

    phi1 = math.radians(lat)
    u1 = math.atan((1 - f) * math.tan(phi1))

    sin_u1, cos_u1 = math.sin(u1), math.cos(u1)
    sin_alpha1, cos_alpha1 = math.sin(alpha1), math.cos(alpha1)

    sin_alpha = cos_u1 * sin_alpha1
    cos2_alpha = 1.0 - sin_alpha**2

    u2 = cos2_alpha * (a * a - b * b) / (b * b)
    cap_a = 1.0 + u2 / 16384.0 * (4096.0 + u2 * (-768.0 + u2 * (320.0 - 175.0 * u2)))
    cap_b = u2 / 1024.0 * (256.0 + u2 * (-128.0 + u2 * (74.0 - 47.0 * u2)))

    sigma = s / (b * cap_a)
    sigma_prev = 0.0

    while abs(sigma - sigma_prev) > 1e-12:
        cos2_sigma_m = math.cos(
            2.0 * math.atan2(sin_u1, cos_u1 * cos_alpha1) + sigma
        )
        sin_sigma = math.sin(sigma)
        cos_sigma = math.cos(sigma)

        delta_sigma = cap_b * sin_sigma * (
            cos2_sigma_m
            + cap_b
            / 4.0
            * (
                cos_sigma * (-1.0 + 2.0 * cos2_sigma_m**2)
                - cap_b
                / 6.0
                * cos2_sigma_m
                * (-3.0 + 4.0 * sin_sigma**2)
                * (-3.0 + 4.0 * cos2_sigma_m**2)
            )
        )
        sigma_prev = sigma
        sigma = s / (b * cap_a) + delta_sigma

    tmp = sin_u1 * sin_sigma - cos_u1 * cos_sigma * cos_alpha1
    phi2 = math.atan2(
        sin_u1 * cos_sigma + cos_u1 * sin_sigma * cos_alpha1,
        (1.0 - f) * math.sqrt(sin_alpha**2 + tmp**2),
    )

    lamb = math.atan2(
        sin_sigma * sin_alpha1,
        cos_u1 * cos_sigma - sin_u1 * sin_sigma * cos_alpha1,
    )

    c = f / 16.0 * cos2_alpha * (4.0 + f * (4.0 - 3.0 * cos2_alpha))
    cap_l = lamb - (1.0 - c) * f * sin_alpha * (
        sigma
        + c
        * sin_sigma
        * (cos2_sigma_m + c * cos_sigma * (-1.0 + 2.0 * cos2_sigma_m**2))
    )

    lon2 = math.radians(lon) + cap_l

    return math.degrees(phi2), math.degrees(lon2)


def bounding_box_vincenty(
    lat: float, lon: float, radius_km: float
) -> Dict[str, Dict[str, float]]:
    """Compute the rectangular bounding box enclosing a circle of radius_km on WGS-84.

    Args:
        lat: Center point latitude in degrees.
        lon: Center point longitude in degrees.
        radius_km: Radius in kilometers.

    Returns:
        Dictionary formatted for Google Places API locationRestriction:
        {
            "low": {"latitude": min_lat, "longitude": min_lon},
            "high": {"latitude": max_lat, "longitude": max_lon}
        }
    """
    north = vincenty_direct(lat, lon, 0, radius_km)
    south = vincenty_direct(lat, lon, 180, radius_km)
    east = vincenty_direct(lat, lon, 90, radius_km)
    west = vincenty_direct(lat, lon, 270, radius_km)

    return {
        "low": {
            "latitude": south[0],
            "longitude": west[1],
        },
        "high": {
            "latitude": north[0],
            "longitude": east[1],
        },
    }


def vincenty_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the geodesic distance between two points in kilometers using Vincenty inverse problem.

    Args:
        lat1: Latitude of point 1 in degrees.
        lon1: Longitude of point 1 in degrees.
        lat2: Latitude of point 2 in degrees.
        lon2: Longitude of point 2 in degrees.

    Returns:
        Distance in kilometers rounded to 4 decimal places.
    """
    a = SEMI_MAJOR_AXIS_A
    f = FLATTENING_F
    b = SEMI_MINOR_AXIS_B

    phi1, phi2 = map(math.radians, (lat1, lat2))
    u1 = math.atan((1.0 - f) * math.tan(phi1))
    u2 = math.atan((1.0 - f) * math.tan(phi2))
    delta_lon = math.radians(lon2 - lon1)

    sin_u1, cos_u1 = math.sin(u1), math.cos(u1)
    sin_u2, cos_u2 = math.sin(u2), math.cos(u2)

    lamb = delta_lon
    for _ in range(1000):
        sin_l, cos_l = math.sin(lamb), math.cos(lamb)
        sin_sigma = math.sqrt(
            (cos_u2 * sin_l) ** 2
            + (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_l) ** 2
        )
        if sin_sigma == 0:
            return 0.0

        cos_sigma = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_l
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_u1 * cos_u2 * sin_l / sin_sigma
        cos2_alpha = 1.0 - sin_alpha**2

        cos2_sigma_m = (
            cos_sigma - 2.0 * sin_u1 * sin_u2 / cos2_alpha
            if cos2_alpha != 0
            else 0.0
        )

        c = f / 16.0 * cos2_alpha * (4.0 + f * (4.0 - 3.0 * cos2_alpha))
        lamb_prev = lamb
        lamb = (
            delta_lon
            + (1.0 - c)
            * f
            * sin_alpha
            * (
                sigma
                + c
                * sin_sigma
                * (
                    cos2_sigma_m
                    + c * cos_sigma * (-1.0 + 2.0 * cos2_sigma_m**2)
                )
            )
        )

        if abs(lamb - lamb_prev) < 1e-12:
            break

    u2_val = cos2_alpha * (a**2 - b**2) / (b**2)
    cap_a = 1.0 + u2_val / 16384.0 * (
        4096.0 + u2_val * (-768.0 + u2_val * (320.0 - 175.0 * u2_val))
    )
    cap_b = u2_val / 1024.0 * (
        256.0 + u2_val * (-128.0 + u2_val * (74.0 - 47.0 * u2_val))
    )

    delta_sigma = (
        cap_b
        * sin_sigma
        * (
            cos2_sigma_m
            + cap_b
            / 4.0
            * (
                cos_sigma * (-1.0 + 2.0 * cos2_sigma_m**2)
                - cap_b
                / 6.0
                * cos2_sigma_m
                * (-3.0 + 4.0 * sin_sigma**2)
                * (-3.0 + 4.0 * cos2_sigma_m**2)
            )
        )
    )

    return round((b * cap_a * (sigma - delta_sigma)) / 1000.0, 4)
