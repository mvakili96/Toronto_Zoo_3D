const $ = (s) => document.querySelector(s);
let map, config, orbiting = false, firstRender = false, loadTimer, constraintFrame;
const state = {phase:'starting', view:'overview', steady:false};
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function constrainCamera() {
  if (!map) return;
  const limits = config.navigation;
  const range = clamp(map.range, limits.min_range_m, limits.max_range_m);
  // Google bounds limit camera position. Also keep the point it looks at inside
  // the GIS extent, and cap range for native mouse, keyboard and touch gestures.
  if (Number.isFinite(range) && Math.abs(map.range - range) > .1) map.range = range;
  const center = map.center;
  if (center) {
    const lat = clamp(center.lat, config.bounds.south, config.bounds.north);
    const lng = clamp(center.lng, config.bounds.west, config.bounds.east);
    if (Math.abs(lat - center.lat) > 1e-7 || Math.abs(lng - center.lng) > 1e-7) {
      map.center = {lat, lng, altitude:center.altitude};
    }
  }
  if (firstRender) {
    $('#zoom-in').disabled = map.range <= limits.min_range_m + .5;
    $('#zoom-out').disabled = map.range >= limits.max_range_m - .5;
  }
}
function scheduleCameraConstraint() {
  if (constraintFrame) return;
  constraintFrame = requestAnimationFrame(() => {
    constraintFrame = undefined;
    constrainCamera();
  });
}

function status(text, phase) {
  $('#status').textContent = text;
  $('#status').dataset.state = phase;
  state.phase = phase;
}
function message(title, text, phase = 'error') {
  clearTimeout(loadTimer);
  status(title, phase);
  $('#message-title').textContent = title;
  $('#message-text').textContent = text;
  $('#message').hidden = false;
  document.querySelectorAll('.panel button, .panel input').forEach(e => e.disabled = true);
}
function activeView(id) {
  state.view = id;
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === id));
}
function setOrbitButton(value) {
  orbiting = value;
  $('#orbit').textContent = value ? 'Pause orbit' : 'Orbit this view';
  $('#orbit').setAttribute('aria-pressed', String(value));
}
async function stopOrbit() {
  if (map) await map.stopCameraAnimation();
  setOrbitButton(false);
}
async function navigate(id) {
  if (!map) return;
  await stopOrbit();
  activeView(id);
  await map.flyCameraTo({endCamera:config.views[id], durationMillis:1000});
}
async function zoom(factor) {
  await stopOrbit();
  map.range = clamp(map.range * factor, config.navigation.min_range_m, config.navigation.max_range_m);
}

function loadGoogle(key) {
  return new Promise((resolve, reject) => {
    window.google3DReady = resolve;
    const url = new URL('https://maps.googleapis.com/maps/api/js');
    url.searchParams.set('key', key);
    url.searchParams.set('v', 'weekly');
    url.searchParams.set('libraries', 'maps3d');
    url.searchParams.set('loading', 'async');
    url.searchParams.set('callback', 'google3DReady');
    const script = document.createElement('script');
    script.async = true;
    script.src = url.href;
    script.onerror = () => reject(new Error('Google Maps could not be reached. Check your internet connection.'));
    document.head.append(script);
  });
}

async function init() {
  $('#retry').onclick = () => location.reload();
  window.gm_authFailure = () => message('Google could not accept this key',
    'Check that the Demo Key supports Maps JavaScript API and that its daily quota is available. If you set website restrictions, allow this localhost address, then reload.');
  try {
    const response = await fetch('config.json', {cache:'no-store'});
    config = await response.json();
    if (!response.ok) throw new Error('The preview configuration could not be loaded. Check the study and Google preview configuration files.');
    if (!config.configured) {
      message('Add your Google Demo Key', 'Save this line in the project’s .env file:\nGOOGLE_MAPS_API_KEY=your_key_here\n\nThen choose Check again.', 'missing-key');
      return;
    }
    status('Connecting to Google 3D…', 'loading');
    loadTimer = setTimeout(() => {
      if (!firstRender && state.phase !== 'error') status('Google is still loading the 3D scene. Please wait…', 'loading');
    }, 45000);
    await loadGoogle(config.apiKey);
    config.apiKey = undefined;
    if (state.phase === 'error') return;
    const {Map3DElement} = await google.maps.importLibrary('maps3d');
    map = new Map3DElement({
      ...config.views.overview, mode:'SATELLITE', bounds:config.bounds,
      minAltitude:20, maxAltitude:config.navigation.max_altitude_m,
      maxTilt:config.navigation.max_tilt_deg,
      description:'Interactive Google 3D preview limited to the Toronto Zoo GIS study area'
    });
    for (const event of ['gmp-centerchange', 'gmp-rangechange']) {
      map.addEventListener(event, scheduleCameraConstraint);
    }
    map.addEventListener('gmp-error', () => message('The Google 3D map could not initialize',
      'Try a current browser with WebGL enabled. Also check that your Google key is valid and has quota available, then reload.'));
    map.addEventListener('gmp-steadychange', e => {
      state.steady = Boolean(e.isSteady);
      if (e.isSteady && state.phase !== 'error') {
        firstRender = true;
        clearTimeout(loadTimer);
        status('Google 3D · Toronto Zoo', 'ready');
        document.querySelectorAll('.panel button, .panel input').forEach(e => e.disabled = false);
        constrainCamera();
      }
    });
    map.addEventListener('gmp-animationend', () => setOrbitButton(false));
    $('#map').append(map);
    activeView('overview');
    document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => navigate(b.dataset.view));
    $('#reset').onclick = () => navigate('overview');
    $('#zoom-in').onclick = () => zoom(.75);
    $('#zoom-out').onclick = () => zoom(1.33);
    $('#labels').onchange = e => map.mode = e.target.checked ? 'HYBRID' : 'SATELLITE';
    $('#orbit').onclick = async () => {
      if (orbiting) { await stopOrbit(); return; }
      await map.stopCameraAnimation();
      await map.flyCameraAround({camera:{center:map.center,range:map.range,tilt:map.tilt,heading:map.heading},durationMillis:45000,repeatCount:1});
      setOrbitButton(true);
    };
    // Expose only camera and loading state for local verification, never the key.
    window.googleZoo = {navigate, snapshot:() => ({...state, orbiting,
      labels:$('#labels').checked, center:map.center?.toJSON?.() ?? map.center,
      cameraPosition:map.cameraPosition?.toJSON?.() ?? map.cameraPosition,
      range:map.range,tilt:map.tilt,heading:map.heading})};
  } catch (error) {
    message('Could not open Google 3D', error.message?.includes('internet connection')
      ? 'Google Maps could not be reached. Check your internet connection, then reload.'
      : 'Check the local preview configuration and Google key, then reload. Your key is never shown in this page.');
  }
}
init();
