import { parseManifest, parseSpecimenIndex } from './manifest';

function validManifest(): Record<string, unknown> {
  return {
    schema: 1,
    specimen_id: 'OPENEAR-ZETA',
    dataset: 'openear',
    side: null,
    synthetic: false,
    units: 'mm',
    attribution: { data_doi: '10.5281/zenodo.1473724', paper_doi: '10.1038/sdata.2018.297', license: 'CC BY 4.0' },
    structures: [
      {
        id: 'malleus',
        names: { en: 'Malleus', ar: 'المطرقة', latin: 'Malleus' },
        ar_status: 'unverified',
        content_status: 'draft',
        provenance_tier: 'specimen-derived',
        color: '#E69F00',
        mesh_error_limit_mm: 0.1,
        source_voxel_mm: [0.125, 0.125, 0.125],
        lods: [
          { level: 0, file: 'malleus.lod0.glb', triangles: 9000, within_limit: true, hausdorff_mm: 0.061 },
          { level: 1, file: 'malleus.lod1.glb', triangles: 2250, within_limit: false, hausdorff_mm: 0.12 },
        ],
      },
    ],
  };
}

function withStructure(patch: Record<string, unknown>): Record<string, unknown> {
  const m = validManifest();
  const s = (m.structures as Record<string, unknown>[])[0];
  m.structures = [{ ...s, ...patch }];
  return m;
}

describe('content manifest', () => {
  it('parses a pipeline manifest', () => {
    const m = parseManifest(validManifest());
    expect(m.specimenId).toBe('OPENEAR-ZETA');
    expect(m.side).toBeNull();
    expect(m.structures[0]?.color).toBe(0xe69f00);
    expect(m.structures[0]?.names.ar).toBe('المطرقة');
    expect(m.structures[0]?.lods[0]?.hausdorffMm).toBe(0.061);
  });

  it('rejects an unknown schema or non-millimetre units', () => {
    expect(() => parseManifest({ ...validManifest(), schema: 2 })).toThrow(/schema/);
    expect(() => parseManifest({ ...validManifest(), units: 'cm' })).toThrow(/millimetres/);
  });

  it('rejects a package whose full-resolution mesh exceeds its error limit', () => {
    const lods = [{ level: 0, file: 'malleus.lod0.glb', triangles: 9, within_limit: false, hausdorff_mm: 0.3 }];
    expect(() => parseManifest(withStructure({ lods }))).toThrow(/exceeds its error limit/);
  });

  it('rejects a package without a full-resolution level', () => {
    const lods = [{ level: 1, file: 'malleus.lod1.glb', triangles: 9, within_limit: true, hausdorff_mm: 0.01 }];
    expect(() => parseManifest(withStructure({ lods }))).toThrow(/full-resolution/);
  });

  it('refuses file names that leave the package folder', () => {
    const lods = [{ level: 0, file: '../secret.glb', triangles: 9, within_limit: true, hausdorff_mm: 0.01 }];
    expect(() => parseManifest(withStructure({ lods }))).toThrow(/plain \.glb file name/);
  });

  it('rejects unknown review states and malformed colours', () => {
    expect(() => parseManifest(withStructure({ content_status: 'approved' }))).toThrow(/content_status/);
    expect(() => parseManifest(withStructure({ color: 'orange' }))).toThrow(/colour/);
  });

  it('reads the starting opacity, defaulting to opaque and refusing values outside 0 to 1', () => {
    expect(parseManifest(validManifest()).structures[0]?.defaultOpacity).toBe(1);
    expect(parseManifest(withStructure({ default_opacity: 0.25 })).structures[0]?.defaultOpacity).toBe(0.25);
    expect(() => parseManifest(withStructure({ default_opacity: 1.5 }))).toThrow(/default_opacity/);
  });

  it('defaults the shown level to full resolution and refuses a level that does not exist', () => {
    expect(parseManifest(validManifest()).structures[0]?.displayLevel).toBe(0);
    expect(() => parseManifest(withStructure({ display_level: 7 }))).toThrow(/display_level/);
  });

  it('refuses a shown level whose file was not published', () => {
    const m = validManifest();
    const s0 = (m.structures as Record<string, unknown>[])[0] as Record<string, unknown>;
    const lod0 = (s0.lods as Record<string, unknown>[])[0] as Record<string, unknown>;
    lod0.published = false;
    expect(() => parseManifest(m)).toThrow(/not published/);
  });

  it('reads dataset and side from the specimen index when present', () => {
    const list = parseSpecimenIndex({
      specimens: [
        { id: 'OPENEAR-ZETA', path: 'OPENEAR-ZETA', dataset: 'openear', side: 'right' },
        { id: 'X', path: 'X' },
      ],
    });
    expect(list[0]).toEqual({ id: 'OPENEAR-ZETA', path: 'OPENEAR-ZETA', dataset: 'openear', side: 'right' });
    expect(list[1]).toEqual({ id: 'X', path: 'X', dataset: null, side: null });
    expect(() => parseSpecimenIndex({ specimens: [{ id: 'X', path: 'X', side: 'up' }] })).toThrow(/side/);
  });

  it('accepts a scan published on Hugging Face only when pinned to a commit', () => {
    const scan = {
      file: 'scan.u8.gz',
      format: 'uint8, gzip, x fastest',
      shape: [2, 2, 2],
      spacing_mm: [0.1, 0.1, 0.1],
      origin_mm: [0, 0, 0],
      modality: 'CBCT',
    };
    const pinned = `https://huggingface.co/datasets/zero019/otoatlas-3d-content/resolve/${'a'.repeat(40)}/OPENEAR-ZETA/scan.u8.gz`;
    expect(parseManifest({ ...validManifest(), scan: { ...scan, url: pinned } }).scan?.url).toBe(pinned);
    expect(parseManifest({ ...validManifest(), scan }).scan?.url).toBeNull();
    expect(() =>
      parseManifest({ ...validManifest(), scan: { ...scan, url: 'https://example.com/scan.u8.gz' } }),
    ).toThrow(/pinned/);
  });

  it('reads known measurements and skips unknown ones', () => {
    const m = parseManifest({
      ...validManifest(),
      measurements: [
        { id: 'cochlear_a_value', value_mm: 9.1, structures: ['bony_labyrinth'] },
        { id: 'something_new', value_mm: 1, structures: [] },
      ],
    });
    expect(m.measurements).toEqual([{ id: 'cochlear_a_value', valueMm: 9.1, structures: ['bony_labyrinth'] }]);
    expect(parseManifest(validManifest()).measurements).toEqual([]);
  });

  it('reads whether a structure starts hidden', () => {
    expect(parseManifest(validManifest()).structures[0]?.defaultVisible).toBe(true);
    expect(parseManifest(withStructure({ default_visible: false })).structures[0]?.defaultVisible).toBe(false);
    expect(() => parseManifest(withStructure({ default_visible: 'no' }))).toThrow(/default_visible/);
  });

  it('accepts a structure with no Arabic or Latin name yet', () => {
    const m = parseManifest(withStructure({ names: { en: 'Sigmoid sinus and dura', ar: null, latin: null } }));
    expect(m.structures[0]?.names.ar).toBeNull();
  });
});

describe('specimen index', () => {
  it('parses the list of installed specimens', () => {
    expect(parseSpecimenIndex({ specimens: [{ id: 'OPENEAR-ZETA', path: 'OPENEAR-ZETA' }] })).toEqual([
      { id: 'OPENEAR-ZETA', path: 'OPENEAR-ZETA', dataset: null, side: null },
    ]);
  });

  it('refuses paths that are not plain folder names', () => {
    expect(() => parseSpecimenIndex({ specimens: [{ id: 'x', path: '../x' }] })).toThrow(/plain folder name/);
  });
});
