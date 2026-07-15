"""Static ETS2 game data used for map-unlock features.

City tokens that have a truck dealer / recruitment agency (base game + all
DLC map expansions). Derived from the open-source "unlocked-profile-ets2" mod
by thedeedawg. Used to only unlock dealers/agencies in cities that actually
have them; the concrete list of cities present in a given save is harvested
from that save's own company units, so unknown-DLC tokens are never written.
"""

DEALER_CITIES = frozenset("""
aberdeen ajaccio albacete almeria amsterdam badajoz barcelona bayonne bergen
berlin bern birmingham bologna bordeaux bourges brasov bratislava bremen brest
brussel bucuresti budapest burgos cagliari calais cardiff catania cluj_napoca
constanta cordoba dortmund dresden dusseldorf edinburgh felixstowe firenze
frankfurt galati gdansk geneve gijon glasgow goteborg graz grimsby hamburg
hannover helsinki iasi istanbul kaliningrad kalmar kaunas klaipeda kobenhavn
krakow lahti leipzig lemans leon lille limoges linkoping lisboa london
luxembourg lyon madrid malaga manchester marseille milano munchen nantes napoli
newcastle nurnberg oslo osnabruck palermo paris petersburg pitesti plovdiv
plymouth porto prague riga roma rostock rotterdam salzburg sassari sevilla
sofia stockholm strasbourg stuttgart szczecin szeged tallinn taranto torino
toulouse turku valladolid verona vilnius warszawa wien wroclaw zaragoza zurich
""".split())

RECRUITMENT_CITIES = frozenset("""
aberdeen berlin birmingham bremen brno brussel calais dortmund dover dresden
edinburgh geneve glasgow graz groningen hamburg hannover innsbruck kassel
klagenfurt koln leipzig liege linz liverpool london luxembourg lyon manchester
mannheim metz milano munchen newcastle nurnberg paris plymouth poznan prague
reims sheffield southampton stuttgart swansea szczecin venezia wien zurich
""".split())
