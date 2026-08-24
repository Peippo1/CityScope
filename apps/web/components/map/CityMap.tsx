"use client";

import { useEffect, useRef, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";
import { cellToBoundary } from "h3-js";
import type { ActivityCell } from "../../types/city";

type MapCell = ActivityCell | { h3_cell: string; total_journeys: number };
type MapPlace = { place_id: string; name?: string; latitude: number; longitude: number; maps_uri?: string };
type Route = NonNullable<import("../../types/investigation").InvestigationResult["route"]>;

type CityMapProps = {
  cells: MapCell[];
  places?: MapPlace[];
  route?: Route;
  selectedH3Cell?: string | null;
  onSelectH3Cell?: (h3Cell: string) => void;
};

export function CityMap({ cells, places = [], route, selectedH3Cell, onSelectH3Cell }: CityMapProps) {
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    if (!node.current || !key) return;
    let cancelled = false;
    const cleanups: (() => void)[] = [];
    const loader = new Loader({ apiKey: key, version: "weekly", libraries: ["geometry"] });
    loader.load().then((google) => {
      if (!node.current || cancelled) return;
      map.current = new google.maps.Map(node.current, {
        center: { lat: 51.5074, lng: -0.1278 },
        zoom: 12,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        restriction: { latLngBounds: { north: 51.72, south: 51.28, west: -0.52, east: 0.34 }, strictBounds: false },
      });
      const max = Math.max(...cells.map((cell) => cell.total_journeys), 1);
      const polygons = cells.map((cell) => {
        const path = cellToBoundary(cell.h3_cell).map(([lat, lng]) => ({ lat, lng }));
        const selected = cell.h3_cell === selectedH3Cell;
        const polygon = new google.maps.Polygon({
          paths: path,
          map: map.current,
          strokeColor: selected ? "#1d4ed8" : "#0f766e",
          strokeOpacity: 0.9,
          strokeWeight: selected ? 3 : 1,
          fillColor: selected ? "#2563eb" : "#14b8a6",
          fillOpacity: Math.min(0.82, 0.22 + 0.56 * (cell.total_journeys / max)),
        });
        polygon.addListener("click", () => onSelectH3Cell?.(cell.h3_cell));
        return polygon;
      });
      const infoWindow = new google.maps.InfoWindow();
      const markers = places.map((place) => {
        const marker = new google.maps.Marker({
          position: { lat: place.latitude, lng: place.longitude },
          map: map.current,
          title: place.name ?? place.place_id,
          icon: { path: google.maps.SymbolPath.CIRCLE, scale: 6, fillColor: "#b45309", fillOpacity: 1, strokeColor: "#ffffff", strokeWeight: 2 },
        });
        marker.addListener("click", () => {
          const content = document.createElement("div");
          const label = place.name ?? place.place_id;
          if (place.maps_uri) {
            const link = document.createElement("a");
            link.href = place.maps_uri;
            link.target = "_blank";
            link.rel = "noreferrer";
            link.textContent = label;
            content.append(link);
          } else {
            content.textContent = label;
          }
          infoWindow.setContent(content);
          infoWindow.open({ map: map.current, anchor: marker });
        });
        return marker;
      });
      const decodedRoute = route ? google.maps.geometry.encoding.decodePath(route.polyline) : [];
      const routeLine = route ? new google.maps.Polyline({ path: decodedRoute, map: map.current, strokeColor: "#2563eb", strokeOpacity: 0.95, strokeWeight: 5 }) : null;
      const routeMarkers = route ? [route.origin, route.destination, ...route.waypoints].map((point, index) => new google.maps.Marker({ position: { lat: point.latitude, lng: point.longitude }, map: map.current, title: "name" in point ? point.name : `Historical activity waypoint ${index}`, icon: { path: google.maps.SymbolPath.CIRCLE, scale: index < 2 ? 8 : 6, fillColor: index === 0 ? "#15803d" : index === 1 ? "#b91c1c" : "#7c3aed", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 } })) : [];
      if (route && decodedRoute.length > 0) {
        const bounds = new google.maps.LatLngBounds();
        decodedRoute.forEach((point) => bounds.extend(point));
        map.current.fitBounds(bounds, 56);
      }
      cleanups.push(() => { polygons.forEach((polygon) => polygon.setMap(null)); markers.forEach((marker) => marker.setMap(null)); routeMarkers.forEach((marker) => marker.setMap(null)); routeLine?.setMap(null); infoWindow.close(); });
    }).catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; cleanups.forEach((cleanup) => cleanup()); };
  }, [cells, places, route, selectedH3Cell, onSelectH3Cell]);

  if (!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) {
    return <div className="map-placeholder" role="img" aria-label="Google Maps preview unavailable until a browser API key is configured">Google Maps preview requires NEXT_PUBLIC_GOOGLE_MAPS_API_KEY. The ranked activity values remain available beside this panel.</div>;
  }
  if (loadError) return <div className="map-placeholder" role="alert"><strong>Google Maps could not be loaded.</strong><span>The activity ranking and investigation evidence remain available in text.</span></div>;
  return <div ref={node} className="map" aria-label="London cycling activity map" />;
}
