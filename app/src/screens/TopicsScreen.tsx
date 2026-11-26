import { useEffect, useMemo, useRef, useState } from 'react';
import { SupervisionCredit } from '../components/SupervisionCredit';
import { useI18n } from '../i18n/I18nProvider';
import { localizeDigits } from '../i18n/numerals';
import { pick, searchTopics, SECTIONS, topicById } from '../topics/topics';
import { TopicReader } from './TopicReader';

interface Props {
  onBack: () => void;
  /** Opens the viewer with these structures shown and the first one selected. */
  onShowIn3d: (ids: readonly string[]) => void;
  initialTopic?: string;
}

/** The chapter's topics: a searchable list by section, and one topic at a time to read. */
export function TopicsScreen({ onBack, onShowIn3d, initialTopic }: Props) {
  const { t, locale, numerals } = useI18n();
  const [query, setQuery] = useState('');
  const [openId, setOpenId] = useState<string | null>(initialTopic ?? null);
  const topRef = useRef<HTMLDivElement>(null);
  const matches = useMemo(() => new Set(searchTopics(query).map((x) => x.id)), [query]);
  const open = openId ? topicById(openId) : null;

  // A newly opened topic (or the list again) starts at the top, not where the last one was scrolled to.
  useEffect(() => {
    const page = topRef.current;
    if (page && typeof page.scrollIntoView === 'function') page.scrollIntoView({ block: 'start' });
  }, [openId]);

  return (
    <div className="page" data-testid="topics-screen" ref={topRef}>
      <header className="page__header">
        <button type="button" onClick={open ? () => setOpenId(null) : onBack}>
          {open ? t('topics.backToList') : t('nav.back')}
        </button>
        <h1>{t('topics.title')}</h1>
      </header>
      <main className="page__body topics">
        {open ? (
          <TopicReader topic={open} onShow={onShowIn3d} />
        ) : (
          <>
            <p className="lead">{t('topics.intro')}</p>
            <label className="topics__search">
              <span className="visually-hidden">{t('topics.search')}</span>
              <input
                type="search"
                value={query}
                placeholder={t('topics.search')}
                onChange={(e) => setQuery(e.target.value)}
                data-testid="topics-search"
              />
            </label>
            <p className="note" aria-live="polite">
              {t('topics.count', { count: localizeDigits(String(matches.size), numerals) })}
            </p>
            {matches.size === 0 && <p>{t('topics.noResults')}</p>}
            {SECTIONS.map((section) => {
              const listed = section.topics.filter((x) => matches.has(x.id));
              if (listed.length === 0) return null;
              return (
                <section key={section.id} className="topics__section">
                  <h2>{pick(section.title, locale)}</h2>
                  <ul>
                    {listed.map((topic) => (
                      <li key={topic.id}>
                        <button type="button" className="topics__item" onClick={() => setOpenId(topic.id)}>
                          {pick(topic.title, locale)}
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </>
        )}
      </main>
      <footer className="page__footer">
        <SupervisionCredit variant="footer" />
      </footer>
    </div>
  );
}
