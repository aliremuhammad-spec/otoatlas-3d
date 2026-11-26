import type { Locale } from '../i18n/translate';

/**
 * Reading texts for every topic of the reference chapter, one file per chapter section in
 * `ontology/topics/`. They are built into the app (not into specimen packages), so a text can
 * be corrected without rebuilding any specimen.
 */

export interface Bilingual {
  en: string;
  ar: string;
}

export const TOPIC_UNITS = ['mm', 'ml', 'deg', 'percent', 'count'] as const;
export type TopicUnit = (typeof TOPIC_UNITS)[number];

export interface TopicNumber {
  label: Bilingual;
  /** A figure with its unit, or `text` for a figure that needs words ("1 in 2,000 births"). */
  value: string | null;
  unit: TopicUnit | null;
  text: Bilingual | null;
  source: { ref: string; page: number | null };
}

export interface Topic {
  id: string;
  section: string;
  title: Bilingual;
  /** Ontology ids of the structures the topic is about; a structure may belong to several topics. */
  structures: readonly string[];
  overview: Bilingual;
  surgical: Bilingual | null;
  variants: Bilingual | null;
  numbers: readonly TopicNumber[];
}

export interface TopicSection {
  id: string;
  title: Bilingual;
  topics: readonly Topic[];
}

export interface TopicSource {
  en: string;
  ar: string;
}

function fail(message: string): never {
  throw new Error(`topics: ${message}`);
}

function obj(v: unknown, what: string): Record<string, unknown> {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) fail(`${what} is not an object`);
  return v as Record<string, unknown>;
}

function str(v: unknown, what: string): string {
  if (typeof v !== 'string' || v.trim() === '') fail(`${what} is not a non-empty string`);
  return v;
}

function bilingual(v: unknown, what: string): Bilingual {
  const o = obj(v, what);
  return { en: str(o.en, `${what}.en`), ar: str(o.ar, `${what}.ar`) };
}

function optionalBilingual(v: unknown, what: string): Bilingual | null {
  return v === undefined ? null : bilingual(v, what);
}

function parseNumber(v: unknown, what: string, sources: ReadonlySet<string>): TopicNumber {
  const o = obj(v, what);
  const source = obj(o.source, `${what}.source`);
  const ref = str(source.ref, `${what}.source.ref`);
  if (!sources.has(ref)) fail(`${what}.source.ref ${ref} is not a known source`);
  let page: number | null = null;
  if (source.page !== undefined) {
    if (typeof source.page !== 'number' || !Number.isInteger(source.page)) fail(`${what}.source.page is not a page number`);
    page = source.page;
  }
  const text = optionalBilingual(o.text, `${what}.text`);
  let value: string | null = null;
  let unit: TopicUnit | null = null;
  if (text === null) {
    value = str(o.value, `${what}.value`);
    if (!(TOPIC_UNITS as readonly unknown[]).includes(o.unit)) fail(`${what}.unit is not one of ${TOPIC_UNITS.join(', ')}`);
    unit = o.unit as TopicUnit;
  } else if (o.value !== undefined) {
    fail(`${what} has both a value and a text`);
  }
  return { label: bilingual(o.label, `${what}.label`), value, unit, text, source: { ref, page } };
}

/** Parses one section file. Unknown sources and malformed entries are errors, never skipped. */
export function parseSection(value: unknown, file: string, sources: ReadonlySet<string>): TopicSection {
  const o = obj(value, file);
  const id = str(o.section, `${file}.section`);
  if (!Array.isArray(o.topics) || o.topics.length === 0) fail(`${file}.topics is not a non-empty list`);
  const topics = o.topics.map((entry, i): Topic => {
    const what = `${file}.topics[${i}]`;
    const t = obj(entry, what);
    if (!Array.isArray(t.structures)) fail(`${what}.structures is not a list`);
    if (!Array.isArray(t.numbers)) fail(`${what}.numbers is not a list`);
    return {
      id: str(t.id, `${what}.id`),
      section: id,
      title: bilingual(t.title, `${what}.title`),
      structures: t.structures.map((s, j) => str(s, `${what}.structures[${j}]`)),
      overview: bilingual(t.overview, `${what}.overview`),
      surgical: optionalBilingual(t.surgical, `${what}.surgical`),
      variants: optionalBilingual(t.variants, `${what}.variants`),
      numbers: t.numbers.map((n, j) => parseNumber(n, `${what}.numbers[${j}]`, sources)),
    };
  });
  return { id, title: bilingual(o.title, `${file}.title`), topics };
}

export function parseSources(value: unknown): Readonly<Record<string, TopicSource>> {
  const o = obj(obj(value, 'sources file').sources, 'sources');
  return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, bilingual(v, `sources.${k}`)]));
}

/** Arabic, English and Latin names of every ontology structure, for topics read outside a specimen. */
export function parseStructureNames(value: unknown): ReadonlyMap<string, { en: string; ar: string | null }> {
  const list = obj(value, 'structures file').structures;
  if (!Array.isArray(list)) fail('structures file has no structure list');
  return new Map(
    list.map((s, i) => {
      const o = obj(s, `structures[${i}]`);
      const ar = typeof o.name_ar === 'string' && o.name_ar.trim() !== '' ? o.name_ar : null;
      return [str(o.id, `structures[${i}].id`), { en: str(o.name_en, `structures[${i}].name_en`), ar }];
    }),
  );
}

const sectionFiles = import.meta.glob('../../../ontology/topics/0*.json', { eager: true, import: 'default' });
const sourceFile = import.meta.glob('../../../ontology/topics/_sources.json', { eager: true, import: 'default' });
const structureFile = import.meta.glob('../../../ontology/structures.json', { eager: true, import: 'default' });

export const SOURCES = parseSources(Object.values(sourceFile)[0]);
const sourceIds = new Set(Object.keys(SOURCES));

/** The chapter's sections in reading order (the file names carry the order). */
export const SECTIONS: readonly TopicSection[] = Object.keys(sectionFiles)
  .sort()
  .map((path) => parseSection(sectionFiles[path], path.split('/').pop() ?? path, sourceIds));

export const STRUCTURE_NAMES = parseStructureNames(Object.values(structureFile)[0]);

const byId = new Map<string, Topic>();
for (const section of SECTIONS) {
  for (const topic of section.topics) {
    if (byId.has(topic.id)) fail(`topic id ${topic.id} is used twice`);
    byId.set(topic.id, topic);
  }
}

export function topicById(id: string): Topic | null {
  return byId.get(id) ?? null;
}

/** Topics about a structure, in reading order. */
export function topicsForStructure(id: string): Topic[] {
  return SECTIONS.flatMap((s) => s.topics.filter((t) => t.structures.includes(id)));
}

export function pick(text: Bilingual, locale: Locale): string {
  return locale === 'ar' ? text.ar : text.en;
}

/** Lower-case text without Arabic diacritics, for matching a search against titles and texts. */
export function normaliseForSearch(text: string): string {
  return text.toLowerCase().replace(/[ً-ْـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه');
}

/** Topics whose title or text contains every word of the query, in either language. */
export function searchTopics(query: string): Topic[] {
  const words = normaliseForSearch(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [...byId.values()];
  return [...byId.values()].filter((t) => {
    const hay = normaliseForSearch(
      [t.title, t.overview, t.surgical, t.variants]
        .filter((b): b is Bilingual => b !== null)
        .map((b) => `${b.en} ${b.ar}`)
        .join(' '),
    );
    return words.every((w) => hay.includes(w));
  });
}
