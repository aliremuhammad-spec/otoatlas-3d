import { useCallback, useState } from 'react';
import { About } from './screens/About';
import { Home } from './screens/Home';
import { Settings } from './screens/Settings';
import { Splash } from './screens/Splash';
import { SurgicalScreen } from './screens/SurgicalScreen';
import { TopicsScreen } from './screens/TopicsScreen';
import { ViewerScreen } from './screens/ViewerScreen';

export type ScreenId = 'splash' | 'home' | 'viewer' | 'about' | 'settings' | 'topics' | 'surgical';

interface Props {
  /** First screen to show. Tests start on a specific screen. */
  initialScreen?: ScreenId;
}

export function App({ initialScreen = 'splash' }: Props) {
  const [screen, setScreen] = useState<ScreenId>(initialScreen);
  // Structures a topic asked to show; the viewer selects the first one on the open specimen.
  const [focus, setFocus] = useState<readonly string[] | null>(null);
  const goHome = useCallback(() => {
    setFocus(null);
    setScreen('home');
  }, []);
  const showIn3d = useCallback((ids: readonly string[]) => {
    setFocus(ids);
    setScreen('viewer');
  }, []);

  switch (screen) {
    case 'splash':
      return <Splash onDone={goHome} />;
    case 'viewer':
      return <ViewerScreen onBack={goHome} focus={focus} />;
    case 'surgical':
      return <SurgicalScreen onBack={goHome} />;
    case 'topics':
      return <TopicsScreen onBack={goHome} onShowIn3d={showIn3d} />;
    case 'about':
      return <About onBack={goHome} />;
    case 'settings':
      return <Settings onBack={goHome} />;
    case 'home':
      return <Home onNavigate={setScreen} />;
  }
}
