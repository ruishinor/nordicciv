// Shared geographic surface interface for terrain meshes and future surface layers.
// Horizontal coordinates use the app's Nordic LAEA map frame in kilometres; heights are metres.
export const SURFACE_CONTRACT_VERSION = 1;
export const SURFACE_LOD_LIMITS_KM = Object.freeze([100, 30, 10, 2]);
export const SURFACE_LOD = Object.freeze({
  OVERVIEW: "overview",
  REGIONAL: "regional",
  LOCAL: "local",
  NEIGHBOURHOOD: "neighbourhood",
  CLOSE: "close",
});

export function physicalLodForWidth(widthKm) {
  if (!Number.isFinite(widthKm) || widthKm <= 0) return SURFACE_LOD.OVERVIEW;
  if (widthKm > 100) return SURFACE_LOD.OVERVIEW;
  if (widthKm > 30) return SURFACE_LOD.REGIONAL;
  if (widthKm > 10) return SURFACE_LOD.LOCAL;
  if (widthKm > 2) return SURFACE_LOD.NEIGHBOURHOOD;
  return SURFACE_LOD.CLOSE;
}

// Keep the finest published terrain level at 30 m. Close views do not imply finer source data.
export function terrainLevelForWidth(widthKm) {
  if (!Number.isFinite(widthKm) || widthKm <= 0 || widthKm > 100) return -1;
  if (widthKm > 30) return 0;
  if (widthKm > 10) return 1;
  return 2;
}

export function legacySettlementRadiusKm(hexRadiusKm, scale, maxRadiusPx = 18) {
  if (!(hexRadiusKm > 0) || !(scale > 0) || !(maxRadiusPx > 0)) return 0;
  return Math.min(hexRadiusKm, maxRadiusPx / scale);
}

export function legacySettlementPosition(city, hexCenter, close = false) {
  if (close && Number.isFinite(city?.x) && Number.isFinite(city?.y)) return [city.x, city.y];
  return [hexCenter.x, hexCenter.y];
}

export function canPlaceLegacySettlement(cell, water) {
  return Number.isInteger(cell) && cell >= 0 && !!water && cell < water.length && !water[cell];
}

export function createSurfaceContract({ projection, widthKm, sample, project }) {
  if (typeof sample !== "function" || typeof project !== "function") {
    throw new TypeError("surface contract requires sample(x, y) and project(x, y, elevationM)");
  }
  const contract = {
    version: SURFACE_CONTRACT_VERSION,
    projection: projection ?? null,
    horizontalUnit: "km",
    verticalUnit: "m",
    widthKm,
    lod: physicalLodForWidth(widthKm),
    sample(x, y) {
      const value = sample(x, y);
      return {
        elevationM: Number.isFinite(value?.elevationM) ? value.elevationM : 0,
        coverage: Number.isFinite(value?.coverage) ? Math.min(1, Math.max(0, value.coverage)) : 0,
        water: value?.water === true,
      };
    },
    project(x, y, elevationM) {
      const z = Number.isFinite(elevationM) ? elevationM : contract.sample(x, y).elevationM;
      return project(x, y, z);
    },
  };
  return Object.freeze(contract);
}
