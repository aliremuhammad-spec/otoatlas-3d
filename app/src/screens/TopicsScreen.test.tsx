import { fireEvent, render, screen, within } from '@testing-library/react';
import { I18nProvider } from '../i18n/I18nProvider';
import type { Locale } from '../i18n/translate';
import { TopicsScreen } from './TopicsScreen';

function renderTopics(locale: Locale, onShowIn3d = vi.fn()) {
  render(
    <I18nProvider initialLocale={locale}>
      <TopicsScreen onBack={() => undefined} onShowIn3d={onShowIn3d} />
    </I18nProvider>,
  );
  return onShowIn3d;
}

describe('topics screen', () => {
  it('opens a topic, shows its figures with their page, and asks to show its structures in 3D', () => {
    const onShow = renderTopics('en');
    fireEvent.click(screen.getByRole('button', { name: 'Tympanic membrane: size, tilt and landmarks' }));
    const reader = screen.getByTestId('topic-reader');
    expect(within(reader).getByText('8.5–10 mm')).toBeInTheDocument();
    expect(reader).toHaveTextContent('p. 438');
    expect(reader).toHaveTextContent('Draft written by Claude');
    fireEvent.click(within(reader).getByTestId('topic-show'));
    expect(onShow).toHaveBeenCalledWith(expect.arrayContaining(['tympanic_membrane', 'malleus_handle']));
  });

  it('filters the list by a search', () => {
    renderTopics('en');
    fireEvent.change(screen.getByTestId('topics-search'), { target: { value: 'Huschke' } });
    expect(screen.getByRole('button', { name: /foramen of Huschke/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cochlea' })).toBeNull();
  });

  it('reads in Arabic, with the credit in the footer', () => {
    renderTopics('ar');
    fireEvent.click(screen.getByRole('button', { name: 'القوقعة' }));
    expect(screen.getByTestId('topic-reader')).toHaveTextContent('الأهمية الجراحية');
    expect(screen.getByTestId('topics-screen').querySelector('footer')).toHaveTextContent('تم تصميم التطبيق بإشراف د. علي ر. محمد');
  });

  it('says when a topic has nothing in the 3D model', () => {
    renderTopics('en');
    fireEvent.click(screen.getByRole('button', { name: 'Auricle: shape and landmarks' }));
    expect(screen.getByTestId('topic-reader')).toHaveTextContent('no structure in the 3D model yet');
    expect(screen.queryByTestId('topic-show')).toBeNull();
  });
});
