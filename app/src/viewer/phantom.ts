import { IcosahedronGeometry, TorusGeometry } from 'three';
import { ar } from '../i18n/ar';
import { en, type MessageKey } from '../i18n/en';
import type { SceneContent, StructureNames } from './content';

function names(key: MessageKey): StructureNames {
  return { en: en[key], ar: ar[key], latin: null };
}

/**
 * Synthetic phantom with known dimensions, used to exercise the viewer and the
 * measurement tools when no specimen content is installed. Sphere A to sphere B
 * gap: 3.00 mm. Sphere A to ring gap: 0.50 mm.
 */
export function createPhantom(): SceneContent {
  return {
    specimenId: 'PHANTOM-01',
    dataset: null,
    scan: null,
    side: null,
    synthetic: true,
    draft: false,
    sourceVoxelMm: null,
    attribution: null,
    structures: [
      {
        id: 'sphereA',
        names: names('phantom.sphereA'),
        color: 0xd8c9a3,
        geometry: new IcosahedronGeometry(3, 24),
        position: [0, 0, 0],
      },
      {
        id: 'sphereB',
        names: names('phantom.sphereB'),
        color: 0xe0a458,
        geometry: new IcosahedronGeometry(2, 24),
        position: [8, 0, 0],
      },
      {
        id: 'torus',
        names: names('phantom.torus'),
        color: 0x5fd0c5,
        geometry: new TorusGeometry(4, 0.5, 48, 192),
        position: [0, 0, 0],
      },
    ],
  };
}
