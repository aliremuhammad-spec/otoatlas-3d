/**
 * Ray-marched true-colour volume view (WebGL 2), the renderer of the surgical view.
 * Ported from the Gate 0 speed test (public/dev/raymarch.html) into the app: one fragment shader marches
 * each pixel's ray through a 3D colour texture, lit by a headlight using normals made from the CBCT.
 * No structure labels yet: show, hide and tint by structure come with the label volume.
 */

export class NoWebGL2Error extends Error {
  constructor() {
    super('WebGL 2 is not available');
    this.name = 'NoWebGL2Error';
  }
}

type V3 = readonly [number, number, number];

export interface VolumeData {
  dims: V3;
  spacingMm: number;
  /** Centre of the first voxel in the specimen frame, mm. */
  originMm: V3;
  /** RGBA bytes, x fastest, then y, then z. */
  rgba: Uint8Array;
}

export interface RenderOptions {
  translucent: boolean;
  /** 0 to 0.8: fraction of the way into the block where rays start. */
  cut: number;
  /** Fraction of the device pixels used on each side. */
  renderScale: number;
}

const VS = `#version 300 es
void main() { vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }`;

const FS = `#version 300 es
precision highp float; precision highp sampler3D;
uniform sampler3D uCol; uniform sampler3D uNrm; uniform sampler3D uOcc;
uniform vec3 uBoxMin, uBoxSize, uNMin, uNSize, uCam;
uniform mat4 uInvVP; uniform vec2 uRes; uniform float uStep, uMode, uCut;
out vec4 o;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  vec2 ndc = gl_FragCoord.xy / uRes * 2.0 - 1.0;
  vec4 f = uInvVP * vec4(ndc, 1.0, 1.0); vec3 far = f.xyz / f.w;
  vec3 d = normalize(far - uCam);
  vec3 inv = 1.0 / d, t0 = (uBoxMin - uCam) * inv, t1 = (uBoxMin + uBoxSize - uCam) * inv;
  vec3 tmn = min(t0, t1), tmx = max(t0, t1);
  float tn = max(max(tmn.x, tmn.y), max(tmn.z, 0.0)), tf = min(min(tmx.x, tmx.y), tmx.z);
  vec3 bg = vec3(0.055, 0.078, 0.094);
  if (tf <= tn) { o = vec4(bg, 1.0); return; }
  float t = tn + (tf - tn) * uCut + hash(gl_FragCoord.xy) * uStep;
  vec3 col = vec3(0.0); float T = 1.0;
  for (int i = 0; i < 2400; i++) {
    if (t > tf) break;
    vec3 p = uCam + d * t;
    vec3 uvw = (p - uBoxMin) / uBoxSize;
    if (texture(uOcc, uvw).r < 0.5) { t += uStep * 3.0; continue; }
    vec4 c = texture(uCol, uvw);
    if (c.a > 0.04) {
      vec4 n = texture(uNrm, (p - uNMin) / uNSize);
      vec3 N = normalize(n.xyz * 2.0 - 1.0);
      float lit = 0.35 + 0.65 * abs(dot(N, d));
      float flat_ = clamp(n.a * 4.0, 0.0, 1.0);
      lit = mix(1.0, lit, flat_);
      if (uMode < 0.5) {
        if (c.a > 0.5) { col = c.rgb * lit; T = 0.0; break; }
      } else {
        float a = smoothstep(0.3, 0.7, c.a) * (1.0 - exp(-uStep * 30.0));
        col += T * a * c.rgb * lit; T *= 1.0 - a;
        if (T < 0.02) break;
      }
    }
    t += uStep;
  }
  o = vec4(col + T * bg, 1.0);
}`;

// ---------------------------------------------------------------- small vector and matrix helpers
const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: V3, b: V3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: V3, b: V3): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a: V3): V3 => {
  const l = Math.hypot(a[0], a[1], a[2]) || 1;
  return [a[0] / l, a[1] / l, a[2] / l];
};

function perspective(fovy: number, aspect: number, n: number, f: number): number[] {
  const t = 1 / Math.tan(fovy / 2);
  return [t / aspect, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, (2 * f * n) / (n - f), 0];
}

function lookAt(e: V3, c: V3, u: V3): number[] {
  const z = norm(sub(e, c));
  const x = norm(cross(u, z));
  const y = cross(z, x);
  return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -dot(x, e), -dot(y, e), -dot(z, e), 1];
}

function mul(a: number[], b: number[]): number[] {
  const o = new Array<number>(16).fill(0);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) sum += (a[k * 4 + r] ?? 0) * (b[c * 4 + k] ?? 0);
      o[c * 4 + r] = sum;
    }
  }
  return o;
}

function invert(m: number[]): number[] {
  const [a00, a01, a02, a03, a10, a11, a12, a13, a20, a21, a22, a23, a30, a31, a32, a33] = m as [
    number, number, number, number, number, number, number, number,
    number, number, number, number, number, number, number, number,
  ];
  const b00 = a00 * a11 - a01 * a10, b01 = a00 * a12 - a02 * a10, b02 = a00 * a13 - a03 * a10;
  const b03 = a01 * a12 - a02 * a11, b04 = a01 * a13 - a03 * a11, b05 = a02 * a13 - a03 * a12;
  const b06 = a20 * a31 - a21 * a30, b07 = a20 * a32 - a22 * a30, b08 = a20 * a33 - a23 * a30;
  const b09 = a21 * a32 - a22 * a31, b10 = a21 * a33 - a23 * a31, b11 = a22 * a33 - a23 * a32;
  const det = 1 / (b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06);
  return [
    (a11 * b11 - a12 * b10 + a13 * b09) * det, (a02 * b10 - a01 * b11 - a03 * b09) * det,
    (a31 * b05 - a32 * b04 + a33 * b03) * det, (a22 * b04 - a21 * b05 - a23 * b03) * det,
    (a12 * b08 - a10 * b11 - a13 * b07) * det, (a00 * b11 - a02 * b08 + a03 * b07) * det,
    (a32 * b02 - a30 * b05 - a33 * b01) * det, (a20 * b05 - a22 * b02 + a23 * b01) * det,
    (a10 * b10 - a11 * b08 + a13 * b06) * det, (a01 * b08 - a00 * b10 - a03 * b06) * det,
    (a30 * b04 - a31 * b02 + a33 * b00) * det, (a21 * b02 - a20 * b04 - a23 * b00) * det,
    (a11 * b07 - a10 * b09 - a12 * b06) * det, (a00 * b09 - a01 * b07 + a02 * b06) * det,
    (a31 * b01 - a30 * b03 - a32 * b00) * det, (a20 * b03 - a21 * b01 + a22 * b00) * det,
  ];
}

/** Coarse occupancy (8-voxel blocks, grown by one block): empty space is crossed in big steps. */
export function buildOccupancy(dims: V3, rgba: Uint8Array): { dims: V3; data: Uint8Array } {
  const B = 8;
  const od: V3 = [Math.ceil(dims[0] / B), Math.ceil(dims[1] / B), Math.ceil(dims[2] / B)];
  const occ = new Uint8Array(od[0] * od[1] * od[2]);
  for (let z = 0; z < dims[2]; z++) {
    for (let y = 0; y < dims[1]; y++) {
      const row = (z * dims[1] + y) * dims[0];
      const orow = (Math.floor(z / B) * od[1] + Math.floor(y / B)) * od[0];
      for (let x = 0; x < dims[0]; x++) {
        if ((rgba[(row + x) * 4 + 3] ?? 0) > 10) occ[orow + Math.floor(x / B)] = 1;
      }
    }
  }
  const out = new Uint8Array(occ.length);
  for (let z = 0; z < od[2]; z++) {
    for (let y = 0; y < od[1]; y++) {
      for (let x = 0; x < od[0]; x++) {
        if (!occ[(z * od[1] + y) * od[0] + x]) continue;
        for (let k = -1; k <= 1; k++) {
          for (let j = -1; j <= 1; j++) {
            for (let i = -1; i <= 1; i++) {
              const xx = x + i, yy = y + j, zz = z + k;
              if (xx >= 0 && yy >= 0 && zz >= 0 && xx < od[0] && yy < od[1] && zz < od[2]) {
                out[(zz * od[1] + yy) * od[0] + xx] = 255;
              }
            }
          }
        }
      }
    }
  }
  return { dims: od, data: out };
}

type UniformName =
  | 'uCol' | 'uNrm' | 'uOcc' | 'uBoxMin' | 'uBoxSize' | 'uNMin' | 'uNSize' | 'uCam'
  | 'uInvVP' | 'uRes' | 'uStep' | 'uMode' | 'uCut';
const UNIFORMS: readonly UniformName[] = [
  'uCol', 'uNrm', 'uOcc', 'uBoxMin', 'uBoxSize', 'uNMin', 'uNSize', 'uCam', 'uInvVP', 'uRes', 'uStep', 'uMode', 'uCut',
];

export class VolumeRenderer {
  private gl: WebGL2RenderingContext;
  private prog!: WebGLProgram;
  private u = {} as Record<UniformName, WebGLUniformLocation | null>;
  private tex: { col: WebGLTexture | null; nrm: WebGLTexture | null; occ: WebGLTexture | null } = {
    col: null, nrm: null, occ: null,
  };
  private colour: VolumeData | null = null;
  private normals: VolumeData | null = null;
  private occupancy: { dims: V3; data: Uint8Array } | null = null;
  private center: V3 = [0, 0, 0];
  private radius = 30;
  private basis = { a: [1, 0, 0] as V3, b: [0, 1, 0] as V3, u: [0, 0, 1] as V3 };
  private yaw = 0.5;
  private pitch = 0.25;
  private dist = 90;
  private lost = false;
  /** Called when the graphics context is lost, and again when it is back and the picture is rebuilt. */
  onContextChange: ((lost: boolean) => void) | null = null;

  constructor(private canvas: HTMLCanvasElement) {
    const gl = canvas.getContext('webgl2', {
      antialias: false,
      alpha: false,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: false,
    });
    if (!gl) throw new NoWebGL2Error();
    this.gl = gl;
    this.buildProgram();
    canvas.addEventListener('webglcontextlost', this.handleLost);
    canvas.addEventListener('webglcontextrestored', this.handleRestored);
  }

  private handleLost = (e: Event): void => {
    e.preventDefault();
    this.lost = true;
    this.onContextChange?.(true);
  };

  private handleRestored = (): void => {
    this.buildProgram();
    this.tex = { col: null, nrm: null, occ: null };
    if (this.colour) this.uploadColour();
    if (this.normals) this.uploadNormals();
    this.lost = false;
    this.onContextChange?.(false);
  };

  private compile(type: number, src: string): WebGLShader {
    const gl = this.gl;
    const s = gl.createShader(type);
    if (!s) throw new Error('could not create a shader');
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? 'shader error');
    return s;
  }

  private buildProgram(): void {
    const gl = this.gl;
    const prog = gl.createProgram();
    if (!prog) throw new Error('could not create a program');
    gl.attachShader(prog, this.compile(gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, this.compile(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog) ?? 'link error');
    this.prog = prog;
    gl.useProgram(prog);
    gl.bindVertexArray(gl.createVertexArray());
    for (const k of UNIFORMS) this.u[k] = gl.getUniformLocation(prog, k);
    gl.uniform1i(this.u.uCol, 0);
    gl.uniform1i(this.u.uNrm, 1);
    gl.uniform1i(this.u.uOcc, 2);
  }

  /** Largest texture side this device allows, to check a tier before uploading it. */
  get maxTextureSize(): number {
    return this.gl.getParameter(this.gl.MAX_3D_TEXTURE_SIZE) as number;
  }

  /** Which unit the next upload goes to; uploads are plain RGBA8 or R8 3D textures. */
  private makeTexture(unit: number, dims: V3, data: Uint8Array, rgba: boolean, linear: boolean): WebGLTexture {
    const gl = this.gl;
    const t = gl.createTexture();
    if (!t) throw new Error('could not create a texture');
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_3D, t);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    const filter = linear ? gl.LINEAR : gl.NEAREST;
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, filter);
    for (const w of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_R]) {
      gl.texParameteri(gl.TEXTURE_3D, w, gl.CLAMP_TO_EDGE);
    }
    if (rgba) gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA8, dims[0], dims[1], dims[2], 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
    else gl.texImage3D(gl.TEXTURE_3D, 0, gl.R8, dims[0], dims[1], dims[2], 0, gl.RED, gl.UNSIGNED_BYTE, data);
    const err = gl.getError();
    if (err !== gl.NO_ERROR) {
      gl.deleteTexture(t);
      throw new Error(`texImage3D failed (${err})`);
    }
    return t;
  }

  private uploadColour(): void {
    const v = this.colour;
    if (!v) return;
    const gl = this.gl;
    if (this.tex.col) gl.deleteTexture(this.tex.col);
    if (this.tex.occ) gl.deleteTexture(this.tex.occ);
    this.tex.col = this.makeTexture(0, v.dims, v.rgba, true, true);
    this.occupancy ??= buildOccupancy(v.dims, v.rgba);
    this.tex.occ = this.makeTexture(2, this.occupancy.dims, this.occupancy.data, false, false);
    const size: V3 = [v.dims[0] * v.spacingMm, v.dims[1] * v.spacingMm, v.dims[2] * v.spacingMm];
    const min: V3 = [
      v.originMm[0] - v.spacingMm / 2,
      v.originMm[1] - v.spacingMm / 2,
      v.originMm[2] - v.spacingMm / 2,
    ];
    gl.useProgram(this.prog);
    gl.uniform3fv(this.u.uBoxMin, min);
    gl.uniform3fv(this.u.uBoxSize, size);
    this.center = [min[0] + size[0] / 2, min[1] + size[1] / 2, min[2] + size[2] / 2];
    this.radius = Math.hypot(size[0], size[1], size[2]) / 2;
  }

  private uploadNormals(): void {
    const v = this.normals;
    if (!v) return;
    const gl = this.gl;
    if (this.tex.nrm) gl.deleteTexture(this.tex.nrm);
    this.tex.nrm = this.makeTexture(1, v.dims, v.rgba, true, true);
    gl.useProgram(this.prog);
    gl.uniform3fv(this.u.uNMin, [
      v.originMm[0] - v.spacingMm / 2,
      v.originMm[1] - v.spacingMm / 2,
      v.originMm[2] - v.spacingMm / 2,
    ]);
    gl.uniform3fv(this.u.uNSize, [v.dims[0] * v.spacingMm, v.dims[1] * v.spacingMm, v.dims[2] * v.spacingMm]);
  }

  setNormals(v: VolumeData): void {
    this.normals = v;
    this.uploadNormals();
  }

  setColour(v: VolumeData): void {
    this.colour = v;
    this.occupancy = null;
    this.uploadColour();
    this.dist = this.radius * 3;
  }

  get ready(): boolean {
    return !this.lost && this.tex.col !== null && this.tex.nrm !== null;
  }

  get voxelMm(): number | null {
    return this.colour?.spacingMm ?? null;
  }

  /**
   * Looking direction of the ear: `lateral` points out of the head toward the viewer, `superior` is up.
   * The first picture is the ear seen from the side, as in the operating field's neighbourhood.
   */
  setFrame(lateral: V3, superior: V3): void {
    const a = norm(lateral);
    const u = norm(sub(superior, [a[0] * dot(superior, a), a[1] * dot(superior, a), a[2] * dot(superior, a)]));
    this.basis = { a, u, b: cross(u, a) };
    this.yaw = 0;
    this.pitch = 0.2;
  }

  rotate(dx: number, dy: number): void {
    this.yaw -= dx * 0.008;
    this.pitch = Math.max(-1.4, Math.min(1.4, this.pitch + dy * 0.008));
  }

  zoom(factor: number): void {
    this.dist = Math.max(this.radius * 0.4, Math.min(this.radius * 6, this.dist * factor));
  }

  /** The canvas size for a render scale; the caller sets nothing, `render` resizes. */
  private resize(scale: number): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 2) * scale;
    const w = Math.max(64, Math.round(this.canvas.clientWidth * dpr));
    const h = Math.max(64, Math.round(this.canvas.clientHeight * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
  }

  get pixelSize(): readonly [number, number] {
    return [this.canvas.width, this.canvas.height];
  }

  render(opts: RenderOptions): void {
    if (!this.ready || !this.colour) return;
    const gl = this.gl;
    this.resize(opts.renderScale);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    const { a, b, u } = this.basis;
    const ca = Math.cos(this.pitch);
    const at = (k: 0 | 1 | 2): number =>
      this.center[k] + this.dist * (ca * (Math.cos(this.yaw) * a[k] + Math.sin(this.yaw) * b[k]) + Math.sin(this.pitch) * u[k]);
    const eye: V3 = [at(0), at(1), at(2)];
    const P = perspective((35 * Math.PI) / 180, this.canvas.width / this.canvas.height, 1, 600);
    const V = lookAt(eye, this.center, u);
    gl.useProgram(this.prog);
    gl.uniformMatrix4fv(this.u.uInvVP, false, invert(mul(P, V)));
    gl.uniform3fv(this.u.uCam, eye);
    gl.uniform2f(this.u.uRes, this.canvas.width, this.canvas.height);
    gl.uniform1f(this.u.uStep, this.colour.spacingMm);
    gl.uniform1f(this.u.uMode, opts.translucent ? 1 : 0);
    gl.uniform1f(this.u.uCut, Math.max(0, Math.min(0.8, opts.cut)));
    for (const [unit, t] of [[0, this.tex.col], [1, this.tex.nrm], [2, this.tex.occ]] as const) {
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_3D, t);
    }
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  dispose(): void {
    this.canvas.removeEventListener('webglcontextlost', this.handleLost);
    this.canvas.removeEventListener('webglcontextrestored', this.handleRestored);
    const gl = this.gl;
    for (const t of [this.tex.col, this.tex.nrm, this.tex.occ]) if (t) gl.deleteTexture(t);
    this.tex = { col: null, nrm: null, occ: null };
    gl.deleteProgram(this.prog);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
}
