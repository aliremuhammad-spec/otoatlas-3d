import { parseSection, searchTopics, SECTIONS, SOURCES, STRUCTURE_NAMES, topicById, topicsForStructure } from './topics';

const all = SECTIONS.flatMap((s) => s.topics);

describe('chapter topics', () => {
  it('cover the eight sections of the chapter in reading order', () => {
    expect(SECTIONS.map((s) => s.id)).toEqual([
      'temporal_bone',
      'external_ear',
      'middle_ear',
      'pneumatization',
      'middle_ear_vessels_nerves',
      'inner_ear',
      'internal_auditory_canal',
      'facial_nerve',
    ]);
    expect(all.length).toBeGreaterThanOrEqual(70);
  });

  it('link only to structures of the ontology', () => {
    for (const t of all) for (const id of t.structures) expect(STRUCTURE_NAMES.has(id), `${t.id}: ${id}`).toBe(true);
  });

  it('give every figure a known source, and a page for the chapter', () => {
    for (const t of all) {
      for (const n of t.numbers) {
        expect(SOURCES[n.source.ref], `${t.id}`).toBeDefined();
        if (n.source.ref === 'janfaza') expect(n.source.page, `${t.id}: ${n.label.en}`).toBeGreaterThanOrEqual(421);
        expect(n.value !== null || n.text !== null).toBe(true);
      }
    }
  });

  it('give every Arabic text Arabic script', () => {
    for (const t of all) {
      for (const b of [t.title, t.overview, t.surgical, t.variants]) if (b) expect(b.ar, t.id).toMatch(/[؀-ۿ]/);
    }
  });

  it('find the topics of a structure, and a structure in several topics', () => {
    const ids = topicsForStructure('facial_nerve').map((t) => t.id);
    expect(ids).toContain('facial_nerve_segments');
    expect(ids).toContain('facial_recess');
    expect(topicById('cochlea')?.section).toBe('inner_ear');
  });

  it('search in either language, ignoring hamza and diacritics', () => {
    expect(searchTopics('Prussak').map((t) => t.id)).toContain('mucosal_folds');
    expect(searchTopics('بروساك').map((t) => t.id)).toContain('mucosal_folds');
    expect(searchTopics('اوستاش').map((t) => t.id)).toContain('eustachian_tube');
    expect(searchTopics('')).toHaveLength(all.length);
  });

  it('refuse a figure without a known source or with both a value and a text', () => {
    const base = {
      section: 's',
      title: { en: 'S', ar: 'س' },
      topics: [
        {
          id: 't',
          title: { en: 'T', ar: 'ت' },
          structures: [],
          overview: { en: 'x', ar: 'س' },
          numbers: [{ label: { en: 'L', ar: 'ل' }, value: '1', unit: 'mm', source: { ref: 'nowhere' } }],
        },
      ],
    };
    expect(() => parseSection(base, 'f', new Set(['janfaza']))).toThrow(/not a known source/);
    const both = structuredClone(base);
    const [topic] = both.topics;
    const [figure] = topic?.numbers ?? [];
    if (figure) Object.assign(figure, { source: { ref: 'janfaza' }, text: { en: 'a', ar: 'ب' } });
    expect(() => parseSection(both, 'f', new Set(['janfaza']))).toThrow(/both a value and a text/);
  });
});
