import { mapToLonLat } from "../../util/geo.js";
import { SOLAR_LIMITS, positionFromParameters } from "../../util/solar.js";

const STEP_KM = 16;
const NIGHT_ALPHA = 0.39;

// One sample per 16 km, then smooth between samples. The map renderer can
// reuse this tiny image at any zoom without running the solar calculation.
export function daylightLayer(projection, { width, height }, parameters) {
  let raster, ctx, pixels, locations, painted;
  function paint(p) {
    if (!raster) {
      raster = document.createElement("canvas");
      raster.width = Math.ceil(width / STEP_KM);
      raster.height = Math.ceil(height / STEP_KM);
      ctx = raster.getContext("2d");
      pixels = ctx.createImageData(raster.width, raster.height);
      locations = [];
      for (let y = 0; y < raster.height; y++) {
        for (let x = 0; x < raster.width; x++) {
          locations.push(mapToLonLat(projection, (x + 0.5) * width / raster.width, (y + 0.5) * height / raster.height));
        }
      }
    }
    const { sunrise, astronomical } = SOLAR_LIMITS;
    const span = sunrise - astronomical;
    for (let i = 0; i < locations.length; i++) {
      const { lat, lon } = locations[i];
      const { elevation } = positionFromParameters(p, lat, lon);
      const twilight = Math.max(0, Math.min(1, (sunrise - elevation) / span));
      const k = i * 4;
      pixels.data[k] = 20;
      pixels.data[k + 1] = 33;
      pixels.data[k + 2] = 58;
      pixels.data[k + 3] = Math.round(255 * NIGHT_ALPHA * twilight * (2 - twilight));
    }
    ctx.putImageData(pixels, 0, 0);
    painted = p.ms;
  }

  return {
    id: "daylight",
    z: 45, // Above landscape art, below rivers, borders, markers and labels.
    visible: () => parameters() !== null,
    sig: () => parameters()?.ms,
    draw(target, vp, w, { lens }) {
      const p = parameters();
      if (!p) return;
      if (painted !== p.ms) paint(p);
      target.globalAlpha = lens ? 0.5 : 1;
      target.imageSmoothingEnabled = true;
      target.drawImage(raster, 0, 0, width, height);
    },
  };
}
