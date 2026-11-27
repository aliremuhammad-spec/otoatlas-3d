// @vitest-environment node
import { gzipSync } from 'node:zlib';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadLabelVolume } from './loadColour';
import type { ManifestLabelVolume } from '../viewer/manifest';

const block = (bytes: number, dims: [number, number, number]): ManifestLabelVolume => ({
  file: 'labels.u8.gz',
  bytes,
  dims,
  spacingMm: 0.125,
  originMm: [0, 0, 0],
  structures: [{ id: 'malleus', value: 1 }],
  excludedSchematic: [],
});

function serve(body: Uint8Array<ArrayBuffer>): void {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(new Blob([body]))));
}

describe('loadLabelVolume', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('downloads and unpacks the labels of a package', async () => {
    const raw = Uint8Array.from({ length: 24 }, (_, i) => i % 3);
    const gz = new Uint8Array(gzipSync(raw)) as Uint8Array<ArrayBuffer>;
    serve(gz);
    const out = await loadLabelVolume('SPEC', block(gz.length, [2, 3, 4]), undefined, 'https://x/content');
    expect(Array.from(out.data)).toEqual(Array.from(raw));
    expect(out.dims).toEqual([2, 3, 4]);
    expect(out.spacingMm).toBe(0.125);
  });

  it('refuses a file that does not match its stated size', async () => {
    const gz = new Uint8Array(gzipSync(new Uint8Array(10))) as Uint8Array<ArrayBuffer>;
    serve(gz);
    await expect(loadLabelVolume('SPEC', block(gz.length, [2, 3, 4]), undefined, 'https://x/content')).rejects.toThrow(
      /wrong size/,
    );
  });
});
