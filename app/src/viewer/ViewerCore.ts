import {
  AmbientLight,
  Box3,
  BufferGeometry,
  Color,
  DirectionalLight,
  Group,
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

/** Pointer travel (CSS pixels) below which a press-and-release counts as a tap, not a drag. */
export const PICK_MIN_OPACITY = 0.5;
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
  private readonly overlay = new Group();
  private readonly resizeObserver: ResizeObserver;
  private pickHandler: ((pick: PickResult) => void) | null = null;
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
      s.geometry.computeBoundsTree();
      this.meshes.set(s.id, mesh);
      this.scene.add(mesh);
      if (s.defaultOpacity !== undefined && s.defaultOpacity < 1) this.setOpacity(s.id, s.defaultOpacity);
    }

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

  setVisible(id: string, visible: boolean): void {
    const mesh = this.meshes.get(id);
    if (mesh) mesh.visible = visible;
    this.requestRender();
  }

  setOpacity(id: string, opacity: number): void {
    const mesh = this.meshes.get(id);
    if (!mesh) return;
    mesh.material.opacity = opacity;
    mesh.material.transparent = opacity < 1;
    mesh.material.depthWrite = opacity >= 1;
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
    const visible = [...this.meshes.values()].filter((m) => m.visible && m.material.opacity >= PICK_MIN_OPACITY);
    const hit = this.raycaster.intersectObjects(visible, false)[0];
    if (!hit) return;
    this.pickHandler({
      structureId: hit.object.name,
      point: [hit.point.x, hit.point.y, hit.point.z],
    });
  };
}
