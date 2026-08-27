"use client";

import { useEffect, useRef, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";
import { cellToBoundary } from "h3-js";
import type { ActivityCell } from "../../types/city";

type MapCell = ActivityCell | { h3_cell: string; total_journeys: number };
type MapPlace = { place_id: string; name?: string; latitude: number; longitude: number; maps_uri?: string };
export type FocusedMapPlace = { place_id: string; name: string; latitude: number; longitude: number; maps_uri?: string };
type Route = NonNullable<import("../../types/investigation").InvestigationResult["route"]>;

type CityMapProps = {
  cells: MapCell[];
  places?: MapPlace[];
  focusedPlace?: FocusedMapPlace | null;
  route?: Route;
  selectedH3Cell?: string | null;
  onSelectH3Cell?: (h3Cell: string) => void;
  onSelectPlace?: (place: FocusedMapPlace) => void;
  cityName?: string;
  bounds?: [number, number, number, number];
  ariaLabel?: string;
};

export function CityMap({ cells, places = [], focusedPlace, route, selectedH3Cell, onSelectH3Cell, onSelectPlace, cityName = "London", bounds = [51.28, -0.52, 51.72, 0.34], ariaLabel }: CityMapProps) {
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    if (!node.current || !key) return;
    let cancelled = false;
    const cleanups: (() => void)[] = [];
    const loader = new Loader({ apiKey: key, version: "weekly", libraries: ["geometry", "places"] });
    loader.load().then((google) => {
      if (!node.current || cancelled) return;
      map.current = new google.maps.Map(node.current, {
        center: { lat: (bounds[0] + bounds[2]) / 2, lng: (bounds[1] + bounds[3]) / 2 },
        zoom: 12,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        restriction: { latLngBounds: { north: bounds[2], south: bounds[0], west: bounds[1], east: bounds[3] }, strictBounds: false },
      });
      const max = Math.max(...cells.map((cell) => cell.total_journeys), 1);
      const polygons = cells.map((cell) => {
        const path = cellToBoundary(cell.h3_cell).map(([lat, lng]) => ({ lat, lng }));
        const selected = cell.h3_cell === selectedH3Cell;
        const polygon = new google.maps.Polygon({
          paths: path,
          map: map.current,
          strokeColor: selected ? "#0b57d0" : "#137333",
          strokeOpacity: 0.9,
          strokeWeight: selected ? 3 : 1,
          fillColor: selected ? "#4285f4" : "#34a853",
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
          title: place.name ?? "Google Maps place",
          icon: { path: google.maps.SymbolPath.CIRCLE, scale: 6, fillColor: "#f9ab00", fillOpacity: 1, strokeColor: "#ffffff", strokeWeight: 2 },
        });
        marker.addListener("click", () => {
          onSelectPlace?.({ place_id: place.place_id, name: place.name ?? "Google Maps place", latitude: place.latitude, longitude: place.longitude, maps_uri: place.maps_uri });
          const content = document.createElement("div");
          const label = place.name ?? "Google Maps place";
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
      const focusedMarker = focusedPlace ? new google.maps.Marker({
        position: { lat: focusedPlace.latitude, lng: focusedPlace.longitude },
        map: map.current,
        title: focusedPlace.name,
        animation: google.maps.Animation.DROP,
      }) : null;
      if (focusedPlace) {
        map.current.panTo({ lat: focusedPlace.latitude, lng: focusedPlace.longitude });
        map.current.setZoom(15);
      }
      const decodedRoute = route ? google.maps.geometry.encoding.decodePath(route.polyline) : [];
      const routeLine = route ? new google.maps.Polyline({ path: decodedRoute, map: map.current, strokeColor: "#1a73e8", strokeOpacity: 0.95, strokeWeight: 5 }) : null;
      const routeMarkers = route ? [route.origin, route.destination, ...route.waypoints].map((point, index) => new google.maps.Marker({ position: { lat: point.latitude, lng: point.longitude }, map: map.current, title: "name" in point ? point.name : `Historical activity waypoint ${index}`, icon: { path: google.maps.SymbolPath.CIRCLE, scale: index < 2 ? 8 : 6, fillColor: index === 0 ? "#34a853" : index === 1 ? "#ea4335" : "#f9ab00", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 } })) : [];
      if (route && decodedRoute.length > 0) {
        const bounds = new google.maps.LatLngBounds();
        decodedRoute.forEach((point) => bounds.extend(point));
        map.current.fitBounds(bounds, 56);
      }
      cleanups.push(() => { polygons.forEach((polygon) => polygon.setMap(null)); markers.forEach((marker) => marker.setMap(null)); focusedMarker?.setMap(null); routeMarkers.forEach((marker) => marker.setMap(null)); routeLine?.setMap(null); infoWindow.close(); });
    }).catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; cleanups.forEach((cleanup) => cleanup()); };
  }, [cells, places, focusedPlace, route, selectedH3Cell, onSelectH3Cell, onSelectPlace, cityName, bounds]);

  if (!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) {
    return <div className="map-placeholder" role="img" aria-label="Google Maps preview unavailable until a browser API key is configured">Google Maps preview requires NEXT_PUBLIC_GOOGLE_MAPS_API_KEY. The ranked activity values remain available beside this panel.</div>;
  }
  if (loadError) return <div className="map-placeholder" role="alert"><strong>Google Maps could not be loaded.</strong><span>The activity ranking and investigation evidence remain available in text.</span></div>;
  return <div ref={node} className="map" aria-label={ariaLabel ?? `${cityName} cycling activity map`} />;
}
