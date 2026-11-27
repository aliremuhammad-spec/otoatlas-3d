import { CONTENT_BASE, fetchBytes, fetchJson, listSpecimens } from '../viewer/loadPackage';
import { parseManifest, type Manifest, type ManifestColour, type ManifestColourVolume } from '../viewer/manifest';
import { decodeBricks, parseBrickIndex } from './bricks';
import type { VolumeData } from './VolumeRenderer';

/** A specimen that has true-colour data, with what the surgical view needs from its manifest. */
export interface ColourSpecimen {
  path: string;
  id: string;
  dataset: string | null;
  side: 'left' | 'right' | null;
  colour: ManifestColour;
  frame: Manifest['anatomicalFrame'];
  draft: boolean;
}

/** Installed specimens that have a colour volume. A package whose manifest cannot be read is skipped. */
export async function listColourSpecimens(base = CONTENT_BASE): Promise<ColourSpecimen[]> {
  const entries = await listSpecimens(base);
  const found = await Promise.all(
    entries.map(async (e): Promise<ColourSpecimen | null> => {
      try {
        const m = parseManifest(await fetchJson(`${base}/${e.path}/manifest.json`));
        if (!m.colour) return null;
        return {
          path: e.path,
          id: e.id,
          dataset: e.dataset,
          side: e.side,
          colour: m.colour,
          frame: m.anatomicalFrame,
          draft: m.structures.some((s) => s.contentStatus === 'draft' || s.arStatus === 'unverified'),
        };
      } catch {
        return null;
      }
    }),
  );
  return found.filter((s): s is ColourSpecimen => s !== null);
}

export interface LoadProgress {
  /** 0 to 1 over the whole download and unpacking of this volume. */
  fraction: number;
}

/** Download first, then unpacking: the bar gives the download 85 percent and the unpacking the rest. */
const DOWNLOAD_SHARE = 0.85;

/**
 * Downloads and unpacks one bricked volume. This site's copy first, then the pinned Hugging Face copy.
 * `volume.dims` must agree with the brick index, or the file is refused.
 */
export async function loadColourVolume(
  path: string,
  volume: ManifestColourVolume,
  onProgress?: (p: LoadProgress) => void,
  base = CONTENT_BASE,
): Promise<VolumeData> {
  const root = `${base}/${path}`;
  const index = parseBrickIndex(await fetchJson(`${root}/${volume.index}`));
  if (index.dims.some((d, i) => d !== volume.dims[i])) throw new Error('brick index does not match the manifest');
  if (index.channels !== 4) throw new Error('colour volume must have four channels');
  const urls = [...(volume.onSite ? [`${root}/${volume.bricks}`] : []), ...(volume.url ? [volume.url] : [])];
  if (urls.length === 0) throw new Error('volume has no source');
  const failures: string[] = [];
  for (const url of urls) {
    try {
      const blob = await fetchBytes(url, (received, total) => {
        const expected = total ?? volume.bytes;
        onProgress?.({ fraction: DOWNLOAD_SHARE * Math.min(1, received / Math.max(1, expected)) });
      });
      const rgba = await decodeBricks(blob, index, (f) =>
        onProgress?.({ fraction: DOWNLOAD_SHARE + (1 - DOWNLOAD_SHARE) * f }),
      );
      return { dims: volume.dims, spacingMm: volume.spacingMm, originMm: volume.originMm, rgba };
    } catch (e) {
      failures.push(`${url.split('/').slice(0, 3).join('/')}: ${String(e)}`);
    }
  }
  throw new Error(failures.join('; '));
}
