"""Independent SYNTHETIC_TEST spatial benchmark for later MapGIS host comparison.

These Shapely calculations are not a substitute for running the MapGIS SDK.
"""
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union


def test_synthetic_cross_zone_population_and_road_reference():
    mode = 'SYNTHETIC_TEST'
    assert mode == 'SYNTHETIC_TEST'
    areas = {
        'A': Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
        'B': Polygon([(10, 0), (20, 0), (20, 10), (10, 10)]),
    }
    buildings = {
        'b1': (Polygon([(1, 1), (3, 1), (3, 3), (1, 3)]), 'flooded'),
        'b2': (Polygon([(9, 1), (12, 1), (12, 3), (9, 3)]), 'normal'),
        'b3': (Polygon([(7, 7), (8, 7), (8, 8), (7, 8)]), 'normal'),
    }
    owner = {identifier: max(areas, key=lambda key: geometry.intersection(areas[key]).area)
             for identifier, (geometry, _) in buildings.items()}
    assert owner == {'b1': 'A', 'b2': 'B', 'b3': 'A'}

    cells = {'A': (areas['A'], 100), 'B': (areas['B'], 200)}  # persons_per_cell
    floods = [Polygon([(0, 0), (5, 0), (5, 10), (0, 10)]),
              Polygon([(4, 0), (7, 0), (7, 10), (4, 10)])]
    flooded_union = unary_union(floods)
    assert flooded_union.intersection(areas['A']).area == 70
    assert sum(f.intersection(areas['A']).area for f in floods) == 80  # proves union is necessary
    population = {key: people * cell.intersection(zone).area / cell.area
                  for key, zone in areas.items() for cell, people in [cells[key]]}
    affected = {key: people * cell.intersection(zone).intersection(flooded_union).area / cell.area
                for key, zone in areas.items() for cell, people in [cells[key]]}
    assert population == {'A': 100, 'B': 200}
    assert affected == {'A': 70, 'B': 0}

    roads = [(LineString([(0, 5), (20, 5)]), 'BLOCKED'),
             (LineString([(0, 6), (20, 6)]), 'NORMAL')]
    total_length = {key: sum(line.intersection(zone).length for line, _ in roads)
                    for key, zone in areas.items()}
    blocked_length = {key: sum(line.intersection(zone).length for line, status in roads if status == 'BLOCKED')
                      for key, zone in areas.items()}
    assert total_length == {'A': 20, 'B': 20}
    assert blocked_length == {'A': 10, 'B': 10}

    building_risk_a = 1 / 2
    score_a = .4 * building_risk_a + .3 * (affected['A'] / population['A']) + .2 * .5 + .1 * .5
    score_b = .4 * 0 + .3 * 0 + .2 * .5 + .1 * .2
    assert abs(score_a - .56) < 1e-12
    assert abs(score_b - .12) < 1e-12
