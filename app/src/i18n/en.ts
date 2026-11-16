/**
 * English message catalog. Every user-visible string lives in a catalog;
 * components never hard-code text. Keys are shared with `ar.ts`.
 */
export const en = {
  'app.name': 'OtoAtlas 3D',
  'app.tagline': '3D anatomy atlas of the middle and inner ear',
  'credit.supervision': 'Designed under the supervision of Dr. Ali R. Muhammad',

  'nav.home': 'Home',
  'nav.viewer': 'Viewer',
  'nav.about': 'About',
  'nav.settings': 'Settings',
  'nav.back': 'Back',

  'splash.continue': 'Continue',

  'home.intro':
    'Explore temporal-bone anatomy from real specimens, measure it, and rehearse the key steps of ear surgery.',
  'home.openViewer': 'Open the viewer',
  'home.phaseNote': 'Early build: the viewer shows a synthetic test phantom until specimen content is installed.',

  'disclaimer.title': 'Educational use only',
  'disclaimer.body':
    'This software is for education. It is not a medical device and must not be used for diagnosis or for planning surgery on an individual patient.',

  'about.title': 'About',
  'about.version': 'Version {version}',
  'about.dataTitle': 'Data and credits',
  'about.dataNone': 'No specimen data is bundled in this build.',
  'about.dataPlanned': 'Datasets cleared for use in coming builds, both under CC BY 4.0:',

  'settings.title': 'Settings',
  'settings.language': 'Language',
  'settings.numerals': 'Numerals',
  'settings.numerals.western': 'Western (0-9)',
  'settings.numerals.eastern': 'Eastern Arabic (٠-٩)',

  'viewer.title': 'Viewer',
  'viewer.phantomBadge': 'Synthetic test phantom, not anatomy',
  'viewer.specimen': 'Specimen: {id}',
  'viewer.specimenSelect': 'Specimen',
  'viewer.phantomOption': 'Test phantom',
  'viewer.loading': 'Loading specimen…',
  'viewer.loadError': 'This specimen could not be loaded.',
  'viewer.draftBadge': 'Draft: not yet reviewed by an expert',
  'viewer.dataSource': 'Data: doi:{doi}, {license}',
  'viewer.measure.sourceVoxel': 'Source voxel size: {size} mm',
  'viewer.structures': 'Structures',
  'viewer.show': 'Show',
  'viewer.opacity': 'Opacity',
  'viewer.isolate': 'Isolate',
  'viewer.showAll': 'Show all',
  'viewer.measure.title': 'Measure',
  'viewer.measure.pointToPoint': 'Point to point',
  'viewer.measure.surfaceToSurface': 'Closest surfaces',
  'viewer.measure.hintPoints': 'Tap two points on a surface.',
  'viewer.measure.hintSurfaces': 'Choose two structures.',
  'viewer.measure.clear': 'Clear',
  'viewer.measure.distance': 'Distance',
  'viewer.measure.method': 'Method',
  'viewer.measure.method.p2p': 'Straight line between two picked surface points',
  'viewer.measure.method.s2s': 'Minimum distance between two triangulated surfaces',
  'viewer.measure.none': 'No measurement yet.',
  'viewer.webglError': 'This device or browser cannot start 3D graphics.',

  'phantom.sphereA': 'Phantom sphere A (radius 3 mm)',
  'phantom.sphereB': 'Phantom sphere B (radius 2 mm)',
  'phantom.torus': 'Phantom ring (radii 4 and 0.5 mm)',

  'units.mm': 'mm',
} as const;

export type MessageKey = keyof typeof en;
