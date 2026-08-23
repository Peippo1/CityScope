"use client";

import { useEffect, useRef } from "react";
import { Loader } from "@googlemaps/js-api-loader";
import { cellToBoundary } from "h3-js";
import type { ActivityCell } from "../../types/city";

type MapCell = ActivityCell | { h3_cell: string; total_journeys: number };
type MapPlace = { place_id: string; name?: string; latitude: number; longitude: number; maps_uri?: string };
type Route = NonNullable<import("../../types/investigation").InvestigationResult["route"]>;

export function CityMap({ cells, places = [], route }: { cells: MapCell[]; places?: MapPlace[]; route?: Route }) {
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    if (!node.current || !key) return;
    const loader = new Loader({ apiKey: key, version: "weekly", libraries: ["geometry"] });
    loader.load().then((google) => {
      if (!node.current) return;
      map.current = new google.maps.Map(node.current, {
        center: { lat: 51.5074, lng: -0.1278 },
        zoom: 12,
        mapTypeControl: false,
        streetViewControl: false,
      });
      const max = Math.max(...cells.map((cell) => cell.total_journeys), 1);
      const polygons = cells.map((cell) => {
        const path = cellToBoundary(cell.h3_cell).map(([lat, lng]) => ({ lat, lng }));
        return new google.maps.Polygon({
          paths: path,
          map: map.current,
          strokeColor: "#0f766e",
          strokeOpacity: 0.8,
          strokeWeight: 1,
          fillColor: "#14b8a6",
          fillOpacity: 0.2 + 0.65 * (cell.total_journeys / max),
        });
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
      const routeLine = route ? new google.maps.Polyline({ path: google.maps.geometry.encoding.decodePath(route.polyline), map: map.current, strokeColor: "#2563eb", strokeOpacity: 0.9, strokeWeight: 5 }) : null;
      const routeMarkers = route ? [route.origin, route.destination, ...route.waypoints].map((point, index) => new google.maps.Marker({ position: { lat: point.latitude, lng: point.longitude }, map: map.current, title: "name" in point ? point.name : `Historical activity waypoint ${index}`, icon: { path: google.maps.SymbolPath.CIRCLE, scale: index < 2 ? 8 : 6, fillColor: index === 0 ? "#15803d" : index === 1 ? "#b91c1c" : "#7c3aed", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 } })) : [];
      return () => { polygons.forEach((polygon) => polygon.setMap(null)); markers.forEach((marker) => marker.setMap(null)); routeMarkers.forEach((marker) => marker.setMap(null)); routeLine?.setMap(null); infoWindow.close(); };
    });
  }, [cells, places, route]);

  if (!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) {
    return <div className="map-placeholder" role="img" aria-label="Google Maps preview unavailable until a browser API key is configured">Google Maps preview requires NEXT_PUBLIC_GOOGLE_MAPS_API_KEY. The ranked activity values remain available beside this panel.</div>;
  }
  return <div ref={node} className="map" aria-label="London cycling activity map" />;
}
