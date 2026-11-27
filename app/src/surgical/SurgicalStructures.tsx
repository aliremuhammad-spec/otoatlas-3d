import { useI18n } from '../i18n/I18nProvider';
import { displayName } from '../viewer/names';
import type { SurgicalStructure } from './loadColour';
import { isolate, type StructureState } from './lut';

interface Props {
  structures: readonly SurgicalStructure[];
  state: StructureState;
  onChange: (next: StructureState) => void;
}

function hex(color: number): string {
  return `#${color.toString(16).padStart(6, '0')}`;
}

/**
 * The structure list of the surgical screen: show or hide each structure of the label volume, keep only one,
 * or tint every structure with its atlas colour. It belongs to this screen; the viewer has its own list.
 */
export function SurgicalStructures({ structures, state, onChange }: Props) {
  const { t, locale } = useI18n();
  const ids = structures.map((s) => s.id);
  const groups = new Map<string, { title: string; items: SurgicalStructure[] }>();
  for (const s of structures) {
    const key = s.group?.id ?? '';
    const entry = groups.get(key) ?? { title: s.group ? displayName(s.group.names, locale) : t('surgical.structures.other'), items: [] };
    entry.items.push(s);
    groups.set(key, entry);
  }
  const toggle = (id: string) => {
    const hidden = new Set(state.hidden);
    if (hidden.has(id)) hidden.delete(id);
    else hidden.add(id);
    onChange({ ...state, hidden });
  };

  return (
    <details className="surgical__structures" open data-testid="surgical-structures">
      <summary>{t('surgical.structures.title', { shown: structures.length - state.hidden.size, total: structures.length })}</summary>
      <div className="surgical__structures-actions">
        <button
          type="button"
          onClick={() => onChange({ ...state, hidden: new Set() })}
          disabled={state.hidden.size === 0}
          data-testid="surgical-show-all"
        >
          {t('surgical.structures.showAll')}
        </button>
        <label>
          <input
            type="checkbox"
            checked={state.tinted}
            onChange={(e) => onChange({ ...state, tinted: e.target.checked })}
            data-testid="surgical-tint"
          />{' '}
          {t('surgical.structures.tint')}
        </label>
      </div>
      {[...groups.entries()].map(([key, g]) => (
        <section key={key} aria-label={g.title}>
          <h3>{g.title}</h3>
          <ul>
            {g.items.map((s) => {
              const name = displayName(s.names, locale);
              return (
                <li key={s.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={!state.hidden.has(s.id)}
                      onChange={() => toggle(s.id)}
                      data-testid={`surgical-structure-${s.id}`}
                    />{' '}
                    <span className="surgical__swatch" style={{ background: hex(s.color) }} aria-hidden="true" />
                    {name}
                  </label>
                  <button
                    type="button"
                    onClick={() => onChange({ ...state, hidden: isolate(ids, s.id) })}
                    aria-label={t('surgical.structures.isolateOne', { name })}
                    data-testid={`surgical-isolate-${s.id}`}
                  >
                    {t('surgical.structures.isolate')}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </details>
  );
}
