// frontend/utils/api.js  -  the only place that talks to the Tanaw backend.
// The backend must be running:  uvicorn app.main:app --reload   (inside backend/)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// List of events: [{ id, name, aoi, beforeDate, afterDate, ready }, ...]
export async function getEvents() {
  const res = await fetch(`${API_BASE}/api/v1/events`);
  if (!res.ok) throw new Error(`Could not load events (HTTP ${res.status})`);
  return res.json();
}

// One event. Same shape as mockFloodData, plus:
//   floodGeojson          -> draw this on the map (red flood shapes)
//   overlays              -> null, or { beforeUrl, afterUrl, bounds } for the slider
//                            bounds = [[south, west], [north, east]]  (Leaflet order)
export async function getFloodExtent(eventId) {
  const res = await fetch(
    `${API_BASE}/api/v1/flood-extent?event=${encodeURIComponent(eventId)}`
  );
  if (!res.ok) throw new Error(`Could not load "${eventId}" (HTTP ${res.status})`);
  const data = await res.json();

  // the backend sends picture addresses without the server name; add it here
  if (data.overlays) {
    data.overlays.beforeUrl = API_BASE + data.overlays.beforeUrl;
    data.overlays.afterUrl = API_BASE + data.overlays.afterUrl;
  }
  return data;
}

// Example (inside a client component, "use client" at the top of the file):
//
//   const [events, setEvents] = useState([]);
//   const [data, setData] = useState(null);
//   useEffect(() => { getEvents().then(setEvents); }, []);
//   useEffect(() => { getFloodExtent("karding_2022").then(setData).catch(console.error); }, []);
//
// In the sidebar, show a dash for numbers that are still null:
//   {data.stats.peopleExposed ?? "—"}
