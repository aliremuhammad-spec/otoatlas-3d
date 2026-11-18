import {
  AmbientLight,
  Box3,
  BufferGeometry,
  Color,
  DoubleSide,
  EdgesGeometry,
  LineSegments,
  PlaneGeometry,
  DirectionalLight,
  Group,
  LessEqualDepth,
  Line,
  LineBasicMaterial,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  Raycaster,
  Scene,
  SphereGeometry,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { acceleratedRaycast, computeBoundsTree, disposeBoundsTree } from 'three-mesh-bvh';
import type { Vec3 } from '../measure/geometry';
import type { SceneContent } from './content';

BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
Mesh.prototype.raycast = acceleratedRaycast;

export interface PickResult {
  structureId: string;
  /** Picked surface point in the specimen frame, millimetres. */
  point: Vec3;
}

/** Structures fainter than this do not take taps, so a see-through bone does not block what is inside it. */
export const PICK_MIN_OPACITY = 0.5;
/** Pointer travel (CSS pixels) below which a press-and-release counts as a tap, not a drag. */
const TAP_SLOP_PX = 6;

/**
 * Framework-free 3D viewer. Owns the renderer, camera, controls and scene, and
 * exposes a small imperative API to the interface layer. Scene units are millimetres.
 */
export class ViewerCore {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(35, 1, 0.1, 2000);
  private readonly controls: OrbitControls;
  private readonly raycaster = new Raycaster();
  private readonly meshes = new Map<string, Mesh<BufferGeometry, MeshStandardMaterial>>();
  private readonly displayOnly = new Set<string>();
  /**
   * Depth-only twin of each mesh, drawn just before it while it is see-through. It lets
   * only the nearest layer of a faded structure show, so the inner walls of the bone
   * (air cells, canals) do not pile up into noise as the opacity changes.
   */
  private readonly depthTwins = new Map<string, Mesh<BufferGeometry, MeshBasicMaterial>>();
  private readonly overlay = new Group();
  private readonly resizeObserver: ResizeObserver;
  private pickHandler: ((pick: PickResult) => void) | null = null;
  private readonly renderListeners = new Set<() => void>();
  private highlighted: string | null = null;
  private slicePlane: Group | null = null;
  private pointerDown: { x: number; y: number } | null = null;
  private frame = 0;
  private needsRender = true;
  private markerRadius = 0.12;

  constructor(
    private readonly container: HTMLElement,
    content: SceneContent,
  ) {
    this.renderer = new WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.style.touchAction = 'none';
    container.appendChild(this.renderer.domElement);

    this.scene.add(new AmbientLight(0xffffff, 0.9));
    const key = new DirectionalLight(0xffffff, 2.2);
    key.position.set(20, 30, 40);
    this.camera.add(key);
    this.scene.add(this.camera);
    this.scene.add(this.overlay);

    for (const s of content.structures) {
      const material = new MeshStandardMaterial({ color: new Color(s.color), roughness: 0.6 });
      const mesh = new Mesh(s.geometry, material);
      mesh.position.set(...s.position);
      mesh.name = s.id;
      // Only measurable structures take taps, so only they need a picking tree.
      if (s.measurable !== false) s.geometry.computeBoundsTree();
      else this.displayOnly.add(s.id);
      this.meshes.set(s.id, mesh);
      this.scene.add(mesh);
      const twin = new Mesh(s.geometry, new MeshBasicMaterial({ colorWrite: false, depthWrite: true }));
      twin.position.copy(mesh.position);
      twin.visible = false;
      twin.raycast = () => undefined;
      this.depthTwins.set(s.id, twin);
      this.scene.add(twin);
      if (s.defaultOpacity !== undefined && s.defaultOpacity < 1) this.setOpacity(s.id, s.defaultOpacity);
      if (s.defaultVisible === false) this.setVisible(s.id, false);
    }

    // See-through structures draw smallest first and enclosing ones (the bone) last,
    // so a faded outer shell never hides a faded structure inside it.
    const bySize = [...this.meshes.values()].sort((a, b) => boxVolume(a) - boxVolume(b));
    bySize.forEach((mesh, i) => {
      const twin = this.depthTwins.get(mesh.name);
      if (twin) twin.renderOrder = 2 * i;
      mesh.renderOrder = 2 * i + 1;
    });

    this.camera.up.set(0, 0, 1);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.frameContent();
    this.controls.enableDamping = true;
    this.controls.addEventListener('change', this.requestRender);

    this.renderer.domElement.addEventListener('pointerdown', this.onPointerDown);
    this.renderer.domElement.addEventListener('pointerup', this.onPointerUp);

    this.resizeObserver = new ResizeObserver(this.resize);
    this.resizeObserver.observe(container);
    this.resize();
    this.frame = requestAnimationFrame(this.tick);
  }

  onPick(handler: ((pick: PickResult) => void) | null): void {
    this.pickHandler = handler;
  }

  /** Called after every rendered frame, so overlays drawn in HTML can follow the camera. Returns an unsubscribe. */
  onRender(listener: () => void): () => void {
    this.renderListeners.add(listener);
    this.requestRender();
    return () => this.renderListeners.delete(listener);
  }

  /** Where a specimen-frame point falls on the canvas, in CSS pixels; null when behind the camera. */
  project(point: Vec3): { x: number; y: number } | null {
    const v = new Vector3(...point).project(this.camera);
    if (v.z < -1 || v.z > 1) return null;
    const { clientWidth: w, clientHeight: h } = this.renderer.domElement;
    return { x: ((v.x + 1) / 2) * w, y: ((1 - v.y) / 2) * h };
  }

  /** Canvas size in CSS pixels. */
  viewSize(): { width: number; height: number } {
    const { clientWidth: width, clientHeight: height } = this.renderer.domElement;
    return { width, height };
  }

  isVisible(id: string): boolean {
    return this.meshes.get(id)?.visible ?? false;
  }

  /**
   * A point on the structure's surface to pin its label to: the vertex nearest the
   * centre of its vertices, so curved structures (canals, nerves) still get a point on them.
   */
  anchorOf(id: string): Vec3 | null {
    const mesh = this.meshes.get(id);
    const position = mesh?.geometry.getAttribute('position');
    if (!mesh || !position || position.count === 0) return null;
    const step = Math.max(1, Math.floor(position.count / 20000));
    let cx = 0;
    let cy = 0;
    let cz = 0;
    let n = 0;
    for (let i = 0; i < position.count; i += step) {
      cx += position.getX(i);
      cy += position.getY(i);
      cz += position.getZ(i);
      n += 1;
    }
    cx /= n;
    cy /= n;
    cz /= n;
    let best = 0;
    let bestD = Infinity;
    for (let i = 0; i < position.count; i += step) {
      const d = (position.getX(i) - cx) ** 2 + (position.getY(i) - cy) ** 2 + (position.getZ(i) - cz) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    mesh.updateMatrixWorld();
    const v = new Vector3(position.getX(best), position.getY(best), position.getZ(best)).applyMatrix4(mesh.matrixWorld);
    return [v.x, v.y, v.z];
  }

  /**
   * Shows where the slice view cuts: a faint rectangle across the scan's extent at
   * `position` mm along `axis`. Pass null to remove it.
   */
  setSlicePlane(
    plane: { axis: 'x' | 'y' | 'z'; position: number; min: readonly [number, number, number]; max: readonly [number, number, number] } | null,
  ): void {
    if (this.slicePlane) {
      this.scene.remove(this.slicePlane);
      for (const child of this.slicePlane.children) {
        const m = child as Mesh | LineSegments;
        m.geometry.dispose();
        (m.material as MeshBasicMaterial | LineBasicMaterial).dispose();
      }
      this.slicePlane = null;
    }
    if (plane) {
      const { axis, position, min, max } = plane;
      const size = [max[0] - min[0], max[1] - min[1], max[2] - min[2]] as const;
      const centre = new Vector3((min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2);
      const [w, h] = axis === 'z' ? [size[0], size[1]] : axis === 'y' ? [size[0], size[2]] : [size[1], size[2]];
      const geometry = new PlaneGeometry(w, h);
      const group = new Group();
      const fill = new Mesh(
        geometry,
        new MeshBasicMaterial({ color: 0x5fd0c5, transparent: true, opacity: 0.12, side: DoubleSide, depthWrite: false }),
      );
      const rim = new LineSegments(new EdgesGeometry(geometry), new LineBasicMaterial({ color: 0x5fd0c5 }));
      fill.raycast = () => undefined;
      rim.raycast = () => undefined;
      group.add(fill, rim);
      if (axis === 'y') group.rotation.x = Math.PI / 2;
      if (axis === 'x') group.rotation.set(Math.PI / 2, Math.PI / 2, 0);
      group.position.copy(centre);
      if (axis === 'x') group.position.x = position;
      else if (axis === 'y') group.position.y = position;
      else group.position.z = position;
      group.renderOrder = 10_000;
      this.slicePlane = group;
      this.scene.add(group);
    }
    this.requestRender();
  }

  /** Marks one structure as selected (a soft glow), or none. */
  setHighlight(id: string | null): void {
    if (this.highlighted) this.meshes.get(this.highlighted)?.material.emissive.setHex(0x000000);
    this.highlighted = id;
    if (id) this.meshes.get(id)?.material.emissive.setHex(0x3a3a3a);
    this.requestRender();
  }

  setVisible(id: string, visible: boolean): void {
    const mesh = this.meshes.get(id);
    if (mesh) mesh.visible = visible;
    const twin = this.depthTwins.get(id);
    if (twin && mesh) twin.visible = visible && mesh.material.transparent;
    this.requestRender();
  }

  setOpacity(id: string, opacity: number): void {
    const mesh = this.meshes.get(id);
    if (!mesh) return;
    const faded = opacity < 1;
    mesh.material.opacity = opacity;
    mesh.material.transparent = faded;
    // The twin has already written this mesh's nearest depth; drawing at equal depth keeps only that layer.
    mesh.material.depthFunc = LessEqualDepth;
    mesh.material.depthWrite = !faded;
    mesh.material.needsUpdate = true;
    const twin = this.depthTwins.get(id);
    if (twin) {
      twin.visible = faded && mesh.visible;
      // In the transparent pass, so it runs after every opaque structure has been drawn.
      twin.material.transparent = true;
    }
    this.requestRender();
  }

  /** Geometry of a structure and the transform from its local frame to the specimen frame. */
  getGeometry(id: string): { geometry: BufferGeometry; toSpecimen: Matrix4 } | null {
    const mesh = this.meshes.get(id);
    if (!mesh) return null;
    mesh.updateMatrixWorld();
    return { geometry: mesh.geometry, toSpecimen: mesh.matrixWorld.clone() };
  }

  /** Draws measurement markers and a connecting line. Pass an empty list to clear. */
  showMeasurement(points: readonly Vec3[]): void {
    for (const child of [...this.overlay.children]) {
      this.overlay.remove(child);
      const disposable = child as Partial<Mesh>;
      disposable.geometry?.dispose();
    }
    const markerMaterial = new MeshBasicMaterial({ color: 0xffffff, depthTest: false });
    for (const p of points) {
      const marker = new Mesh(new SphereGeometry(this.markerRadius, 16, 12), markerMaterial);
      marker.position.set(...p);
      marker.renderOrder = 10;
      this.overlay.add(marker);
    }
    if (points.length >= 2) {
      const geometry = new BufferGeometry().setFromPoints(points.map((p) => new Vector3(...p)));
      const line = new Line(geometry, new LineBasicMaterial({ color: 0xffffff, depthTest: false }));
      line.renderOrder = 10;
      this.overlay.add(line);
    }
    this.requestRender();
  }

  /** Points the camera at the whole specimen and sizes markers to it. */
  private frameContent(): void {
    const box = new Box3();
    for (const mesh of this.meshes.values()) box.expandByObject(mesh);
    if (box.isEmpty()) return;
    const centre = box.getCenter(new Vector3());
    const radius = Math.max(box.getSize(new Vector3()).length() / 2, 1e-3);
    const distance = (radius / Math.sin((this.camera.fov * Math.PI) / 360)) * 1.15;
    this.camera.position.copy(centre).add(new Vector3(0.25, -0.85, 0.45).normalize().multiplyScalar(distance));
    this.camera.near = distance / 200;
    this.camera.far = distance * 20;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(centre);
    this.markerRadius = radius / 90;
  }

  dispose(): void {
    cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.renderer.domElement.removeEventListener('pointerdown', this.onPointerDown);
    this.renderer.domElement.removeEventListener('pointerup', this.onPointerUp);
    for (const mesh of this.meshes.values()) {
      mesh.geometry.disposeBoundsTree();
      mesh.material.dispose();
    }
    for (const twin of this.depthTwins.values()) twin.material.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private readonly requestRender = (): void => {
    this.needsRender = true;
  };

  private readonly tick = (): void => {
    this.frame = requestAnimationFrame(this.tick);
    // Damping keeps the camera moving after input stops, so update controls every frame.
    this.controls.update();
    if (!this.needsRender) return;
    this.needsRender = false;
    this.renderer.render(this.scene, this.camera);
    for (const listener of this.renderListeners) listener();
  };

  private readonly resize = (): void => {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (w === 0 || h === 0) return;
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = '100%';
    this.renderer.domElement.style.height = '100%';
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.requestRender();
  };

  private readonly onPointerDown = (e: PointerEvent): void => {
    this.pointerDown = { x: e.clientX, y: e.clientY };
  };

  private readonly onPointerUp = (e: PointerEvent): void => {
    const down = this.pointerDown;
    this.pointerDown = null;
    if (!down || !this.pickHandler) return;
    if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > TAP_SLOP_PX) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    this.raycaster.firstHitOnly = true;
    // Faded structures (opacity below 0.5) do not take taps, so a see-through bone
    // does not block picking the structures inside it.
    const visible = [...this.meshes.values()].filter((m) => m.visible && m.material.opacity >= PICK_MIN_OPACITY && !this.displayOnly.has(m.name));
    const hit = this.raycaster.intersectObjects(visible, false)[0];
    if (!hit) return;
    this.pickHandler({
      structureId: hit.object.name,
      point: [hit.point.x, hit.point.y, hit.point.z],
    });
  };
}

function boxVolume(mesh: Mesh): number {
  const geometry = mesh.geometry;
  if (!geometry.boundingBox) geometry.computeBoundingBox();
  const size = geometry.boundingBox?.getSize(new Vector3()) ?? new Vector3();
  return size.x * size.y * size.z;
}
