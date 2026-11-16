import { IcosahedronGeometry, TorusGeometry, type BufferGeometry } from 'three';
import type { MessageKey } from '../i18n/en';

/** One selectable object in the scene. Real specimens will fill this from a content package. */
export interface SceneStructure {
  id: string;
  nameKey: MessageKey;
  color: number;
  geometry: BufferGeometry;
  /** Position of the geometry in the specimen frame, in millimetres. */
  position: readonly [number, number, number];
}

export interface SceneContent {
  specimenId: string;
  /** True when the geometry is not derived from a specimen. Drives the on-screen badge. */
  synthetic: boolean;
  structures: readonly SceneStructure[];
}

/**
 * Synthetic phantom with known dimensions, used to exercise the viewer and the
 * measurement tools before specimen content exists. Sphere A to sphere B gap: 3.00 mm.
 * Sphere A to ring gap: 0.50 mm.
 */
export function createPhantom(): SceneContent {
  return {
    specimenId: 'PHANTOM-01',
    synthetic: true,
    structures: [
      {
        id: 'sphereA',
        nameKey: 'phantom.sphereA',
        color: 0xd8c9a3,
        geometry: new IcosahedronGeometry(3, 24),
        position: [0, 0, 0],
      },
      {
        id: 'sphereB',
        nameKey: 'phantom.sphereB',
        color: 0xe0a458,
        geometry: new IcosahedronGeometry(2, 24),
        position: [8, 0, 0],
      },
      {
        id: 'torus',
        nameKey: 'phantom.torus',
        color: 0x5fd0c5,
        geometry: new TorusGeometry(4, 0.5, 48, 192),
        position: [0, 0, 0],
      },
    ],
  };
}
