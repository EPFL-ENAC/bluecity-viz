/**
 * The statistical sectors of Lausanne, the 17 quartiers split in 81 pieces.
 *
 * The basemap has no district for Lausanne: the `place` layer only carries the
 * city point, and OpenStreetMap has no quartier boundary either. So a zone in
 * the middle of town could never be called "Cite" or "Valency", it always fell
 * back to the name of its main street.
 *
 * The list of sectors comes from the city statistics office (see
 * https://fr.wikipedia.org/wiki/Liste_des_quartiers_de_Lausanne). There is no
 * public geometry we can fetch, so each sector is one point, geocoded from its
 * name. A zone takes the name of the closest point, which cuts the city the
 * same way a Voronoi does. The points sit about 400 m apart in the centre, so
 * DISTRICT_REACH is mostly there to say "this is still Lausanne".
 *
 * Only Lausanne is filled in. Everywhere else in Switzerland no point is in
 * reach, and the naming falls back to the basemap places, then to the main
 * street of the zone.
 */
export interface DistrictPoint {
  name: string
  lon: number
  lat: number
}

/** how far a zone centre can sit from a sector point and still take its name, in metres */
export const DISTRICT_REACH = 900

export const DISTRICTS: DistrictPoint[] = [
  { name: 'Ancien-Stand', lon: 6.62664, lat: 46.53469 },
  { name: 'Avant-Poste', lon: 6.6423, lat: 46.5171 },
  { name: 'Avenue Rambert', lon: 6.64691, lat: 46.51518 },
  { name: 'Avenue Secrétan', lon: 6.64639, lat: 46.51931 },
  { name: "Avenue d'Ouchy", lon: 6.63086, lat: 46.51362 },
  { name: "Avenue d'Échallens", lon: 6.62287, lat: 46.52407 },
  { name: 'Avenue de Provence', lon: 6.60934, lat: 46.52294 },
  { name: 'Beaulieu', lon: 6.62353, lat: 46.52822 },
  { name: 'Bellerive', lon: 6.61834, lat: 46.51009 },
  { name: 'Bellevaux', lon: 6.6339, lat: 46.53888 },
  { name: 'Bergières', lon: 6.61923, lat: 46.53026 },
  { name: 'Blécherette', lon: 6.61899, lat: 46.54178 },
  { name: 'Bois de Rovéréaz', lon: 6.65662, lat: 46.52993 },
  { name: 'Bois-Gentil', lon: 6.62226, lat: 46.53853 },
  { name: 'Bois-Mermet', lon: 6.62849, lat: 46.53693 },
  { name: 'Borde', lon: 6.62998, lat: 46.53231 },
  { name: 'Bossons', lon: 6.61729, lat: 46.53919 },
  { name: 'Bourdonnette', lon: 6.59034, lat: 46.52331 },
  { name: 'Bourget', lon: 6.58973, lat: 46.51869 },
  { name: 'Béthusy', lon: 6.647, lat: 46.52173 },
  { name: 'Chablière', lon: 6.61312, lat: 46.53282 },
  { name: 'Chailly', lon: 6.65445, lat: 46.52519 },
  { name: 'Chauderon', lon: 6.62514, lat: 46.52403 },
  { name: 'Chemin de la Vuachère', lon: 6.65116, lat: 46.51717 },
  { name: 'Chemin des Roches', lon: 6.65642, lat: 46.54216 },
  { name: 'Chissiez', lon: 6.6488, lat: 46.51404 },
  { name: 'Cité', lon: 6.63589, lat: 46.52407 },
  { name: 'Cour', lon: 6.62582, lat: 46.51258 },
  { name: 'Craivavers', lon: 6.65921, lat: 46.53133 },
  { name: 'Devin', lon: 6.65199, lat: 46.53016 },
  { name: 'Florimont', lon: 6.63907, lat: 46.51536 },
  { name: 'Gare de Sébeillon', lon: 6.60894, lat: 46.52529 },
  { name: 'Gare/Petit-Chêne', lon: 6.62922, lat: 46.51681 },
  { name: 'Georgette', lon: 6.63759, lat: 46.51708 },
  { name: 'Grancy', lon: 6.62887, lat: 46.51493 },
  { name: 'Grand-Vennes', lon: 6.64616, lat: 46.54011 },
  { name: 'Grangette', lon: 6.6332, lat: 46.54159 },
  { name: 'Harpe', lon: 6.62529, lat: 46.51376 },
  { name: 'Hôpitaux', lon: 6.64454, lat: 46.52521 },
  { name: 'La Sallaz', lon: 6.64702, lat: 46.53275 },
  { name: 'Le Flon', lon: 6.63063, lat: 46.52077 },
  { name: 'Le Vallon', lon: 6.6394, lat: 46.52702 },
  { name: 'Les Cèdres', lon: 6.62664, lat: 46.52472 },
  { name: 'Les Râpes', lon: 6.69481, lat: 46.55428 },
  { name: 'Malley', lon: 6.60307, lat: 46.52421 },
  { name: 'Marc-Dufour', lon: 6.61675, lat: 46.51903 },
  { name: 'Marterey', lon: 6.63846, lat: 46.52062 },
  { name: 'Maupas', lon: 6.62405, lat: 46.52583 },
  { name: 'Milan', lon: 6.62264, lat: 46.5153 },
  { name: 'Mon-Repos', lon: 6.64111, lat: 46.51871 },
  { name: "Mont-d'Or", lon: 6.61515, lat: 46.51697 },
  { name: 'Montbenon', lon: 6.62965, lat: 46.51977 },
  { name: 'Montchoisi', lon: 6.6364, lat: 46.511 },
  { name: 'Montheron', lon: 6.66435, lat: 46.59015 },
  { name: 'Montoie', lon: 6.60847, lat: 46.51846 },
  { name: 'Montétan', lon: 6.61332, lat: 46.52998 },
  { name: 'Ouchy', lon: 6.62624, lat: 46.50742 },
  { name: 'Pierrefleur', lon: 6.61651, lat: 46.53495 },
  { name: 'Pontaise', lon: 6.62432, lat: 46.53323 },
  { name: 'Praz-Séchaud', lon: 6.66688, lat: 46.53746 },
  { name: 'Pré-Fleuri', lon: 6.62944, lat: 46.51322 },
  { name: 'Pré-du-Marché', lon: 6.62881, lat: 46.52504 },
  { name: 'Prélaz', lon: 6.61268, lat: 46.52639 },
  { name: 'Prés-de-Vidy', lon: 6.598, lat: 46.5185 },
  { name: 'Pyramides', lon: 6.60191, lat: 46.52279 },
  { name: 'Riponne/Tunnel', lon: 6.6337, lat: 46.52325 },
  { name: 'Route de Berne', lon: 6.64998, lat: 46.53781 },
  { name: 'Route du Signal', lon: 6.63708, lat: 46.53222 },
  { name: 'Rouvraie', lon: 6.63172, lat: 46.53256 },
  { name: 'Rue Centrale', lon: 6.63304, lat: 46.52083 },
  { name: 'Rue de Morges', lon: 6.61431, lat: 46.52579 },
  { name: 'Rue de Sébeillon', lon: 6.61739, lat: 46.52347 },
  { name: 'Sauvabelin', lon: 6.64051, lat: 46.53274 },
  { name: 'Tivoli', lon: 6.62107, lat: 46.5211 },
  { name: 'Valency', lon: 6.61139, lat: 46.53137 },
  { name: 'Valentin', lon: 6.63152, lat: 46.52449 },
  { name: 'Vallée de la Jeunesse', lon: 6.60497, lat: 46.52078 },
  { name: 'Valmont', lon: 6.65547, lat: 46.53532 },
  { name: 'Vennes', lon: 6.6576, lat: 46.54123 },
  { name: 'Vernand', lon: 6.59266, lat: 46.56686 },
  { name: 'Victor-Ruffy', lon: 6.64855, lat: 46.53186 },
  { name: 'Élysée', lon: 6.62374, lat: 46.51866 }
]
