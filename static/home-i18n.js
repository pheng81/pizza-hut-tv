(function () {
  'use strict';

  var STORAGE_KEY = 'everydayadvertise.language';
  var config = window.EA_HOME_I18N_CONFIG || {};
  var trialDays = Math.max(0, Number(config.trialDays) || 0);
  var freeScreens = Math.max(0, Number(config.freeScreens) || 0);

  function khmerPricingFeature() {
    if (trialDays > 0 && freeScreens > 0) {
      return 'សាកល្បងឥតគិតថ្លៃ ' + trialDays + ' ថ្ងៃ + អេក្រង់ ' + freeScreens + ' ដំបូងឥតគិតថ្លៃ';
    }
    if (trialDays > 0) {
      return 'សាកល្បងឥតគិតថ្លៃ ' + trialDays + ' ថ្ងៃ';
    }
    if (freeScreens > 0) {
      return 'អេក្រង់ ' + freeScreens + ' ដំបូងឥតគិតថ្លៃ';
    }
    return 'អាចបោះបង់បានគ្រប់ពេល';
  }

  function khmerPricingNote() {
    var parts = [];
    if (trialDays > 0) {
      parts.push('សាកល្បងឥតគិតថ្លៃរយៈពេល ' + trialDays + ' ថ្ងៃ។');
    }
    if (freeScreens > 0) {
      parts.push('អេក្រង់ ' + freeScreens + ' ដំបូងអាចប្រើបានមុនពេលចាប់ផ្តើមគិតថ្លៃ។');
    }
    parts.push('មិនត្រូវការកាតឥណទានទេ។');
    return parts.join(' ');
  }

  var translations = {
    km: {
      pageTitle: 'Everyday Advertise | កម្មវិធីផ្ទាំងម៉ឺនុយឌីជីថល',
      pageDescription: 'Everyday Advertise គឺជាកម្មវិធីផ្ទាំងម៉ឺនុយឌីជីថលសម្រាប់ភោជនីយដ្ឋាន ហាងកាហ្វេ ហាងតែគុជ ហាងប៊ឺហ្គឺ និងហាងលក់អាហារវេចខ្ចប់។',
      navFeatures: 'លក្ខណៈពិសេស',
      navPlatforms: 'វេទិកា',
      navSuperAdmin: 'អ្នកគ្រប់គ្រងកំពូល',
      navLogin: 'ចូល',
      languageLabel: 'ភាសា',
      contactLinksLabel: 'តំណទំនាក់ទំនង',
      contactTelegramLabel: 'ទាក់ទងតាម Telegram',
      contactWhatsAppLabel: 'ទាក់ទងតាម WhatsApp',
      heroTitleLine1: 'ប្រព័ន្ធម៉ឺនុយឌីជីថល',
      heroTitleLine2: 'ទំនើបបំផុត',
      heroSubtitle: 'ងាយស្រួលប្រើ។ មានអានុភាព។ ធ្វើសមកាលកម្មយ៉ាងល្អឥតខ្ចោះ។',
      heroPrimaryCta: 'ចាប់ផ្តើមឥតគិតថ្លៃ',
      heroSecondaryCta: 'មើលលក្ខណៈពិសេស',
      heroProofSecondary: 'រៀបចំក្នុងរយៈពេល 5 នាទី',
      heroProofTertiary: 'ជំនួយ 24/7',
      heroImageAlt: 'រូបភាពមើលជាមុននៃផ្ទាំងគ្រប់គ្រង EverydayAdvertise',
      carouselImageAlt: 'រូបភាពក្នុងស្លាយវេបសាយ',
      bodyMediaAlt: 'មេឌៀក្នុងវេបសាយ',
      previousSlideLabel: 'ស្លាយមុន',
      nextSlideLabel: 'ស្លាយបន្ទាប់',
      pricingTitle: 'តម្លៃសាមញ្ញ និងច្បាស់លាស់',
      pricingSubtitle: 'គ្មានថ្លៃលាក់បាំង។ គ្មានកិច្ចសន្យារយៈពេលវែង។ អាចបោះបង់បានគ្រប់ពេល។',
      pricePeriod: 'ក្នុងមួយអេក្រង់ / ខែ',
      pricingFeature: khmerPricingFeature(),
      pricingNote: khmerPricingNote(),
      standardFeatureUpdates: 'ធ្វើបច្ចុប្បន្នភាពមាតិកាដោយគ្មានដែនកំណត់',
      standardFeatureSync: 'ធ្វើសមកាលកម្មអេក្រង់យ៉ាងល្អឥតខ្ចោះ',
      standardFeatureCloud: 'គ្រប់គ្រងតាមក្លោដ',
      standardFeatureSupport: 'ជំនួយបច្ចេកទេស 24/7',
      standardFeatureNoFees: 'គ្មានថ្លៃដំឡើង',
      startFreeTrial: 'ចាប់ផ្តើមសាកល្បងឥតគិតថ្លៃ',
      enterpriseBadge: 'សហគ្រាស',
      customPrice: 'តម្លៃតាមតម្រូវការ',
      enterpriseFeatureWhiteLabel: 'កម្មវិធីស្លាកសញ្ញាផ្ទាល់ខ្លួនពេញលេញ',
      enterpriseFeatureBranding: 'ម៉ាកយីហោផ្ទាល់ខ្លួនរបស់អ្នក',
      enterpriseFeatureSource: 'អាចចូលប្រើកូដប្រភពពេញលេញ',
      enterpriseFeatureHosting: 'ជម្រើសបង្ហោះដោយខ្លួនឯង ឬតាមក្លោដ',
      enterpriseFeatureSupport: 'ក្រុមជំនួយផ្តាច់មុខ',
      enterpriseFeatureDevelopment: 'អភិវឌ្ឍមុខងារតាមតម្រូវការ',
      contactUs: 'ទាក់ទងមកយើង',
      enterpriseNote: 'ស័ក្តិសមសម្រាប់អាជីវកម្មដែលចង់បានដំណោះស្រាយក្រោមម៉ាកយីហោផ្ទាល់ខ្លួន។',
      featuresTitle: 'ហេតុអ្វីជ្រើសរើស EverydayAdvertise?',
      feature1Title: 'ជញ្ជាំងវីដេអូ',
      feature1Description: 'បច្ចេកវិទ្យាធ្វើសមកាលកម្មឈានមុខក្នុងវិស័យ ជួយឱ្យអេក្រង់ទាំងអស់របស់អ្នកដំណើរការស៊ីគ្នាយ៉ាងល្អឥតខ្ចោះ។ បង្កើតជញ្ជាំងវីដេអូដ៏ទាក់ទាញដែលធ្វើឱ្យអតិថិជនចាប់អារម្មណ៍។',
      feature2Title: 'ការគ្រប់គ្រងងាយស្រួល',
      feature2Description: 'ផ្ទាំងគ្រប់គ្រងដ៏មានអានុភាព អនុញ្ញាតឱ្យអ្នកគ្រប់គ្រងអេក្រង់ទាំងអស់ពីគ្រប់ទីកន្លែង។ បង្ហោះមាតិកា កំណត់ពេលបញ្ជីចាក់ និងតាមដានស្ថានភាពភ្លាមៗ។',
      feature3Title: 'លឿនដូចផ្លេកបន្ទោរ',
      feature3Description: 'បង្កើនប្រសិទ្ធភាពសម្រាប់ល្បឿន។ មាតិកាផ្ទុកភ្លាមៗ និងការផ្លាស់ប្តូររលូន។ គ្មានការយឺតយ៉ាវ និងគ្មានការរង់ចាំផ្ទុក។',
      feature4Title: 'ធ្វើបច្ចុប្បន្នភាពស្វ័យប្រវត្តិ',
      feature4Description: 'កែប្រែម៉ឺនុយរបស់អ្នកម្តង ហើយធ្វើបច្ចុប្បន្នភាពគ្រប់ទីកន្លែង។ អេក្រង់ទាំងអស់នឹងផ្ទុកឡើងវិញដោយស្វ័យប្រវត្តិពេលអ្នកធ្វើការកែប្រែ។',
      feature5Title: 'គាំទ្រហាងច្រើន',
      feature5Description: 'គ្រប់គ្រងទីតាំងជាច្រើនពីផ្ទាំងគ្រប់គ្រងតែមួយ។ ម៉ឺនុយខុសៗគ្នាសម្រាប់ហាងនីមួយៗ គ្រប់យ៉ាងនៅកន្លែងតែមួយ។',
      feature6Title: 'រឹងមាំ និងទុកចិត្តបាន',
      feature6Description: 'ភាពជឿជាក់កម្រិតសហគ្រាស។ ម៉ឺនុយរបស់អ្នកដំណើរការ 24/7 ជាមួយការប្ដូរប្រព័ន្ធស្វ័យប្រវត្តិ និងការគាំទ្រក្រៅបណ្តាញ។',
      trustedBrandsTitle: '🌟 ទទួលបានការជឿទុកចិត្តពីម៉ាកទូរទស្សន៍ឈានមុខជុំវិញពិភពលោក',
      platformsTitle: 'ដំណើរការលើគ្រប់វេទិកា',
      platformsSubtitle: 'ចាប់ពី Raspberry Pi ដែលមានតម្លៃសមរម្យ ដល់ប្រអប់ Android TV កម្រិតខ្ពស់។ មាតិការបស់អ្នក ជម្រើសរបស់អ្នក។',
      raspberryPiDescription: 'ជម្រើសតម្លៃសមរម្យបំផុត។ មុខងារពេញលេញក្នុងតម្លៃក្រោម $100',
      androidTvDescription: 'ដំណើរការកម្រិតខ្ពស់ជាមួយប្រអប់ Android TV',
      fireTvDescription: 'រៀបចំបានងាយស្រួលជាមួយឧបករណ៍ Amazon Fire',
      webBrowserTitle: 'កម្មវិធីរុករកវេប',
      webBrowserDescription: 'ដំណើរការជាមួយ Chrome, Safari, Edge និង Firefox',
      androidAppTitle: 'កម្មវិធី Android',
      androidAppDescription: 'កម្មវិធីដើមសម្រាប់ថេប្លេត និងទូរសព្ទ Android',
      smartTvTitle: 'ទូរទស្សន៍ឆ្លាតវៃ',
      smartTvDescription: 'គាំទ្រដោយផ្ទាល់សម្រាប់ទូរទស្សន៍ឆ្លាតវៃទំនើប',
      ctaTitle: 'ត្រៀមខ្លួនផ្លាស់ប្តូរម៉ឺនុយរបស់អ្នកហើយឬនៅ?',
      ctaSubtitle: 'ចូលរួមជាមួយភោជនីយដ្ឋានរាប់រយដែលកំពុងប្រើប្រព័ន្ធម៉ឺនុយឌីជីថលទំនើបបំផុតរបស់ពិភពលោក',
      footerDashboard: 'ផ្ទាំងគ្រប់គ្រង',
      footerSystemStatus: 'ស្ថានភាពប្រព័ន្ធ',
      footerTerms: 'លក្ខខណ្ឌសេវាកម្ម',
      footerPrivacy: 'គោលការណ៍ឯកជនភាព',
      footerCopyright: '© 2025 EverydayAdvertise. បង្កើតឡើងដោយ ❤️ សម្រាប់ភោជនីយដ្ឋានទូទាំងពិភពលោក។',
      footerBuild: 'កំណែ',
      cookieMessage: 'យើងប្រើខូគីសម្រាប់តែមុខងារចាំបាច់ ដូចជាការចូល និងសុវត្ថិភាពសម័យប្រើប្រាស់។ តាមរយៈការប្រើវេបសាយនេះ អ្នកយល់ព្រមទទួលយកខូគី។',
      cookieLearnMore: 'ស្វែងយល់បន្ថែម',
      cookieAccept: 'យល់ព្រម'
    }
  };

  var additionalLocales = window.EA_HOME_I18N_LOCALES || {};
  Object.keys(additionalLocales).forEach(function (language) {
    translations[language] = additionalLocales[language];
  });

  var supportedLanguages = ['en', 'km', 'zh', 'th', 'hi', 'ko', 'ja'];

  var bindingDefinitions = [
    { selector: '[data-i18n]', keyAttribute: 'data-i18n', property: 'textContent' },
    { selector: '[data-i18n-content]', keyAttribute: 'data-i18n-content', attribute: 'content' },
    { selector: '[data-i18n-alt]', keyAttribute: 'data-i18n-alt', attribute: 'alt' },
    { selector: '[data-i18n-aria-label]', keyAttribute: 'data-i18n-aria-label', attribute: 'aria-label' }
  ];
  var bindings = [];

  function collectBindings() {
    bindingDefinitions.forEach(function (definition) {
      document.querySelectorAll(definition.selector).forEach(function (element) {
        var original = definition.attribute
          ? element.getAttribute(definition.attribute)
          : element[definition.property];
        bindings.push({
          element: element,
          key: element.getAttribute(definition.keyAttribute),
          attribute: definition.attribute,
          property: definition.property,
          original: original
        });
      });
    });
  }

  function normaliseLanguage(value) {
    var language = String(value || '').toLowerCase().split('-')[0];
    return supportedLanguages.indexOf(language) !== -1 ? language : 'en';
  }

  function requestedLanguage() {
    try {
      var queryLanguage = new URLSearchParams(window.location.search).get('lang');
      if (supportedLanguages.indexOf(queryLanguage) !== -1) {
        return queryLanguage;
      }
    } catch (error) {}

    try {
      var storedLanguage = window.localStorage.getItem(STORAGE_KEY);
      if (supportedLanguages.indexOf(storedLanguage) !== -1) {
        return storedLanguage;
      }
    } catch (error) {}

    return normaliseLanguage(window.navigator.language);
  }

  function writeBinding(binding, value) {
    if (binding.attribute) {
      binding.element.setAttribute(binding.attribute, value);
    } else {
      binding.element[binding.property] = value;
    }
  }

  function applyLanguage(language, persist, updateUrl) {
    var selectedLanguage = normaliseLanguage(language);
    var dictionary = translations[selectedLanguage] || {};

    document.documentElement.lang = selectedLanguage;
    bindings.forEach(function (binding) {
      var translatedValue = dictionary[binding.key];
      writeBinding(binding, translatedValue === undefined ? binding.original : translatedValue);
    });

    var selector = document.getElementById('siteLanguage');
    if (selector) {
      selector.value = selectedLanguage;
    }

    if (persist) {
      try {
        window.localStorage.setItem(STORAGE_KEY, selectedLanguage);
      } catch (error) {}
    }

    if (updateUrl) {
      try {
        var url = new URL(window.location.href);
        url.searchParams.set('lang', selectedLanguage);
        window.history.replaceState({}, '', url.pathname + url.search + url.hash);
      } catch (error) {}
    }

    document.documentElement.setAttribute('data-language-ready', 'true');
    document.dispatchEvent(new CustomEvent('everydayadvertise:languagechange', {
      detail: { language: selectedLanguage }
    }));
  }

  function initialise() {
    collectBindings();
    var selector = document.getElementById('siteLanguage');
    applyLanguage(requestedLanguage(), false, false);

    if (selector) {
      selector.addEventListener('change', function () {
        applyLanguage(selector.value, true, true);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialise, { once: true });
  } else {
    initialise();
  }
})();
