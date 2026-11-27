// @vitest-environment node
import golden from './fixtures/bricks_golden.json';
import { decodeBricks, parseBrickIndex } from './bricks';

function fromBase64(text: string): Uint8Array<ArrayBuffer> {
  const bin = atob(text);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

describe('bricks', () => {
  it('decodes a volume written by the Python pipeline, byte for byte', async () => {
    const index = parseBrickIndex(golden.index);
    expect(index.bricks.length).toBeLessThan(3 * 3 * 2); // some bricks are all zero and not stored
    const progress: number[] = [];
    const out = await decodeBricks(fromBase64(golden.blob), index, (f) => progress.push(f));
    expect(out).toEqual(fromBase64(golden.expected));
    expect(progress.at(-1)).toBe(1);
  });

  it('refuses a brick that lies beyond the end of the file', async () => {
    const index = parseBrickIndex(golden.index);
    const blob = fromBase64(golden.blob);
    await expect(decodeBricks(blob.subarray(0, blob.length - 5), index)).rejects.toThrow();
  });

  it('refuses malformed indexes', () => {
    const ok = golden.index;
    expect(() => parseBrickIndex(null)).toThrow();
    expect(() => parseBrickIndex({ ...ok, dims: [10, 10] })).toThrow(/dims/);
    expect(() => parseBrickIndex({ ...ok, channels: 7 })).toThrow(/channels/);
    expect(() => parseBrickIndex({ ...ok, brick: 2 })).toThrow(/brick size/);
    expect(() => parseBrickIndex({ ...ok, bricks: [[0, 0, 9, 0, 10]] })).toThrow(/outside/);
    expect(() => parseBrickIndex({ ...ok, bricks: [[0, 0, 0, 0]] })).toThrow(/malformed/);
  });
});
