import { useEffect, useMemo, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import type { SceneContent } from '../viewer/content';
import { listSpecimens, loadPackage } from '../viewer/loadPackage';
import type { SpecimenIndexEntry } from '../viewer/manifest';
import { createPhantom } from '../viewer/phantom';
import { SpecimenView } from './SpecimenView';

const PHANTOM = 'phantom';

interface Props {
  onBack: () => void;
}

export function ViewerScreen({ onBack }: Props) {
  const { t } = useI18n();
  const phantom = useMemo(createPhantom, []);
  const [specimens, setSpecimens] = useState<readonly SpecimenIndexEntry[]>([]);
  const [selected, setSelected] = useState<string>(PHANTOM);
  const [content, setContent] = useState<SceneContent>(phantom);
  const [status, setStatus] = useState<'ready' | 'loading' | 'error'>('ready');

  // Installed specimens take precedence over the phantom: open the first one found.
  useEffect(() => {
    let cancelled = false;
    void listSpecimens().then((found) => {
      if (cancelled || found.length === 0) return;
      setSpecimens(found);
      setSelected(found[0]?.path ?? PHANTOM);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selected === PHANTOM) {
      setContent(phantom);
      setStatus('ready');
      return undefined;
    }
    let cancelled = false;
    setStatus('loading');
    loadPackage(selected).then(
      (loaded) => {
        if (cancelled) return;
        setContent(loaded);
        setStatus('ready');
      },
      () => {
        if (!cancelled) setStatus('error');
      },
    );
    return () => {
      cancelled = true;
    };
  }, [selected, phantom]);

  return (
    <div className="viewer" data-testid="viewer-screen">
      <header className="page__header">
        <button type="button" onClick={onBack}>
          {t('nav.back')}
        </button>
        <h1>{t('viewer.title')}</h1>
        <label className="specimen-select">
          <span>{t('viewer.specimenSelect')}</span>
          <select value={selected} onChange={(e) => setSelected(e.target.value)} data-testid="specimen-select">
            {specimens.map((s) => (
              <option key={s.path} value={s.path}>
                {s.id}
              </option>
            ))}
            <option value={PHANTOM}>{t('viewer.phantomOption')}</option>
          </select>
        </label>
      </header>
      {status === 'ready' ? (
        <SpecimenView key={content.specimenId} content={content} />
      ) : (
        <div className="viewer__stage viewer__stage--message" role="status">
          {t(status === 'loading' ? 'viewer.loading' : 'viewer.loadError')}
        </div>
      )}
    </div>
  );
}
