import { useCallback, useState } from 'react';
import { About } from './screens/About';
import { Home } from './screens/Home';
import { Settings } from './screens/Settings';
import { Splash } from './screens/Splash';
import { ViewerScreen } from './screens/ViewerScreen';

export type ScreenId = 'splash' | 'home' | 'viewer' | 'about' | 'settings';

interface Props {
  /** First screen to show. Tests start on a specific screen. */
  initialScreen?: ScreenId;
}

export function App({ initialScreen = 'splash' }: Props) {
  const [screen, setScreen] = useState<ScreenId>(initialScreen);
  const goHome = useCallback(() => setScreen('home'), []);

  switch (screen) {
    case 'splash':
      return <Splash onDone={goHome} />;
    case 'viewer':
      return <ViewerScreen onBack={goHome} />;
    case 'about':
      return <About onBack={goHome} />;
    case 'settings':
      return <Settings onBack={goHome} />;
    case 'home':
      return <Home onNavigate={setScreen} />;
  }
}
