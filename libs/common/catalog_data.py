"""Genre templates for the fictional music catalog.

All artists/albums/tracks are generated from these templates — nothing real,
so no licensing questions. Kept as data (not code) so students can extend it.
"""

GENRES: dict[str, dict] = {
    "Jazz": {
        "artist_patterns": ["The {adj} {noun} Trio", "{first} {last} Quartet", "{first} {last}"],
        "album_patterns": ["Midnight {noun}", "Blue {noun}", "{noun} in {key}"],
        "price_mu": 2800, "era": (1955, 2024),
    },
    "Rock": {
        "artist_patterns": ["The {adj} {plural}", "{noun} Machine", "{adj} {noun}"],
        "album_patterns": ["{noun} and {noun2}", "Electric {noun}", "The {adj} Sessions"],
        "price_mu": 2400, "era": (1965, 2025),
    },
    "Electronic": {
        "artist_patterns": ["{prefix}{noun}", "DJ {adj}", "{noun}wave"],
        "album_patterns": ["{noun}.exe", "Neon {noun}", "{adj} Frequencies"],
        "price_mu": 2200, "era": (1988, 2026),
    },
    "Hip-Hop": {
        "artist_patterns": ["{adj} {first}", "MC {noun}", "{first} {last}"],
        "album_patterns": ["{noun} Chronicles", "State of {noun}", "{adj} Theory"],
        "price_mu": 2300, "era": (1985, 2026),
    },
    "Classical": {
        "artist_patterns": ["{city} {ensemble}", "{first} {last}"],
        "album_patterns": ["{noun} Variations", "Symphonies Nos. {n1} & {n2}", "{key} Concertos"],
        "price_mu": 3200, "era": (1960, 2024),
    },
    "Folk": {
        "artist_patterns": ["{first} {last}", "The {noun} Family", "{first} & the {plural}"],
        "album_patterns": ["Songs from the {noun}", "{adj} River", "Under the {noun}"],
        "price_mu": 2100, "era": (1962, 2025),
    },
    "Blues": {
        "artist_patterns": ["{adj} {first} {last}", "{first} '{nick}' {last}"],
        "album_patterns": ["{noun} Blues", "Down at the {noun}", "{adj} Morning"],
        "price_mu": 2500, "era": (1958, 2023),
    },
    "Reggae": {
        "artist_patterns": ["{first} {last}", "The {adj} {plural}"],
        "album_patterns": ["{noun} Vibration", "Island {noun}", "{adj} Roots"],
        "price_mu": 2200, "era": (1970, 2024),
    },
    "Country": {
        "artist_patterns": ["{first} {last}", "The {noun} Brothers"],
        "album_patterns": ["{noun} Road", "{adj} Hearts", "Back to {noun}"],
        "price_mu": 2000, "era": (1968, 2026),
    },
    "Metal": {
        "artist_patterns": ["{noun}forge", "{adj} {noun}", "{noun} of {noun2}"],
        "album_patterns": ["{noun} Eternal", "Rise of the {noun}", "{adj} Dominion"],
        "price_mu": 2600, "era": (1980, 2026),
    },
    "Pop": {
        "artist_patterns": ["{first}", "{first} {last}", "The {plural}"],
        "album_patterns": ["{adj} Hearts", "{noun}!", "Forever {noun}"],
        "price_mu": 1900, "era": (1982, 2026),
    },
    "Soul": {
        "artist_patterns": ["{first} {last}", "The {adj} {plural}"],
        "album_patterns": ["{noun} & Soul", "{adj} Nights", "Velvet {noun}"],
        "price_mu": 2400, "era": (1963, 2024),
    },
}

WORDS = {
    "adj": ["Velvet", "Crimson", "Golden", "Silent", "Electric", "Wandering", "Midnight",
            "Broken", "Rising", "Hollow", "Lucky", "Restless", "Neon", "Dusty", "Wild"],
    "noun": ["Sparrow", "Harbor", "Ember", "Meridian", "Canyon", "Lantern", "Echo",
             "Tempest", "Orchid", "Summit", "Drifter", "Signal", "Aurora", "Cinder", "Atlas"],
    "noun2": ["Thunder", "Ash", "Glass", "Iron", "Smoke", "Salt", "Stone", "Wire"],
    "plural": ["Sparrows", "Drifters", "Lanterns", "Echoes", "Tides", "Shadows",
               "Ramblers", "Satellites", "Wanderers", "Embers"],
    "first": ["Marlon", "Etta", "Silas", "Wren", "Cassius", "Odessa", "Rufus", "Imara",
              "Dexter", "Lorena", "Amos", "Celia", "Barnaby", "Nadia", "Otis", "Vera"],
    "last": ["Calloway", "Mercer", "Vance", "Okafor", "Delacroix", "Hargrove", "Whitfield",
             "Moreno", "Castellan", "Byrd", "Slater", "Kowalski", "Renaud", "Ashby"],
    "nick": ["Hollow", "Smokes", "Lightning", "Preacher", "Dusty", "Sugar"],
    "prefix": ["Syn", "Volt", "Neo", "Poly", "Chrome", "Flux"],
    "city": ["Meridian", "Halvard", "Ostrava", "Caldera", "Norwich", "Aster"],
    "ensemble": ["Philharmonic", "Chamber Orchestra", "Sinfonietta", "String Ensemble"],
    "key": ["A Minor", "E Flat", "G Major", "D Minor", "B Flat"],
    "track_noun": ["Rain", "Letter", "Highway", "Mirror", "Garden", "Clock", "Window",
                   "Bridge", "Feather", "Storm", "Candle", "Shoreline", "Whisper", "Engine"],
    "track_verb": ["Waiting", "Falling", "Running", "Dreaming", "Burning", "Calling",
                   "Breathing", "Turning", "Fading", "Shining"],
}

FORMAT_MULTIPLIER = {"vinyl": 1.45, "cd": 1.0, "digital": 0.55}
