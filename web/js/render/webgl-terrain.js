// Optional WebGL terrain surface. The source remains one elevation value per map hex.
export const TERRAIN_LAYER_TYPES = Object.freeze([
  "elevation", "vegetation", "buildings", "agriculture", "infrastructure",
]);
export const VERTICAL_EXAGGERATION = 2.5;

const VERTEX_SHADER = `#version 300 es
in vec3 a_position;
in vec3 a_color;
in float a_shade;
uniform vec4 u_view; // x0, y0, css width, css height
uniform vec3 u_camera; // horizontal scale, vertical scale, vertical exaggeration
uniform vec2 u_pitch; // cosine, sine
out vec3 v_color;
out float v_shade;
void main() {
  float x = (a_position.x - u_view.x) * u_camera.x;
  float y = (a_position.y - u_view.y) * u_camera.y - a_position.z * u_camera.x * u_camera.z * u_pitch.y;
  float depth = (a_position.y - u_view.y) * u_pitch.y - a_position.z * u_camera.z * u_pitch.x;
  float depthRange = u_view.w / u_camera.y;
  gl_Position = vec4(2.0 * x / u_view.z - 1.0, 1.0 - 2.0 * y / u_view.w, 2.0 * depth / depthRange - 1.0, 1.0);
  v_color = a_color;
  v_shade = a_shade;
}`;

const FRAGMENT_SHADER = `#version 300 es
precision mediump float;
in vec3 v_color;
in float v_shade;
out vec4 out_color;
void main() {
  out_color = vec4(v_color * v_shade, 0.38);
}`;

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("could not create a WebGL shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) || "unknown shader error";
    gl.deleteShader(shader);
    throw new Error(`could not compile WebGL terrain shader: ${message}`);
  }
  return shader;
}

function createProgram(gl) {
  const vertex = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!program) throw new Error("could not create a WebGL terrain program");
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const message = gl.getProgramInfoLog(program) || "unknown program error";
    gl.deleteProgram(program);
    throw new Error(`could not link WebGL terrain program: ${message}`);
  }
  return program;
}

function landHeight(world, cell) {
  if (world.water[cell]) return 0;
  const elevation = world.raw.elev[cell];
  if (!Number.isFinite(elevation)) throw new TypeError(`terrain elevation ${cell} is not finite`);
  return elevation / 1000;
}

function cornerHeight(world, cell, direction) {
  const adjacent = world.grid.neighbour(cell, direction);
  const previous = world.grid.neighbour(cell, (direction + 5) % 6);
  return (landHeight(world, cell) + (adjacent < 0 ? landHeight(world, cell) : landHeight(world, adjacent)) +
    (previous < 0 ? landHeight(world, cell) : landHeight(world, previous))) / 3;
}

export function terrainElevationAt(world, x, y) {
  const cell = world.grid.cellAt(x, y);
  if (cell < 0 || world.water[cell]) return 0;
  const cx = world.grid.cx(cell), cy = world.grid.cy(cell);
  const centerHeight = landHeight(world, cell) * 1000;
  for (let d = 0; d < 6; d++) {
    const [ax, ay] = world.grid.corners[d];
    const [bx, by] = world.grid.corners[(d + 1) % 6];
    const det = ax * by - ay * bx;
    const u = ((x - cx) * by - (y - cy) * bx) / det;
    const v = (ax * (y - cy) - ay * (x - cx)) / det;
    if (u >= -1e-8 && v >= -1e-8 && u + v <= 1 + 1e-8) {
      const hA = cornerHeight(world, cell, d) * 1000;
      const hB = cornerHeight(world, cell, (d + 1) % 6) * 1000;
      return centerHeight * (1 - u - v) + hA * u + hB * v;
    }
  }
  return centerHeight;
}

function terrainShade(world, cell, verticalExaggeration) {
  const { grid } = world;
  const x = grid.cx(cell), y = grid.cy(cell), z = landHeight(world, cell);
  let xx = 0, xy = 0, yy = 0, xz = 0, yz = 0;
  for (let d = 0; d < 6; d++) {
    const neighbour = grid.neighbour(cell, d);
    if (neighbour < 0 || world.water[neighbour]) continue;
    const dx = grid.cx(neighbour) - x, dy = grid.cy(neighbour) - y;
    const dz = (landHeight(world, neighbour) - z) * verticalExaggeration;
    xx += dx * dx;
    xy += dx * dy;
    yy += dy * dy;
    xz += dx * dz;
    yz += dy * dz;
  }
  const det = xx * yy - xy * xy;
  const gx = det ? (xz * yy - yz * xy) / det : 0;
  const gy = det ? (yz * xx - xz * xy) / det : 0;
  const inv = 1 / Math.hypot(gx, gy, 1);
  const facing = Math.max(0, (-gx * -0.45 - gy * -0.55 + inv * 0.72) * inv);
  return 0.75 + 0.45 * facing;
}

export function projectTerrainPoint(view, x, y, elevationM = 0, pitch = 0, verticalExaggeration = VERTICAL_EXAGGERATION) {
  const radians = (pitch * Math.PI) / 180;
  const px = (x - view.x0) * view.s;
  const py = (y - view.y0) * (view.yScale ?? view.s) -
    (elevationM / 1000) * verticalExaggeration * view.s * Math.sin(radians);
  return [2 * px / view.cssW - 1, 1 - 2 * py / view.cssH];
}

/** Build a triangle fan for each land hex, with corner heights shared across the three touching samples. */
export function buildTerrainMesh(world) {
  const { grid, raw } = world || {};
  if (!grid || !raw || !Array.isArray(raw.elev) || raw.elev.length !== grid.size ||
      !world.water || world.water.length !== grid.size) {
    throw new TypeError("terrain mesh requires a prepared world with one elevation and water value per hex");
  }
  const cells = [];
  for (let i = 0; i < grid.size; i++) if (!world.water[i]) cells.push(i);
  const positions = new Float32Array(cells.length * 7 * 3);
  const colors = new Uint8Array(cells.length * 7 * 3);
  const shades = new Float32Array(cells.length * 7);
  const indices = new Uint32Array(cells.length * 18);
  let vertex = 0, index = 0;
  for (const cell of cells) {
    const x = grid.cx(cell), y = grid.cy(cell);
    const color = world.terrainColors?.[cell] || [125, 151, 92];
    const shade = terrainShade(world, cell, VERTICAL_EXAGGERATION);
    const put = (px, py, z) => {
      positions[vertex * 3] = px;
      positions[vertex * 3 + 1] = py;
      positions[vertex * 3 + 2] = z;
      colors[vertex * 3] = color[0];
      colors[vertex * 3 + 1] = color[1];
      colors[vertex * 3 + 2] = color[2];
      shades[vertex] = shade;
      return vertex++;
    };
    const center = put(x, y, landHeight(world, cell));
    const corners = [];
    for (let d = 0; d < 6; d++) {
      const a = grid.neighbour(cell, d), b = grid.neighbour(cell, (d + 5) % 6);
      const z = cornerHeight(world, cell, d);
      const [cx, cy] = grid.corners[d];
      corners.push(put(x + cx, y + cy, z));
    }
    for (let d = 0; d < 6; d++) {
      indices[index++] = center;
      indices[index++] = corners[d];
      indices[index++] = corners[(d + 1) % 6];
    }
  }
  return {
    positions, colors, shades, indices, cells: cells.length,
    vertices: vertex, triangles: index / 3, hexRadiusKm: grid.R,
  };
}

export class WebGLTerrainRenderer {
  constructor(world, { onUnavailable = null } = {}) {
    this.canvas = document.createElement("canvas");
    this.available = false;
    this.error = null;
    this.onUnavailable = onUnavailable;
    this.layers = new Map();
    this.uploadMs = 0;
    this.submissionMs = [];
    let gl = null;
    try {
      gl = this.canvas.getContext("webgl2", {
        alpha: true, antialias: false, depth: true, stencil: false, premultipliedAlpha: false,
      });
    } catch (error) {
      this.error = error;
    }
    if (!gl) {
      this.error ||= new Error("WebGL 2 is not available");
      return;
    }
    this.gl = gl;
    try {
      this.mesh = buildTerrainMesh(world);
      this.program = createProgram(gl);
      this.positionBuffer = gl.createBuffer();
      this.colorBuffer = gl.createBuffer();
      this.shadeBuffer = gl.createBuffer();
      this.indexBuffer = gl.createBuffer();
      if (!this.positionBuffer || !this.colorBuffer || !this.shadeBuffer || !this.indexBuffer) throw new Error("could not create WebGL terrain buffers");
      const t0 = performance.now();
      gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, this.mesh.positions, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, this.mesh.colors, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.shadeBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, this.mesh.shades, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indexBuffer);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, this.mesh.indices, gl.STATIC_DRAW);
      this.uploadMs = performance.now() - t0;
      this.locations = {
        position: gl.getAttribLocation(this.program, "a_position"),
        color: gl.getAttribLocation(this.program, "a_color"),
        shade: gl.getAttribLocation(this.program, "a_shade"),
        view: gl.getUniformLocation(this.program, "u_view"),
        camera: gl.getUniformLocation(this.program, "u_camera"),
        pitch: gl.getUniformLocation(this.program, "u_pitch"),
      };
      this.available = true;
      this.canvas.addEventListener("webglcontextlost", (event) => {
        event.preventDefault();
        this.disable(new Error("WebGL context was lost"));
      });
    } catch (error) {
      this.disable(error);
    }
  }

  disable(error) {
    this.available = false;
    this.error = error;
    this.onUnavailable?.(error);
  }

  registerLayer(layer) {
    if (!this.available) throw new Error("WebGL terrain layers need an active WebGL 2 renderer");
    if (!layer || typeof layer.id !== "string" || !layer.id || !TERRAIN_LAYER_TYPES.includes(layer.type) ||
        typeof layer.draw !== "function") {
      throw new TypeError(`terrain layer must provide an id, a supported type (${TERRAIN_LAYER_TYPES.join(", ")}), and draw(gl, frame)`);
    }
    this.layers.set(layer.id, layer);
    return () => this.layers.delete(layer.id);
  }

  draw(ctx, vp, world, pitch = 0) {
    const gl = this.gl;
    if (!this.available || gl.isContextLost()) {
      if (this.available) this.disable(new Error("WebGL context was lost"));
      return false;
    }
    const width = Math.max(1, Math.ceil(vp.cssW * vp.dpr));
    const height = Math.max(1, Math.ceil(vp.cssH * vp.dpr));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    try {
      const t0 = performance.now();
      gl.viewport(0, 0, width, height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.useProgram(this.program);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
      gl.enableVertexAttribArray(this.locations.position);
      gl.vertexAttribPointer(this.locations.position, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.enableVertexAttribArray(this.locations.color);
      gl.vertexAttribPointer(this.locations.color, 3, gl.UNSIGNED_BYTE, true, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.shadeBuffer);
      gl.enableVertexAttribArray(this.locations.shade);
      gl.vertexAttribPointer(this.locations.shade, 1, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indexBuffer);
      const radians = (pitch * Math.PI) / 180;
      gl.uniform4f(this.locations.view, vp.x0, vp.y0, vp.cssW, vp.cssH);
      gl.uniform3f(this.locations.camera, vp.s, vp.yScale ?? vp.s, VERTICAL_EXAGGERATION);
      gl.uniform2f(this.locations.pitch, Math.cos(radians), Math.sin(radians));
      gl.enable(gl.DEPTH_TEST);
      gl.depthFunc(gl.LEQUAL);
      gl.drawElements(gl.TRIANGLES, this.mesh.indices.length, gl.UNSIGNED_INT, 0);
      const frame = { world, view: vp, pitch, scale: vp.s, verticalExaggeration: VERTICAL_EXAGGERATION,
        project: (x, y, elevationM = 0) => projectTerrainPoint(vp, x, y, elevationM, pitch) };
      for (const [id, layer] of this.layers) {
        try {
          layer.draw(gl, frame);
        } catch (error) {
          this.layers.delete(id);
          console.error(`terrain layer "${id}" failed and was removed`, error);
        }
      }
      this.submissionMs.push(performance.now() - t0);
      if (this.submissionMs.length > 60) this.submissionMs.shift();
      ctx.save();
      try {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.drawImage(this.canvas, 0, 0);
      } finally {
        ctx.restore();
      }
      return true;
    } catch (error) {
      this.disable(error);
      return false;
    }
  }

  stats() {
    const sorted = [...this.submissionMs].sort((a, b) => a - b);
    return {
      available: this.available, error: this.error?.message || null,
      hexRadiusKm: this.mesh?.hexRadiusKm ?? null, verticalExaggeration: VERTICAL_EXAGGERATION, cells: this.mesh?.cells ?? 0,
      triangles: this.mesh?.triangles ?? 0, uploadMs: +this.uploadMs.toFixed(2),
      submissionMedianMs: sorted.length ? +sorted[sorted.length >> 1].toFixed(2) : null,
      submissionSamples: sorted.length,
    };
  }
}
