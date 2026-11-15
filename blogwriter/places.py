"""Where places are: longitude and latitude for the globe technique (video/src/viz/globe.jsx). A table of big cities and
the cloud regions people name in system-design lessons; a place the table does not know is left out of the picture
(never guessed)."""
from typing import List, Optional

# name -> (longitude, latitude)
PLACES = {
    "new york": (-74.0, 40.7), "san francisco": (-122.4, 37.8), "los angeles": (-118.2, 34.1), "chicago": (-87.6, 41.9),
    "seattle": (-122.3, 47.6), "dallas": (-96.8, 32.8), "miami": (-80.2, 25.8), "toronto": (-79.4, 43.7),
    "mexico city": (-99.1, 19.4), "sao paulo": (-46.6, -23.6), "buenos aires": (-58.4, -34.6), "bogota": (-74.1, 4.7),
    "london": (-0.1, 51.5), "paris": (2.35, 48.9), "berlin": (13.4, 52.5), "frankfurt": (8.7, 50.1), "dublin": (-6.3, 53.3),
    "madrid": (-3.7, 40.4), "rome": (12.5, 41.9), "amsterdam": (4.9, 52.4), "stockholm": (18.1, 59.3), "moscow": (37.6, 55.8),
    "istanbul": (29.0, 41.0), "cairo": (31.2, 30.0), "lagos": (3.4, 6.5), "nairobi": (36.8, -1.3), "johannesburg": (28.0, -26.2),
    "cape town": (18.4, -33.9), "dubai": (55.3, 25.3), "riyadh": (46.7, 24.7), "tel aviv": (34.8, 32.1), "tehran": (51.4, 35.7),
    "mumbai": (72.9, 19.1), "delhi": (77.2, 28.6), "bangalore": (77.6, 13.0), "bengaluru": (77.6, 13.0), "hyderabad": (78.5, 17.4),
    "chennai": (80.3, 13.1), "kolkata": (88.4, 22.6), "karachi": (67.0, 24.9), "dhaka": (90.4, 23.8), "singapore": (103.8, 1.35),
    "jakarta": (106.8, -6.2), "bangkok": (100.5, 13.8), "hong kong": (114.2, 22.3), "shanghai": (121.5, 31.2), "beijing": (116.4, 39.9),
    "seoul": (127.0, 37.6), "tokyo": (139.7, 35.7), "osaka": (135.5, 34.7), "manila": (121.0, 14.6), "sydney": (151.2, -33.9),
    "melbourne": (145.0, -37.8), "auckland": (174.8, -36.8), "perth": (115.9, -32.0),
    # cloud regions, by the names the lessons use
    "us-east": (-77.5, 39.0), "us east": (-77.5, 39.0), "virginia": (-77.5, 39.0), "us-west": (-121.9, 45.8), "us west": (-121.9, 45.8),
    "oregon": (-121.9, 45.8), "eu-west": (-6.3, 53.3), "eu west": (-6.3, 53.3), "ireland": (-6.3, 53.3), "eu-central": (8.7, 50.1),
    "ap-south": (72.9, 19.1), "ap south": (72.9, 19.1), "ap-southeast": (103.8, 1.35), "ap southeast": (103.8, 1.35),
    "ap-northeast": (139.7, 35.7), "ap northeast": (139.7, 35.7), "sa-east": (-46.6, -23.6),
}


def lookup(name: str) -> Optional[tuple]:
    """(longitude, latitude) of a place by name (case, accents and a trailing region word ignored), or None."""
    key = " ".join(str(name).lower().replace("ã", "a").replace("é", "e").replace("í", "i").split())
    key = key.replace(" region", "").replace(" data center", "").replace(" datacenter", "")
    return PLACES.get(key)


def resolve(names: List[str]) -> List[list]:
    """[[longitude, latitude, name], ...] for the places that are known, each once, in order."""
    out, seen = [], set()
    for n in names:
        at = lookup(n)
        if at and at not in seen:
            seen.add(at)
            out.append([at[0], at[1], str(n)])
    return out
