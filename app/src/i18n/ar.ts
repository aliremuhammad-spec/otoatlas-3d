import type { MessageKey } from './en';

/**
 * Arabic message catalog. Interface wording only; anatomical terms live in the
 * ontology, where each Arabic term carries its own review status.
 */
export const ar: Record<MessageKey, string> = {
  'app.name': 'OtoAtlas 3D',
  'app.tagline': 'أطلس تشريحي ثلاثي الأبعاد للأذن الوسطى والداخلية',
  'credit.supervision': 'تم تصميم التطبيق بإشراف د. علي ر. محمد',

  'nav.home': 'الرئيسية',
  'nav.viewer': 'العارض',
  'nav.about': 'حول التطبيق',
  'nav.settings': 'الإعدادات',
  'nav.back': 'رجوع',

  'splash.continue': 'متابعة',

  'home.intro':
    'استكشف تشريح العظم الصدغي من عيّنات حقيقية، وخذ القياسات، وتدرّب على الخطوات الأساسية في جراحة الأذن.',
  'home.openViewer': 'افتح العارض',
  'home.phaseNote': 'نسخة أولية: يعرض العارض مجسّماً اختبارياً اصطناعياً إلى أن يُثبَّت محتوى العيّنات.',

  'disclaimer.title': 'للاستخدام التعليمي فقط',
  'disclaimer.body':
    'هذا البرنامج تعليمي. ليس جهازاً طبياً، ولا يجوز استخدامه للتشخيص أو لتخطيط جراحة لمريض بعينه.',

  'about.title': 'حول التطبيق',
  'about.version': 'الإصدار {version}',
  'about.dataTitle': 'البيانات والمصادر',
  'about.dataNone': 'لا تتضمن هذه النسخة بيانات عيّنات.',
  'about.dataPlanned': 'مجموعات البيانات المعتمدة للنسخ القادمة، وكلتاهما برخصة CC BY 4.0:',

  'settings.title': 'الإعدادات',
  'settings.language': 'اللغة',
  'settings.numerals': 'الأرقام',
  'settings.numerals.western': 'غربية (0-9)',
  'settings.numerals.eastern': 'عربية مشرقية (٠-٩)',

  'viewer.title': 'العارض',
  'viewer.phantomBadge': 'مجسّم اختباري اصطناعي، ليس تشريحاً',
  'viewer.specimen': 'العيّنة: {id}',
  'viewer.specimenSelect': 'العيّنة',
  'viewer.phantomOption': 'مجسّم اختباري',
  'viewer.loading': 'جارٍ تحميل العيّنة…',
  'viewer.loadError': 'تعذّر تحميل هذه العيّنة.',
  'viewer.draftBadge': 'مسودة: لم يراجعها خبير بعد',
  'viewer.dataSource': 'البيانات: doi:{doi}، {license}',
  'viewer.measure.sourceVoxel': 'حجم فوكسل المصدر: {size} مم',
  'viewer.structures': 'البنى',
  'viewer.show': 'إظهار',
  'viewer.opacity': 'الشفافية',
  'viewer.isolate': 'عزل',
  'viewer.showAll': 'إظهار الكل',
  'viewer.measure.title': 'القياس',
  'viewer.measure.pointToPoint': 'من نقطة إلى نقطة',
  'viewer.measure.surfaceToSurface': 'أقرب مسافة بين سطحين',
  'viewer.measure.hintPoints': 'انقر نقطتين على السطح.',
  'viewer.measure.hintSurfaces': 'اختر بنيتين.',
  'viewer.measure.clear': 'مسح',
  'viewer.measure.distance': 'المسافة',
  'viewer.measure.method': 'الطريقة',
  'viewer.measure.method.p2p': 'خط مستقيم بين نقطتين محدّدتين على السطح',
  'viewer.measure.method.s2s': 'أصغر مسافة بين سطحين مثلّثيّين',
  'viewer.measure.none': 'لا يوجد قياس بعد.',
  'viewer.webglError': 'هذا الجهاز أو المتصفح لا يستطيع تشغيل الرسوم ثلاثية الأبعاد.',

  'phantom.sphereA': 'كرة اختبارية أ (نصف القطر 3 مم)',
  'phantom.sphereB': 'كرة اختبارية ب (نصف القطر 2 مم)',
  'phantom.torus': 'حلقة اختبارية (نصفا القطرين 4 و0.5 مم)',

  'units.mm': 'مم',
};
