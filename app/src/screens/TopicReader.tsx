import { useI18n } from '../i18n/I18nProvider';
import { localizeDigits } from '../i18n/numerals';
import { pick, SOURCES, STRUCTURE_NAMES, type Topic, type TopicNumber } from '../topics/topics';

interface Props {
  topic: Topic;
  /**
   * Shows the topic's structures in 3D. Absent where there is nowhere to show them; given a
   * list, only the listed structures get a button (those present on the open specimen).
   */
  onShow?: (ids: readonly string[]) => void;
  showable?: ReadonlySet<string>;
  /** Heading level of the title, so the reader fits the page it sits in. */
  level?: 2 | 3;
}

function NumberRow({ n }: { n: TopicNumber }) {
  const { t, locale, numerals } = useI18n();
  let figure: string;
  if (n.text) figure = localizeDigits(pick(n.text, locale), numerals);
  else {
    const value = localizeDigits(n.value ?? '', numerals);
    figure =
      n.unit === 'count'
        ? value
        : n.unit === 'deg' || n.unit === 'percent'
          ? `${value}${t(n.unit === 'deg' ? 'units.deg' : 'units.percent')}`
          : `${value} ${t(n.unit === 'ml' ? 'units.ml' : 'units.mm')}`;
  }
  const source = SOURCES[n.source.ref];
  return (
    <tr>
      <th scope="row">{localizeDigits(pick(n.label, locale), numerals)}</th>
      <td className="topic__figure" dir="auto">
        {figure}
      </td>
      <td className="topic__source">
        {source ? pick(source, locale) : n.source.ref}
        {n.source.page !== null && `${locale === 'ar' ? '، ' : ', '}${t('topics.page', { page: localizeDigits(String(n.source.page), numerals) })}`}
      </td>
    </tr>
  );
}

/** One topic: its text in the current language, its figures with their sources, and its structures. */
export function TopicReader({ topic, onShow, showable, level = 2 }: Props) {
  const { t, locale, numerals } = useI18n();
  const Title = level === 2 ? 'h2' : 'h3';
  const Sub = level === 2 ? 'h3' : 'h4';
  const shown = showable ? topic.structures.filter((id) => showable.has(id)) : topic.structures;
  return (
    <article className="topic" data-testid="topic-reader" aria-label={pick(topic.title, locale)}>
      <Title className="topic__title">{pick(topic.title, locale)}</Title>
      <p className="topic__draft">{t('topics.draft')}</p>
      <section>
        <Sub>{t('topics.overview')}</Sub>
        <p>{localizeDigits(pick(topic.overview, locale), numerals)}</p>
      </section>
      {topic.surgical && (
        <section>
          <Sub>{t('topics.surgical')}</Sub>
          <p>{localizeDigits(pick(topic.surgical, locale), numerals)}</p>
        </section>
      )}
      {topic.variants && (
        <section>
          <Sub>{t('topics.variants')}</Sub>
          <p>{localizeDigits(pick(topic.variants, locale), numerals)}</p>
        </section>
      )}
      {topic.numbers.length > 0 && (
        <section>
          <Sub>{t('topics.numbers')}</Sub>
          <div className="topic__table-wrap">
            <table className="topic__numbers">
              <tbody>
                {topic.numbers.map((n, i) => (
                  <NumberRow key={i} n={n} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <section>
        <Sub>{t('topics.structures')}</Sub>
        {topic.structures.length === 0 ? (
          <p className="note">{t('topics.notIn3d')}</p>
        ) : (
          <>
            <ul className="topic__structures">
              {topic.structures.map((id) => {
                const names = STRUCTURE_NAMES.get(id);
                return <li key={id}>{names ? (locale === 'ar' ? (names.ar ?? names.en) : names.en) : id}</li>;
              })}
            </ul>
            {onShow && shown.length > 0 && (
              <button type="button" className="primary" onClick={() => onShow(shown)} data-testid="topic-show">
                {t('topics.showIn3d')}
              </button>
            )}
          </>
        )}
      </section>
    </article>
  );
}
