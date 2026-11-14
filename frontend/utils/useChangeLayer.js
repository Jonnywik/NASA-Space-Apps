// frontend/utils/useChangeLayer.js
"use client";

import { useEffect, useState } from "react";
import {
  categoryColor,
  featureLabel,
  filterChangeFeatures,
  hasCategoryData,
  lossColor,
} from "./changeFilter";

export default function useChangeLayer({
  mapRef,
  leafletRef,
  mapReady,
  geojson,
  visible,
  minLoss,
  minArea = 0,
  activeCategories = null,
}) {
  const [counts, setCounts] = useState({
    total: 0,
    shown: 0,
    hasCategories: false,
  });

  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L) return undefined;

    const all = geojson?.features ?? [];
    const hasCats = hasCategoryData(all);
    const kept = filterChangeFeatures(
      all,
      minLoss,
      minArea,
      hasCats ? activeCategories : null,
    );
    setCounts({
      total: all.length,
      shown: kept.length,
      hasCategories: hasCats,
    });

    if (!visible || kept.length === 0) return undefined;

    if (!map.getPane("changePane"))
      map.createPane("changePane").style.zIndex = 430;

    const layer = L.geoJSON(
      { type: "FeatureCollection", features: kept },
      {
        pane: "changePane",
        style: (feature) => {
          const c =
            hasCats && feature?.properties?.category
              ? categoryColor(feature.properties.category)
              : lossColor(feature?.properties?.meanLoss);
          return { color: c, weight: 1.5, fillColor: c, fillOpacity: 0.5 };
        },
        onEachFeature: (feature, l) =>
          l.bindTooltip(featureLabel(feature), { sticky: true }),
      },
    ).addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [
    mapRef,
    leafletRef,
    mapReady,
    geojson,
    visible,
    minLoss,
    minArea,
    activeCategories,
  ]);

  return counts;
}
