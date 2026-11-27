/*
 * Mar-to-gis: pure spatial and descriptive chemistry helpers.
 * Coordinates are Mars longitude (east-positive degrees), latitude (degrees).
 * Polygon lookup is a cartographic overlay of the supplied position; it does not
 * establish the geology of a remote laser target or resolve contact uncertainty.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.MarsGISMath = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const RADIUS_M = 3396190;
  const DEG = Math.PI / 180;
  // The same molar-mass convention used by the Mars LIBS Explorer.
  const MOLAR = Object.freeze({
    SiO2: [60.0843, 1, 'Si'], Al2O3: [101.9613, 2, 'Al'],
    FeOT: [71.844, 1, 'Fe'], MgO: [40.3044, 1, 'Mg'],
    CaO: [56.0774, 1, 'Ca'], Na2O: [61.9789, 2, 'Na'],
    K2O: [94.196, 2, 'K']
  });
  const boundsCache = new WeakMap();
  const collectionCache = new WeakMap();
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const validCoordinate = value => Array.isArray(value) && value.length >= 2 &&
    finite(value[0]) && finite(value[1]) && Math.abs(value[1]) <= 90;
  const normalizedLongitudeDelta = value => ((value + 180) % 360 + 360) % 360 - 180;

  function orderedValues(values) {
    return Array.from(values || []).filter(finite).sort((a, b) => a - b);
  }

  // Linear interpolation between order statistics: h = (n - 1) p.
  function sortedQuantile(values, p) {
    if (!values.length || !finite(p) || p < 0 || p > 1) return null;
    const h = (values.length - 1) * p;
    const i = Math.floor(h);
    return values[i] + (values[Math.min(i + 1, values.length - 1)] - values[i]) * (h - i);
  }

  function quantile(values, p) { return sortedQuantile(orderedValues(values), p); }
  function median(values) { return quantile(values, 0.5); }

  function geometryOf(feature) {
    return feature?.type === 'Feature' ? feature.geometry : feature;
  }

  function featureBounds(feature) {
    if (!feature || typeof feature !== 'object') return null;
    if (boundsCache.has(feature)) return boundsCache.get(feature);
    const bounds = [Infinity, Infinity, -Infinity, -Infinity];
    function visitCoordinates(coordinates) {
      if (!Array.isArray(coordinates)) return;
      if (finite(coordinates[0]) && finite(coordinates[1])) {
        bounds[0] = Math.min(bounds[0], coordinates[0]);
        bounds[1] = Math.min(bounds[1], coordinates[1]);
        bounds[2] = Math.max(bounds[2], coordinates[0]);
        bounds[3] = Math.max(bounds[3], coordinates[1]);
      } else for (const child of coordinates) visitCoordinates(child);
    }
    function visitGeometry(geometry) {
      if (!geometry) return;
      if (geometry.type === 'GeometryCollection') {
        for (const child of geometry.geometries || []) visitGeometry(child);
      } else visitCoordinates(geometry.coordinates);
    }
    visitGeometry(geometryOf(feature));
    const result = bounds.every(finite) ? bounds : null;
    boundsCache.set(feature, result);
    return result;
  }

  function insideBounds(lon, lat, bounds) {
    return bounds && lon >= bounds[0] && lon <= bounds[2] && lat >= bounds[1] && lat <= bounds[3];
  }

  // 0 outside, 1 inside, 2 on a boundary. The tiny numeric tolerance is for
  // floating-point stability only; it is not a positional uncertainty estimate.
  function ringRelation(lon, lat, ring) {
    if (!Array.isArray(ring) || ring.length < 3) return 0;
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[j], b = ring[i];
      if (!validCoordinate(a) || !validCoordinate(b)) continue;
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const px = lon - a[0], py = lat - a[1];
      const cross = px * dy - py * dx;
      const tolerance = 1e-12 * Math.max(1, Math.abs(dx), Math.abs(dy));
      if (Math.abs(cross) <= tolerance &&
          lon >= Math.min(a[0], b[0]) - 1e-12 && lon <= Math.max(a[0], b[0]) + 1e-12 &&
          lat >= Math.min(a[1], b[1]) - 1e-12 && lat <= Math.max(a[1], b[1]) + 1e-12) return 2;
      if ((a[1] > lat) !== (b[1] > lat) &&
          lon < (b[0] - a[0]) * (lat - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside ? 1 : 0;
  }

  function insidePolygon(lon, lat, rings) {
    if (!Array.isArray(rings) || !rings.length) return false;
    if (!ringRelation(lon, lat, rings[0])) return false;
    // Hole interiors and hole boundaries are excluded. An outer-ring boundary
    // is included; classify() resolves shared outer boundaries in source order.
    for (let i = 1; i < rings.length; i++) if (ringRelation(lon, lat, rings[i])) return false;
    return true;
  }

  function pointInFeature(lon, lat, feature) {
    if (!finite(lon) || !finite(lat) || Math.abs(lat) > 90) return false;
    if (!insideBounds(lon, lat, featureBounds(feature))) return false;
    const geometry = geometryOf(feature);
    if (geometry?.type === 'Polygon') return insidePolygon(lon, lat, geometry.coordinates);
    if (geometry?.type === 'MultiPolygon') return geometry.coordinates.some(rings => insidePolygon(lon, lat, rings));
    return false;
  }

  function featuresOf(collection) {
    if (Array.isArray(collection)) return collection;
    if (collection?.type === 'Feature') return [collection];
    return collection?.features || [];
  }

  function classify(lon, lat, featureCollection) {
    if (!featureCollection || typeof featureCollection !== 'object' || !finite(lon) || !finite(lat)) return null;
    // Collections and features are treated as immutable. Replace their objects
    // when changing coordinates, so the bounding-box index can be rebuilt.
    let index = collectionCache.get(featureCollection);
    if (!index) {
      index = featuresOf(featureCollection).map(feature => ({feature, bounds: featureBounds(feature)}));
      collectionCache.set(featureCollection, index);
    }
    for (const item of index) {
      if (insideBounds(lon, lat, item.bounds) && pointInFeature(lon, lat, item.feature)) return item.feature;
    }
    return null;
  }

  function distanceMeters(a, b) {
    if (!validCoordinate(a) || !validCoordinate(b)) return null;
    const dLat = (b[1] - a[1]) * DEG;
    const dLon = normalizedLongitudeDelta(b[0] - a[0]) * DEG;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * DEG) * Math.cos(b[1] * DEG) * Math.sin(dLon / 2) ** 2;
    return 2 * RADIUS_M * Math.asin(Math.sqrt(Math.max(0, Math.min(1, h))));
  }

  function lineParts(feature) {
    const geometry = geometryOf(feature);
    if (geometry?.type === 'LineString') return [geometry.coordinates];
    if (geometry?.type === 'MultiLineString') return geometry.coordinates;
    if (geometry?.type === 'GeometryCollection') return geometry.geometries.flatMap(lineParts);
    return [];
  }

  // Point-to-segment distance in a local equirectangular tangent approximation
  // centered on the query position. Appropriate for these regional map extents,
  // not a global geodesic nearest-line solver or a target-position error model.
  function nearestLineMeters(lon, lat, featureCollection) {
    if (!validCoordinate([lon, lat])) return {distance_m: null, feature: null};
    const xScale = RADIUS_M * DEG * Math.cos(lat * DEG);
    const yScale = RADIUS_M * DEG;
    let bestDistance = Infinity, bestFeature = null;
    for (const feature of featuresOf(featureCollection)) {
      for (const part of lineParts(feature)) {
        for (let i = 1; i < part.length; i++) {
          const a = part[i - 1], b = part[i];
          if (!validCoordinate(a) || !validCoordinate(b)) continue;
          const ax = normalizedLongitudeDelta(a[0] - lon) * xScale;
          const ay = (a[1] - lat) * yScale;
          const bx = normalizedLongitudeDelta(b[0] - lon) * xScale;
          const by = (b[1] - lat) * yScale;
          const dx = bx - ax, dy = by - ay, lengthSquared = dx * dx + dy * dy;
          const t = lengthSquared > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / lengthSquared)) : 0;
          const distance = Math.hypot(ax + t * dx, ay + t * dy);
          if (distance < bestDistance) { bestDistance = distance; bestFeature = feature; }
        }
      }
    }
    return {distance_m: bestFeature ? bestDistance : null, feature: bestFeature};
  }

  function cations(point) {
    const out = {};
    for (const [oxide, [mass, count, symbol]] of Object.entries(MOLAR)) {
      const value = point?.oxides?.[oxide];
      out[symbol] = finite(value) && value >= 0 ? value / mass * count : null;
    }
    return out;
  }

  function computeMetric(point, metric) {
    if (['mgNumber', 'caAl', 'alkAl', 'feMg'].includes(metric)) {
      const c = cations(point);
      if (metric === 'mgNumber') return finite(c.Mg) && finite(c.Fe) && c.Mg + c.Fe > 0 ? 100 * c.Mg / (c.Mg + c.Fe) : null;
      if (metric === 'caAl') return finite(c.Ca) && finite(c.Al) && c.Al > 0 ? c.Ca / c.Al : null;
      if (metric === 'alkAl') return finite(c.Na) && finite(c.K) && finite(c.Al) && c.Al > 0 ? (c.Na + c.K) / c.Al : null;
      if (metric === 'feMg') return finite(c.Fe) && finite(c.Mg) && c.Mg > 0 ? c.Fe / c.Mg : null;
    }
    const value = point?.oxides?.[metric];
    // Archived negative predictions remain in the raw source/table. This
    // quantitative plotting/summary function accepts only nonnegative values.
    return finite(value) && value >= 0 ? value : null;
  }

  function ternary(point) {
    const c = cations(point);
    if (!Object.values(c).every(finite)) return null;
    const a = c.Si + c.Al, b = c.Ca + c.Na + c.K, d = c.Fe + c.Mg;
    const sum = a + b + d;
    return sum > 0 ? {a: a / sum, b: b / sum, c: d / sum} : null;
  }

  function summarize(points, metric) {
    const input = Array.from(points || []);
    const values = orderedValues(input.map(point => computeMetric(point, metric)));
    return {
      n: values.length, missing: input.length - values.length,
      median: sortedQuantile(values, 0.5), q1: sortedQuantile(values, 0.25), q3: sortedQuantile(values, 0.75),
      min: values.length ? values[0] : null, max: values.length ? values[values.length - 1] : null
    };
  }

  function rose(lines, options = {}) {
    const binCount = Number.isInteger(options.binCount) && options.binCount > 0 && options.binCount <= 180 ? options.binCount : 12;
    const width = 180 / binCount;
    const bins = Array.from({length: binCount}, (_, i) => ({
      start_deg: i * width, end_deg: (i + 1) * width, center_deg: (i + 0.5) * width,
      length_m: 0, fraction: 0, segment_count: 0
    }));
    let totalLength = 0, segmentCount = 0, featureCount = 0;
    for (const feature of featuresOf(lines)) {
      if (options.kind != null && feature.properties?.kind !== options.kind) continue;
      let usedFeature = false;
      for (const part of lineParts(feature)) {
        for (let i = 1; i < part.length; i++) {
          const a = part[i - 1], b = part[i];
          const length = distanceMeters(a, b);
          if (!finite(length) || length <= 1e-9) continue;
          // Segment orientation in the local tangent plane at mean latitude;
          // axial folding makes reversed digitization directions identical.
          const east = normalizedLongitudeDelta(b[0] - a[0]) * Math.cos((a[1] + b[1]) * DEG / 2);
          const north = b[1] - a[1];
          const bearing = ((Math.atan2(east, north) / DEG) % 180 + 180) % 180;
          const index = Math.min(binCount - 1, Math.floor(bearing / width));
          bins[index].length_m += length;
          bins[index].segment_count++;
          totalLength += length; segmentCount++; usedFeature = true;
        }
      }
      if (usedFeature) featureCount++;
    }
    if (totalLength > 0) for (const bin of bins) bin.fraction = bin.length_m / totalLength;
    return {
      bins, total_length_m: totalLength, segment_count: segmentCount, feature_count: featureCount,
      kind: options.kind ?? null,
      convention: 'Axial azimuth 0–180 degrees; north = 0, east = 90. Original mapped segments weighted by spherical length.',
      interpretation: 'Describes orientations of the selected mapped linework. Contacts, scarps and ridges are not automatically faults or fractures; this is not a stress inversion.'
    };
  }

  return Object.freeze({
    RADIUS_M, finite, median, quantile, featureBounds, pointInFeature, classify,
    distanceMeters, nearestLineMeters, computeMetric, ternary, summarize, rose
  });
});
