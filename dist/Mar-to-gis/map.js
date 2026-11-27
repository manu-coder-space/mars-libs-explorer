/* Mar-to-gis: local Mars equirectangular map. No terrestrial map projection. */
(() => {
  'use strict';
  const RADIUS = 3396190;
  const RAD = Math.PI / 180;
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
  const validBounds = b => Array.isArray(b) && b.length === 4 && b.every(finite) && b[2] > b[0] && b[3] > b[1];
  const intersects = (a, b) => !a || !b || (a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]);
  const distance = (a, b) => {
    const p1 = a.lat * RAD, p2 = b.lat * RAD;
    const h = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin((b.lon - a.lon) * RAD / 2) ** 2;
    return 2 * RADIUS * Math.asin(Math.sqrt(clamp(h, 0, 1)));
  };
  const lengthOf = points => points.slice(1).reduce((sum, p, i) => sum + distance(points[i], p), 0);
  const metres = m => m >= 1000 ? `${(m / 1000).toLocaleString(undefined, {maximumFractionDigits: 2})} km` : `${Math.round(m).toLocaleString()} m`;

  function geometryBounds(geometry) {
    if (!geometry) return null;
    const bounds = [Infinity, Infinity, -Infinity, -Infinity];
    const walk = value => {
      if (!Array.isArray(value)) return;
      if (finite(value[0]) && finite(value[1])) {
        bounds[0] = Math.min(bounds[0], value[0]); bounds[2] = Math.max(bounds[2], value[0]);
        bounds[1] = Math.min(bounds[1], value[1]); bounds[3] = Math.max(bounds[3], value[1]);
      } else value.forEach(walk);
    };
    walk(geometry.coordinates);
    return bounds.every(finite) ? bounds : null;
  }

  function inRing(lon, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[i], b = ring[j];
      if ((a[1] > lat) !== (b[1] > lat) && lon < (b[0] - a[0]) * (lat - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }

  function contains(lon, lat, geometry) {
    const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : [];
    return polygons.some(rings => rings.length && inRing(lon, lat, rings[0]) && !rings.slice(1).some(r => inRing(lon, lat, r)));
  }

  function color(value, lo, hi) {
    if (!finite(value)) return '#929b9d';
    const stops = [[51, 93, 131], [84, 165, 181], [169, 200, 176], [225, 191, 124], [205, 119, 76]];
    const v = clamp((value - lo) / (hi - lo || 1), 0, 1) * 4, i = Math.min(3, Math.floor(v)), f = v - i;
    return `rgb(${stops[i].map((n, j) => Math.round(n + (stops[i + 1][j] - n) * f)).join(',')})`;
  }

  class MarsGISMap {
    constructor(canvas, callbacks = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.callbacks = callbacks;
      this.data = {rasters: [], polygons: {features: []}, lines: {features: []}, points: [], traverse: [], evidence: [], landmarks: []};
      this.style = {showGeology: true, geologyOpacity: .42, showContacts: true, showStructures: true, showPoints: true, showTraverse: true, showEvidence: true, showAcquisitions: false, colorMin: 0, colorMax: 100, colorLabel: 'SiO₂ wt%', pointSize: 3, visibleRasterIds: null, lineKinds: null};
      this.center = [77.405, 18.46];
      this.span = .11;
      this.mode = 'inspect';
      this.images = new Map();
      this.pointers = new Map();
      this.polygonIndex = [];
      this.lineIndex = [];
      this.selection = null;
      this.measurement = [];
      this.measurementFinished = false;
      this.hover = null;
      this.width = 1;
      this.height = 1;
      this.frame = 0;
      canvas.style.touchAction = 'none';
      if (!canvas.hasAttribute('tabindex')) canvas.tabIndex = 0;
      if (!canvas.hasAttribute('aria-label')) canvas.setAttribute('aria-label', 'Interactive Mars map. Drag to pan, pinch or scroll to zoom; keyboard arrow keys pan, plus and minus zoom.');
      this._listeners = [];
      this._listen(canvas, 'pointerdown', this._down.bind(this));
      this._listen(canvas, 'pointermove', this._move.bind(this));
      this._listen(canvas, 'pointerup', this._up.bind(this));
      this._listen(canvas, 'pointercancel', this._cancel.bind(this));
      this._listen(canvas, 'pointerleave', () => {if (!this.pointers.size) {this.hover = null; this.draw();}});
      this._listen(canvas, 'wheel', e => {e.preventDefault(); this.zoom(Math.exp(clamp(e.deltaY, -150, 150) * .002), this._pixel(e));}, {passive: false});
      this._listen(canvas, 'dblclick', e => {e.preventDefault(); if (this.mode === 'measure') {this.measurementFinished = true; this.draw();} else if (this.mode === 'inspect') this.zoom(.55, this._pixel(e));});
      this._listen(canvas, 'keydown', this._key.bind(this));
      this.resizeObserver = new ResizeObserver(() => this.draw());
      this.resizeObserver.observe(canvas);
      this.draw();
    }

    _listen(target, type, fn, options) {target.addEventListener(type, fn, options); this._listeners.push([target, type, fn, options]);}
    _pixel(event) {const r = this.canvas.getBoundingClientRect(); return {x: event.clientX - r.left, y: event.clientY - r.top};}
    _cos() {return Math.max(.05, Math.cos(this.center[1] * RAD));}
    _spanX() {return this.span * this.width / this.height / this._cos();}
    project(lon, lat) {return {x: (lon - this.center[0]) / this._spanX() * this.width + this.width / 2, y: (this.center[1] - lat) / this.span * this.height + this.height / 2};}
    unproject(x, y) {return {lon: this.center[0] + (x / this.width - .5) * this._spanX(), lat: this.center[1] - (y / this.height - .5) * this.span};}
    getView() {const x = this._spanX(); return [this.center[0] - x / 2, this.center[1] - this.span / 2, this.center[0] + x / 2, this.center[1] + this.span / 2];}

    setData(data = {}) {
      Object.assign(this.data, data);
      if ('polygons' in data) this.polygonIndex = (data.polygons?.features || []).map(feature => ({feature, bounds: geometryBounds(feature.geometry)}));
      if ('lines' in data) this.lineIndex = (data.lines?.features || []).map(feature => ({feature, bounds: geometryBounds(feature.geometry)}));
      (this.data.rasters || []).forEach(r => this._image(r.image));
      this.draw();
      return this;
    }
    setStyle(style = {}) {Object.assign(this.style, style); this.draw(); return this;}
    fit(bounds) {this._fitBounds(bounds, 1.08);}
    setView(bounds) {this._fitBounds(bounds, 1);}
    _fitBounds(bounds, padding) {
      if (!validBounds(bounds)) return;
      const r = this.canvas.getBoundingClientRect(); this.width = Math.max(1, r.width); this.height = Math.max(1, r.height);
      this.center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
      this.span = clamp(Math.max(bounds[3] - bounds[1], (bounds[2] - bounds[0]) * this._cos() * this.height / this.width) * padding, .00002, 150);
      this.draw(); this._changed();
    }
    setMode(mode) {
      this.mode = ['inspect', 'select', 'measure'].includes(mode) ? mode : 'inspect';
      this.canvas.style.cursor = this.mode === 'inspect' ? 'grab' : 'crosshair';
      this.hover = null; this.draw();
    }
    clearSelection() {this.selection = null; this.selectionDrag = null; this.draw();}
    clearMeasure() {this.measurement = []; this.measurementFinished = false; this.hover = null; this.draw(); this.callbacks.onMeasure?.(0, []);}
    zoom(factor, pixel = {x: this.width / 2, y: this.height / 2}) {
      const anchor = this.unproject(pixel.x, pixel.y);
      this.span = clamp(this.span * factor, .00002, 150);
      // Latitude changes the longitude scale; update it before anchoring longitude.
      this.center[1] = clamp(anchor.lat + (pixel.y / this.height - .5) * this.span, -85, 85);
      this.center[0] = anchor.lon - (pixel.x / this.width - .5) * this._spanX();
      this.draw(); this._changed();
    }
    _changed() {clearTimeout(this.viewTimer); this.viewTimer = setTimeout(() => this.callbacks.onView?.(this.getView()), 100);}

    _down(e) {
      if (e.button !== undefined && e.button !== 0) return;
      e.preventDefault(); this.canvas.focus({preventScroll: true}); this.canvas.setPointerCapture(e.pointerId);
      const p = this._pixel(e); this.pointers.set(e.pointerId, p);
      if (this.pointers.size === 1) {
        this.gesture = {start: p, center: [...this.center], span: this.span, spanX: this._spanX(), moved: false, pinched: false};
        if (this.mode === 'select') this.selectionDrag = [p, p];
        this.canvas.style.cursor = this.mode === 'inspect' ? 'grabbing' : 'crosshair';
      } else if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()], mid = {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2};
        this.gesture = {distance: Math.hypot(a.x - b.x, a.y - b.y), anchor: this.unproject(mid.x, mid.y), span: this.span, moved: true, pinched: true};
        this.selectionDrag = null;
      }
    }
    _move(e) {
      const p = this._pixel(e); this.hover = this.unproject(p.x, p.y);
      if (!this.pointers.has(e.pointerId)) {if (this.mode === 'measure') this.draw(); return;}
      this.pointers.set(e.pointerId, p);
      const g = this.gesture;
      if (this.pointers.size >= 2 && g?.anchor) {
        const [a, b] = [...this.pointers.values()], d = Math.max(1, Math.hypot(a.x - b.x, a.y - b.y));
        const mid = {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2};
        this.span = clamp(g.span * g.distance / d, .00002, 150);
        this.center[1] = clamp(g.anchor.lat + (mid.y / this.height - .5) * this.span, -85, 85);
        this.center[0] = g.anchor.lon - (mid.x / this.width - .5) * this._spanX();
      } else if (g && !g.pinched) {
        const dx = p.x - g.start.x, dy = p.y - g.start.y;
        g.moved ||= Math.hypot(dx, dy) > 5;
        if (this.mode === 'select') this.selectionDrag = [g.start, p];
        else if (g.moved) {
          this.center[0] = g.center[0] - dx / this.width * g.spanX;
          this.center[1] = clamp(g.center[1] + dy / this.height * g.span, -85, 85);
        }
      }
      this.draw();
    }
    _up(e) {
      if (!this.pointers.has(e.pointerId)) return;
      const p = this._pixel(e), g = this.gesture;
      this.pointers.delete(e.pointerId);
      if (this.pointers.size) return;
      if (g && !g.pinched) {
        if (this.mode === 'select' && g.moved) {
          const a = this.unproject(g.start.x, g.start.y), b = this.unproject(p.x, p.y);
          this.selection = [Math.min(a.lon, b.lon), Math.min(a.lat, b.lat), Math.max(a.lon, b.lon), Math.max(a.lat, b.lat)];
          this.callbacks.onSelection?.([...this.selection]);
        } else if (!g.moved) this._pick(p);
      }
      this.selectionDrag = null; this.gesture = null;
      this.canvas.style.cursor = this.mode === 'inspect' ? 'grab' : 'crosshair';
      this.draw(); this._changed();
    }
    _cancel(e) {this.pointers.delete(e.pointerId); if (!this.pointers.size) {this.gesture = null; this.selectionDrag = null;} this.draw();}
    _key(e) {
      let handled = true;
      if (e.key === '+' || e.key === '=') this.zoom(.7);
      else if (e.key === '-' || e.key === '_') this.zoom(1 / .7);
      else if (e.key === 'ArrowLeft') this.center[0] -= this._spanX() * .12;
      else if (e.key === 'ArrowRight') this.center[0] += this._spanX() * .12;
      else if (e.key === 'ArrowUp') this.center[1] = clamp(this.center[1] + this.span * .12, -85, 85);
      else if (e.key === 'ArrowDown') this.center[1] = clamp(this.center[1] - this.span * .12, -85, 85);
      else if (e.key === 'Escape') {this.selectionDrag = null; this.clearMeasure(); this.setMode('inspect');}
      else if (e.key === 'Enter' && this.mode === 'measure') this.measurementFinished = true;
      else handled = false;
      if (handled) {e.preventDefault(); this.draw(); this._changed();}
    }

    _pick(pixel) {
      const location = this.unproject(pixel.x, pixel.y);
      if (this.mode === 'measure') {
        const now = performance.now();
        if (this.lastMeasureClick && now - this.lastMeasureClick.time < 330 && Math.hypot(pixel.x - this.lastMeasureClick.x, pixel.y - this.lastMeasureClick.y) < 8) {this.measurementFinished = true; return;}
        if (this.measurementFinished) {this.measurement = []; this.measurementFinished = false;}
        this.measurement.push(location); this.lastMeasureClick = {...pixel, time: now};
        this.callbacks.onMeasure?.(lengthOf(this.measurement), this.measurement.map(p => ({...p})));
        return;
      }
      let nearest = null, nearEvidence = null, best = 12;
      if (this.style.showPoints) for (const point of this.data.points || []) {
        const p = this.project(point.lon, point.lat), d = Math.hypot(p.x - pixel.x, p.y - pixel.y);
        if (d < best) {nearest = point; best = d;}
      }
      best = 11;
      if (this.style.showEvidence || this.style.showAcquisitions) for (const item of this.data.evidence || []) {
        if (!this._evidenceVisible(item)) continue;
        const p = this.project(item.lon, item.lat), d = Math.hypot(p.x - pixel.x, p.y - pixel.y);
        if (d < best) {nearEvidence = item; best = d;}
      }
      const position = nearEvidence || nearest || location;
      // Evidence and measured points take precedence over the cartographic lines.
      const line = !nearEvidence && !nearest ? this._pickLine(pixel) : null;
      const pointInFeature = window.MarsGISMath?.pointInFeature || ((lon, lat, feature) => contains(lon, lat, feature.geometry));
      const polygon = this.style.showGeology ? this.polygonIndex.find(item => intersects(item.bounds, [position.lon, position.lat, position.lon, position.lat]) && pointInFeature(position.lon, position.lat, item.feature))?.feature : null;
      const feature = line || polygon || null;
      this.callbacks.onPick?.({...location, feature, point: nearest, evidence: nearEvidence});
    }

    _pickLine(pixel) {
      const a = this.unproject(pixel.x - 7, pixel.y + 7), b = this.unproject(pixel.x + 7, pixel.y - 7);
      const hitBox = [a.lon, a.lat, b.lon, b.lat];
      let nearest = null, best = 6;
      for (const item of this.lineIndex) {
        if (!intersects(item.bounds, hitBox) || !this._lineVisible(item.feature)) continue;
        const geometry = item.feature.geometry;
        const lines = geometry?.type === 'LineString' ? [geometry.coordinates] : geometry?.type === 'MultiLineString' ? geometry.coordinates : [];
        for (const line of lines) for (let i = 1; i < line.length; i++) {
          const p = this.project(line[i - 1][0], line[i - 1][1]), q = this.project(line[i][0], line[i][1]);
          const dx = q.x - p.x, dy = q.y - p.y;
          const t = clamp(((pixel.x - p.x) * dx + (pixel.y - p.y) * dy) / (dx * dx + dy * dy || 1), 0, 1);
          const d = Math.hypot(pixel.x - p.x - t * dx, pixel.y - p.y - t * dy);
          if (d < best) {best = d; nearest = item.feature;}
        }
      }
      return nearest;
    }

    _image(url) {
      if (!url || this.images.has(url)) return this.images.get(url);
      const record = {image: new Image(), state: 'loading'};
      this.images.set(url, record); record.image.crossOrigin = 'anonymous';
      record.image.onload = () => {record.state = 'ready'; this.draw();};
      record.image.onerror = () => {record.state = 'error'; this.callbacks.onStatus?.(`Image unavailable: ${url}`); this.draw();};
      record.image.src = url;
      return record;
    }
    draw() {if (!this.frame) this.frame = requestAnimationFrame(() => {this.frame = 0; this._render();});}

    _path(coordinates, close = false) {
      const ctx = this.ctx;
      coordinates.forEach((v, i) => {const p = this.project(v[0], v[1]); if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);});
      if (close) ctx.closePath();
    }
    _evidenceVisible(item) {return item.category === 'raman_acquisition' ? this.style.showAcquisitions : this.style.showEvidence;}
    _lineVisible(feature) {
      const p = feature.properties || {}, kind = String(p.kind || p.layer || p.label || 'structure');
      // Source map-limit lines are not geologic contacts.
      if (/\bboundary\b/i.test(String(p.label || ''))) return false;
      const contact = /contact/i.test(kind);
      return (contact ? this.style.showContacts : this.style.showStructures) && (!this.style.lineKinds || this.style.lineKinds.includes(kind));
    }

    _render() {
      const rect = this.canvas.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) return;
      this.width = rect.width; this.height = rect.height;
      const dpr = Math.min(2, window.devicePixelRatio || 1), w = this.width, h = this.height, ctx = this.ctx;
      if (this.canvas.width !== Math.round(w * dpr) || this.canvas.height !== Math.round(h * dpr)) {this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr);}
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.globalAlpha = 1; ctx.setLineDash([]);
      ctx.fillStyle = '#172326'; ctx.fillRect(0, 0, w, h);
      const bounds = this.getView();
      const rasters = (this.data.rasters || []).filter(r => !this.style.visibleRasterIds || this.style.visibleRasterIds.includes(r.id));
      let loading = 0, failed = 0;
      for (const raster of rasters) {
        if (!validBounds(raster.bounds) || !intersects(bounds, raster.bounds)) continue;
        const image = this._image(raster.image);
        if (image?.state !== 'ready') {if (image?.state === 'error') failed++; else loading++; continue;}
        const a = this.project(raster.bounds[0], raster.bounds[3]), b = this.project(raster.bounds[2], raster.bounds[1]);
        ctx.globalAlpha = finite(raster.opacity) ? raster.opacity : 1;
        ctx.drawImage(image.image, a.x, a.y, b.x - a.x, b.y - a.y);
      }
      ctx.globalAlpha = 1;
      if (this.style.showGeology) {
        ctx.globalAlpha = clamp(Number(this.style.geologyOpacity), 0, 1);
        for (const item of this.polygonIndex) {
          if (!intersects(item.bounds, bounds)) continue;
          const g = item.feature.geometry, polygons = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
          ctx.fillStyle = item.feature.properties?.color || '#b5b1a1';
          for (const rings of polygons) {ctx.beginPath(); rings.forEach(ring => this._path(ring, true)); ctx.fill('evenodd');}
        }
        ctx.globalAlpha = 1;
      }
      this._graticule(bounds);
      for (const item of this.lineIndex) {
        if (!intersects(item.bounds, bounds) || !this._lineVisible(item.feature)) continue;
        const p = item.feature.properties || {}, kind = `${p.kind || ''} ${p.label || ''}`;
        const lines = item.feature.geometry?.type === 'LineString' ? [item.feature.geometry.coordinates] : item.feature.geometry?.type === 'MultiLineString' ? item.feature.geometry.coordinates : [];
        const contact = /contact/i.test(kind), uncertain = /approx|conceal|infer|uncertain/i.test(kind);
        ctx.lineWidth = contact ? 1.1 : 1.7;
        ctx.strokeStyle = contact ? 'rgba(21,25,21,.85)' : '#ffc578';
        ctx.setLineDash(uncertain ? [5, 4] : []);
        for (const line of lines) {ctx.beginPath(); this._path(line); ctx.stroke();}
      }
      ctx.setLineDash([]);
      if (this.style.showTraverse) this._traverse();
      if (this.style.showPoints) this._points(bounds);
      for (const evidence of this.data.evidence || []) if (this._evidenceVisible(evidence) && finite(evidence.lon) && finite(evidence.lat)) this._evidence(evidence);
      for (const landmark of this.data.landmarks || []) {
        if (!finite(landmark.lon) || !finite(landmark.lat)) continue;
        const p = this.project(landmark.lon, landmark.lat);
        if (p.x < 0 || p.x > w || p.y < 0 || p.y > h) continue;
        ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fillStyle = landmark.color || landmark.style?.color || '#f4eee2'; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = '#172326'; ctx.stroke();
        ctx.font = '600 12px system-ui,sans-serif'; ctx.textAlign = 'left'; ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(15,25,27,.9)'; ctx.strokeText(landmark.name || '', p.x + 8, p.y - 8); ctx.fillStyle = landmark.color || landmark.style?.color || '#f4eee2'; ctx.fillText(landmark.name || '', p.x + 8, p.y - 8);
      }
      this._selection(); this._measure(); this._furniture();
      if (loading || failed) this._badge(failed ? `${failed} imagery layer${failed > 1 ? 's' : ''} unavailable` : 'Loading orbital imagery…', w - 12, h - 14, true, failed ? '#fec7a0' : '#d5e5e0');
    }

    _graticule(bounds) {
      const ctx = this.ctx, range = this._spanX(), raw = range / 5, magnitude = 10 ** Math.floor(Math.log10(raw));
      const step = [1, 2, 5, 10].map(n => n * magnitude).find(n => n >= raw) || magnitude * 10;
      const digits = clamp(-Math.floor(Math.log10(step)), 0, 5);
      ctx.lineWidth = .7; ctx.strokeStyle = 'rgba(228,238,231,.13)'; ctx.font = '11px ui-monospace,monospace'; ctx.fillStyle = '#e5ece7'; ctx.textAlign = 'center';
      for (let lon = Math.ceil(bounds[0] / step) * step; lon < bounds[2]; lon += step) {
        const p = this.project(lon, this.center[1]); ctx.beginPath(); ctx.moveTo(p.x, 0); ctx.lineTo(p.x, this.height); ctx.stroke();
        if (p.x > 70 && p.x < this.width - 60) {const label = `${lon.toFixed(digits)}°E`; ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(13,25,26,.75)'; ctx.strokeText(label, p.x, 17); ctx.fillText(label, p.x, 17); ctx.lineWidth = .7; ctx.strokeStyle = 'rgba(228,238,231,.13)';}
      }
      for (let lat = Math.ceil(bounds[1] / step) * step; lat < bounds[3]; lat += step) {
        const p = this.project(this.center[0], lat); ctx.beginPath(); ctx.moveTo(0, p.y); ctx.lineTo(this.width, p.y); ctx.stroke();
        if (p.y > 36 && p.y < this.height - 62) {const label = `${Math.abs(lat).toFixed(digits)}°${lat < 0 ? 'S' : 'N'}`; ctx.textAlign = 'left'; ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(13,25,26,.75)'; ctx.strokeText(label, 9, p.y - 5); ctx.fillText(label, 9, p.y - 5); ctx.textAlign = 'center'; ctx.lineWidth = .7; ctx.strokeStyle = 'rgba(228,238,231,.13)';}
      }
    }
    _traverse() {
      const ctx = this.ctx; ctx.beginPath();
      let last = null;
      for (const point of this.data.traverse || []) {
        const lon = point.lon ?? point.longitude, lat = point.lat ?? point.latitude;
        if (!finite(lon) || !finite(lat)) {last = null; continue;}
        const p = this.project(lon, lat);
        // Break unsupported geographic jumps instead of drawing a spurious traverse.
        if (last && Math.hypot(p.x - last.x, p.y - last.y) < Math.max(this.width, this.height) * 2) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);
        last = p;
      }
      ctx.strokeStyle = 'rgba(10,26,28,.8)'; ctx.lineWidth = 3.5; ctx.stroke(); ctx.strokeStyle = '#5ca6ba'; ctx.lineWidth = 1.3; ctx.stroke();
    }
    _points(bounds) {
      const ctx = this.ctx, selected = this.style.selectedPointId;
      for (const point of this.data.points || []) {
        if (!finite(point.lon) || !finite(point.lat) || point.lon < bounds[0] || point.lon > bounds[2] || point.lat < bounds[1] || point.lat > bounds[3]) continue;
        const p = this.project(point.lon, point.lat), radius = (Number(this.style.pointSize) || 3) + Math.min(3.3, Math.log2(Math.max(1, point.count || 1)) * .48);
        ctx.beginPath(); ctx.arc(p.x, p.y, radius, 0, Math.PI * 2); ctx.fillStyle = color(point.value, this.style.colorMin, this.style.colorMax); ctx.fill(); ctx.strokeStyle = 'rgba(14,30,34,.72)'; ctx.lineWidth = .9; ctx.stroke();
        if (point.id === selected) {ctx.beginPath(); ctx.arc(p.x, p.y, radius + 3, 0, Math.PI * 2); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();}
      }
    }
    _evidence(item) {
      const p = this.project(item.lon, item.lat), ctx = this.ctx;
      if (p.x < -10 || p.x > this.width + 10 || p.y < -10 || p.y > this.height + 10) return;
      const type = item.category, colors = {raman_acquisition: '#b2c2ce', raman_mineral: '#5eb8cd', organic_detection: '#e0a15f', organic_candidate: '#c190db', luminescence_unresolved: '#9babad'};
      ctx.beginPath();
      if (type === 'raman_acquisition') ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
      else {ctx.moveTo(p.x, p.y - 6.5); ctx.lineTo(p.x + 6.5, p.y); ctx.lineTo(p.x, p.y + 6.5); ctx.lineTo(p.x - 6.5, p.y); ctx.closePath();}
      ctx.fillStyle = colors[type] || '#fff'; ctx.strokeStyle = '#182c2d'; ctx.lineWidth = 2;
      if (type !== 'raman_acquisition' && type !== 'luminescence_unresolved') ctx.fill();
      ctx.stroke(); ctx.strokeStyle = colors[type] || '#fff'; ctx.lineWidth = 1; ctx.stroke();
    }
    _selection() {
      let a, b;
      if (this.selectionDrag) [a, b] = this.selectionDrag;
      else if (this.selection) {a = this.project(this.selection[0], this.selection[3]); b = this.project(this.selection[2], this.selection[1]);}
      if (!a || !b) return;
      const ctx = this.ctx; ctx.fillStyle = 'rgba(113,224,213,.12)'; ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y); ctx.strokeStyle = '#95f1df'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y); ctx.setLineDash([]);
    }
    _measure() {
      if (!this.measurement.length) return;
      const ctx = this.ctx, points = [...this.measurement], ghost = this.mode === 'measure' && !this.measurementFinished && this.hover && !this.pointers.size;
      if (ghost) points.push(this.hover);
      ctx.beginPath(); points.forEach((v, i) => {const p = this.project(v.lon, v.lat); i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);});
      ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(18,29,31,.8)'; ctx.stroke(); ctx.lineWidth = 2; ctx.strokeStyle = '#ffdb92'; ctx.stroke();
      for (const point of this.measurement) {const p = this.project(point.lon, point.lat); ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fillStyle = '#ffdb92'; ctx.fill(); ctx.strokeStyle = '#172326'; ctx.lineWidth = 1; ctx.stroke();}
      const end = this.project(points.at(-1).lon, points.at(-1).lat);
      this._badge(`${ghost ? '~ ' : ''}${metres(lengthOf(points))}`, clamp(end.x + 12, 12, this.width - 115), clamp(end.y - 12, 42, this.height - 12));
    }
    _badge(text, x, y, right = false, colorValue = '#f2f6e9') {
      const ctx = this.ctx; ctx.font = '12px system-ui,sans-serif'; const width = ctx.measureText(text).width + 16;
      const left = right ? x - width : x; ctx.fillStyle = 'rgba(15,31,34,.9)'; ctx.fillRect(left, y - 20, width, 27); ctx.fillStyle = colorValue; ctx.textAlign = 'left'; ctx.fillText(text, left + 8, y - 2);
    }
    _furniture() {
      const ctx = this.ctx, w = this.width, h = this.height;
      ctx.fillStyle = 'rgba(15,31,34,.86)'; ctx.fillRect(w - 44, 29, 30, 63); ctx.fillStyle = '#e8f2e8'; ctx.font = '600 12px system-ui,sans-serif'; ctx.textAlign = 'center'; ctx.fillText('N', w - 29, 46);
      ctx.beginPath(); ctx.moveTo(w - 29, 52); ctx.lineTo(w - 23, 73); ctx.lineTo(w - 29, 69); ctx.lineTo(w - 35, 73); ctx.closePath(); ctx.fill();
      const perPixel = this.span * RAD * RADIUS / h, target = perPixel * Math.min(140, w * .24), mag = 10 ** Math.floor(Math.log10(target));
      const value = [1, 2, 5, 10].map(v => v * mag).filter(v => v <= target).pop() || mag;
      const px = value / perPixel, x = 17, y = h - 21;
      ctx.fillStyle = 'rgba(15,31,34,.86)'; ctx.fillRect(10, h - 59, Math.max(px + 25, 118), 49); ctx.strokeStyle = '#f0f4e7'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x, y); ctx.lineTo(x + px, y); ctx.lineTo(x + px, y - 4); ctx.stroke();
      ctx.fillStyle = '#f0f4e7'; ctx.font = '12px ui-monospace,monospace'; ctx.textAlign = 'left'; ctx.fillText(metres(value), x, y - 10);
      ctx.font = '11px system-ui,sans-serif'; ctx.fillStyle = '#c1cfcb'; ctx.fillText('Mars · local scale', x, h - 12);
    }
    exportPNG() {this._render(); return this.canvas.toDataURL('image/png');}
    destroy() {cancelAnimationFrame(this.frame); clearTimeout(this.viewTimer); this.resizeObserver.disconnect(); this._listeners.forEach(([t, n, f, o]) => t.removeEventListener(n, f, o));}
  }
  MarsGISMap.color = color;
  MarsGISMap.distance = distance;
  MarsGISMap.radius = RADIUS;
  window.MarsGISMap = MarsGISMap;
})();
