import { act, render, screen } from '@testing-library/react';
import { App, type ScreenId } from './App';
import { ar } from './i18n/ar';
import { en } from './i18n/en';
import { I18nProvider } from './i18n/I18nProvider';
import type { Locale } from './i18n/translate';
import { SPLASH_MIN_MS } from './screens/Splash';

const CREDIT: Record<Locale, string> = {
  en: en['credit.supervision'],
  ar: ar['credit.supervision'],
};

function renderApp(locale: Locale, initialScreen: ScreenId) {
  return render(
    <I18nProvider initialLocale={locale}>
      <App initialScreen={initialScreen} />
    </I18nProvider>,
  );
}

describe.each(['en', 'ar'] as const)('supervision credit (%s)', (locale) => {
  it('is on the splash screen', () => {
    renderApp(locale, 'splash');
    expect(screen.getByTestId('splash-screen')).toHaveTextContent(CREDIT[locale]);
  });

  it('is on the home screen footer', () => {
    renderApp(locale, 'home');
    const footer = screen.getByTestId('home-screen').querySelector('footer');
    expect(footer).toHaveTextContent(CREDIT[locale]);
  });

  it('is at the top of the About screen, above the version and the data credits', () => {
    renderApp(locale, 'about');
    const credit = screen.getByTestId('supervision-credit');
    const version = screen.getByTestId('app-version');
    const data = screen.getByTestId('data-credits');
    expect(credit).toHaveTextContent(CREDIT[locale]);
    const follows = Node.DOCUMENT_POSITION_FOLLOWING;
    expect(credit.compareDocumentPosition(version) & follows).toBeTruthy();
    expect(version.compareDocumentPosition(data) & follows).toBeTruthy();
  });
});

describe('splash screen', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('stays for at least two seconds, then opens the home screen', () => {
    expect(SPLASH_MIN_MS).toBeGreaterThanOrEqual(2000);
    renderApp('en', 'splash');
    act(() => vi.advanceTimersByTime(1999));
    expect(screen.getByTestId('splash-screen')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(SPLASH_MIN_MS));
    expect(screen.getByTestId('home-screen')).toBeInTheDocument();
  });
});

describe('language and direction', () => {
  it('sets right-to-left direction for Arabic and left-to-right for English', () => {
    const first = renderApp('ar', 'home');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
    first.unmount();
    renderApp('en', 'home');
    expect(document.documentElement.dir).toBe('ltr');
  });

  it('shows the disclaimer on the home screen in Arabic', () => {
    renderApp('ar', 'home');
    expect(screen.getByTestId('home-screen')).toHaveTextContent(ar['disclaimer.body']);
  });

  it('switches language from Settings without a reload', () => {
    renderApp('en', 'settings');
    act(() => screen.getByLabelText('العربية').click());
    expect(screen.getByTestId('settings-screen')).toHaveTextContent(ar['settings.title']);
    expect(document.documentElement.dir).toBe('rtl');
  });
});
