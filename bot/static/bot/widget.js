/**
 * ONMA scout Chat Widget — vanilla JS, no dependencies.
 * Namespaced DOM (.onma-chat-*) and a single global (ONMAChat) so it can be
 * dropped into any page without colliding with existing site scripts.
 *
 * Bilingual (DE/EN): the visitor picks a language with the DE/EN toggle in
 * the header. This is a manual switch, not automatic language detection
 * (that's a V2 feature) — every string in the widget and the `language`
 * sent to the backend follow whatever the visitor last picked.
 *
 * This copy talks to the Django V2 backend (POST {apiBase}/api/session/ and
 * {apiBase}/api/chat/). apiBase defaults to '' (same origin as the page);
 * set it to e.g. 'http://localhost:8000' when embedding on a page served
 * from somewhere else, and make sure that origin is allowed in the
 * Django app's CORS_ALLOWED_ORIGINS.
 *
 * Usage:
 *   <link rel="stylesheet" href="{% static 'bot/widget.css' %}">
 *   <script src="{% static 'bot/widget.js' %}"></script>
 *   <script>
 *     ONMAChat.init({
 *       hasConsent: function () { return document.cookie.includes('cookie_consent=accepted'); },
 *       onConsentGiven: function (cb) { document.addEventListener('onma:consentAccepted', cb); }
 *     });
 *   </script>
 */
(function (window, document) {
  'use strict';

  // Resolve the bundled logo relative to wherever this script itself was
  // loaded from, so it keeps working no matter which page embeds the widget.
  var CURRENT_SCRIPT_SRC = document.currentScript ? document.currentScript.src : '';
  var DEFAULT_LOGO_URL = CURRENT_SCRIPT_SRC
    ? CURRENT_SCRIPT_SRC.replace(/widget\.js(\?.*)?$/, 'onma.png')
    : 'onma.png';

  var STRINGS = {
    de: {
      title: 'ONMA scout Assistent',
      subtitle: 'Wir antworten in der Regel sofort',
      greeting: 'Hallo! Ich bin der virtuelle Assistent von ONMA scout. Wie kann ich Ihnen bei SEO, SEA, Webdesign oder App-Entwicklung helfen?',
      placeholder: 'Ihre Nachricht…',
      launcherLabel: 'Chat öffnen',
      closeLabel: 'Chat schließen',
      sendLabel: 'Senden',
      inputLabel: 'Nachricht eingeben',
      footerNote: 'Antworten werden automatisch generiert und können Fehler enthalten.',
      consentTitle: 'Bitte Cookies akzeptieren',
      consentBody: 'Der Chat startet, sobald Sie der Cookie-Nutzung auf dieser Seite zugestimmt haben.',
      errorBubble: 'Entschuldigung, da ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.',
      retryLabel: 'Erneut senden',
      fallbackReply: 'Entschuldigung, ich habe darauf keine Antwort.',
      youLabel: 'Sie',
      langButtonLabelDe: 'Auf Deutsch anzeigen',
      langButtonLabelEn: 'Auf Englisch anzeigen',
      leadTitle: 'Möchten Sie, dass wir uns bei Ihnen melden?',
      leadBody: 'Hinterlassen Sie uns Ihre Kontaktdaten, und wir melden uns persönlich bei Ihnen.',
      leadNamePlaceholder: 'Ihr Name',
      leadEmailPlaceholder: 'E-Mail-Adresse',
      leadPhonePlaceholder: 'Telefonnummer (optional)',
      leadConsentLabel: 'Ich stimme zu, dass ONMA scout mich zu meiner Anfrage kontaktiert.',
      leadSubmitLabel: 'Absenden',
      leadDismissLabel: 'Nein, danke',
      leadConsentRequired: 'Bitte stimmen Sie der Kontaktaufnahme zu.',
      leadContactRequired: 'Bitte geben Sie E-Mail oder Telefonnummer an.',
      leadThankYou: 'Vielen Dank! Wir melden uns in Kürze bei Ihnen.',
      leadError: 'Da ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.'
    },
    en: {
      title: 'ONMA scout Assistant',
      subtitle: 'We usually reply right away',
      greeting: "Hi! I'm ONMA scout's virtual assistant. How can I help you with SEO, SEA, web design or app development?",
      placeholder: 'Your message…',
      launcherLabel: 'Open chat',
      closeLabel: 'Close chat',
      sendLabel: 'Send',
      inputLabel: 'Enter message',
      footerNote: 'Answers are generated automatically and may contain errors.',
      consentTitle: 'Please accept cookies',
      consentBody: 'The chat will start as soon as you accept cookie usage on this site.',
      errorBubble: 'Sorry, something went wrong. Please try again.',
      retryLabel: 'Retry',
      fallbackReply: "Sorry, I don't have an answer for that.",
      youLabel: 'You',
      langButtonLabelDe: 'Show in German',
      langButtonLabelEn: 'Show in English',
      leadTitle: 'Would you like us to reach out to you?',
      leadBody: 'Leave your contact details and we\'ll get back to you personally.',
      leadNamePlaceholder: 'Your name',
      leadEmailPlaceholder: 'Email address',
      leadPhonePlaceholder: 'Phone number (optional)',
      leadConsentLabel: 'I agree that ONMA scout may contact me about my inquiry.',
      leadSubmitLabel: 'Submit',
      leadDismissLabel: 'No, thanks',
      leadConsentRequired: 'Please agree to being contacted.',
      leadContactRequired: 'Please provide an email or phone number.',
      leadThankYou: 'Thank you! We\'ll be in touch shortly.',
      leadError: 'Something went wrong. Please try again.'
    }
  };

  var DEFAULTS = {
    apiBase: '',
    maxLength: 1000,
    storageKey: 'onma_chat_session_token',
    langStorageKey: 'onma_chat_lang',
    defaultLanguage: null, // null = auto-detect from navigator.language, falls back to 'de'
    logoUrl: DEFAULT_LOGO_URL,
    // Cloudflare Turnstile site key (public, safe to expose client-side).
    // Leave blank to skip Turnstile entirely — matches the server defaulting
    // to disabled when it has no keys configured either.
    turnstileSiteKey: '',
    // By default, look for a common consent cookie/localStorage flag.
    // Host site should override this via ONMAChat.init({ hasConsent: fn }).
    hasConsent: function () {
      try {
        if (localStorage.getItem('cookie_consent') === 'accepted') return true;
      } catch (e) {}
      return /cookie_?consent=accepted/i.test(document.cookie);
    },
    onConsentGiven: function (callback) {
      document.addEventListener('onma:consentAccepted', callback);
      window.addEventListener('storage', function (e) {
        if (e.key === 'cookie_consent' && e.newValue === 'accepted') callback();
      });
    }
  };

  var ICONS = {
    chat: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 4h16v12H7l-3 3V4z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 12l16-8-6 8 6 8-16-8z" fill="currentColor"/></svg>'
  };

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function detectDefaultLanguage() {
    try {
      var nav = (navigator.language || navigator.userLanguage || 'de').toLowerCase();
      return nav.indexOf('en') === 0 ? 'en' : 'de';
    } catch (e) {
      return 'de';
    }
  }

  function ONMAChatWidget(config) {
    this.config = Object.assign({}, DEFAULTS, config || {});
    this.sessionToken = null;
    this.isOpen = false;
    this.isSending = false;
    this.consentReady = false;
    this.pendingFirstOpen = false;
    this.history = [];
    this.lang = this._loadInitialLanguage();
    this._remoteBotName = null;
    this._remoteBotIcon = null;
    this._build();
    this._bind();
    this._checkConsent();
    this._loadRemoteConfig();
  }

  // Fetches admin-configured branding (BotSettings.bot_name/bot_icon, set
  // via /admin/) and applies it once loaded — a brief moment of the
  // built-in defaults before this resolves is expected and harmless (this
  // is a branding nicety, not something that should block first render).
  ONMAChatWidget.prototype._loadRemoteConfig = function () {
    var self = this;
    fetch(this.config.apiBase + '/api/config/')
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (data.bot_name) self._remoteBotName = data.bot_name;
        if (data.bot_icon_url) self._remoteBotIcon = data.bot_icon_url;
        if (!data.bot_name && !data.bot_icon_url) return;

        self._applyStrings();
        if (data.bot_icon_url) {
          self.el.root.querySelectorAll('[data-onma-bot-avatar]').forEach(function (img) {
            img.src = data.bot_icon_url;
          });
        }
      })
      .catch(function () { /* keep the built-in defaults */ });
  };

  ONMAChatWidget.prototype._loadInitialLanguage = function () {
    try {
      var stored = localStorage.getItem(this.config.langStorageKey);
      if (stored === 'de' || stored === 'en') return stored;
    } catch (e) {}
    return this.config.defaultLanguage === 'de' || this.config.defaultLanguage === 'en'
      ? this.config.defaultLanguage
      : detectDefaultLanguage();
  };

  ONMAChatWidget.prototype._t = function (key) {
    return STRINGS[this.lang][key];
  };

  ONMAChatWidget.prototype._checkConsent = function () {
    var self = this;
    if (this.config.hasConsent()) {
      this.consentReady = true;
      return;
    }
    this.config.onConsentGiven(function () {
      self.consentReady = true;
      self._hideConsentNotice();
      if (self.pendingFirstOpen) {
        self.pendingFirstOpen = false;
        self._ensureSession();
      }
    });
  };

  ONMAChatWidget.prototype._build = function () {
    var root = document.createElement('div');
    root.className = 'onma-chat-root';
    root.innerHTML =
      '<button type="button" class="onma-chat-launcher" aria-haspopup="dialog" aria-expanded="false">' +
        ICONS.chat +
      '</button>' +
      '<section class="onma-chat-panel" role="dialog" aria-modal="false">' +
        '<header class="onma-chat-header">' +
          '<div class="onma-chat-header-info">' +
            '<span class="onma-chat-header-title"></span>' +
            '<span class="onma-chat-header-status"><span class="onma-chat-status-dot"></span><span class="onma-chat-header-status-text"></span></span>' +
          '</div>' +
          '<div class="onma-chat-header-actions">' +
            '<div class="onma-chat-lang-switch" role="group">' +
              '<button type="button" class="onma-chat-lang-btn" data-lang="de">DE</button>' +
              '<button type="button" class="onma-chat-lang-btn" data-lang="en">EN</button>' +
            '</div>' +
            '<button type="button" class="onma-chat-close">' + ICONS.close + '</button>' +
          '</div>' +
        '</header>' +
        '<div class="onma-chat-messages" aria-live="polite"></div>' +
        '<div class="onma-chat-inputbar">' +
          '<textarea class="onma-chat-textarea" rows="1" maxlength="' + this.config.maxLength + '"></textarea>' +
          '<button type="button" class="onma-chat-send" disabled>' + ICONS.send + '</button>' +
        '</div>' +
        '<div class="onma-chat-footer-note"></div>' +
      '</section>';

    document.body.appendChild(root);

    this.el = {
      root: root,
      launcher: root.querySelector('.onma-chat-launcher'),
      panel: root.querySelector('.onma-chat-panel'),
      closeBtn: root.querySelector('.onma-chat-close'),
      title: root.querySelector('.onma-chat-header-title'),
      statusText: root.querySelector('.onma-chat-header-status-text'),
      langBtns: root.querySelectorAll('.onma-chat-lang-btn'),
      messages: root.querySelector('.onma-chat-messages'),
      textarea: root.querySelector('.onma-chat-textarea'),
      sendBtn: root.querySelector('.onma-chat-send'),
      footerNote: root.querySelector('.onma-chat-footer-note')
    };

    this._applyStrings();
  };

  ONMAChatWidget.prototype._applyStrings = function () {
    var t = this._t.bind(this);

    this.el.launcher.setAttribute('aria-label', t('launcherLabel'));
    this.el.panel.setAttribute('aria-label', this._remoteBotName || t('title'));
    this.el.closeBtn.setAttribute('aria-label', t('closeLabel'));
    this.el.title.textContent = this._remoteBotName || t('title');
    this.el.statusText.textContent = t('subtitle');
    this.el.textarea.setAttribute('placeholder', t('placeholder'));
    this.el.textarea.setAttribute('aria-label', t('inputLabel'));
    this.el.sendBtn.setAttribute('aria-label', t('sendLabel'));
    this.el.footerNote.textContent = t('footerNote');
    this.el.root.setAttribute('lang', this.lang);

    this.el.langBtns.forEach(function (btn) {
      var isCurrent = btn.getAttribute('data-lang') === this.lang;
      btn.classList.toggle('onma-chat-lang-btn-active', isCurrent);
      btn.setAttribute('aria-pressed', String(isCurrent));
      btn.setAttribute('aria-label', btn.getAttribute('data-lang') === 'de' ? t('langButtonLabelDe') : t('langButtonLabelEn'));
    }, this);

    var consentTitleEl = this.el.messages.querySelector('.onma-chat-consent strong');
    if (consentTitleEl) {
      consentTitleEl.textContent = t('consentTitle');
      consentTitleEl.nextSibling && (consentTitleEl.nextSibling.textContent = t('consentBody'));
    }
  };

  ONMAChatWidget.prototype._setLanguage = function (lang) {
    if (lang !== 'de' && lang !== 'en') return;
    if (lang === this.lang) return;

    this.lang = lang;
    try { localStorage.setItem(this.config.langStorageKey, lang); } catch (e) {}
    this._applyStrings();

    // If nothing beyond the greeting has happened yet, swap the greeting
    // text too so the very first thing the visitor reads matches their pick.
    var onlyGreetingShown = this.history.length === 0 && this.el.messages.children.length === 1;
    if (onlyGreetingShown) {
      this.el.messages.innerHTML = '';
      this._renderGreetingIfEmpty();
    }
  };

  ONMAChatWidget.prototype._bind = function () {
    var self = this;

    this.el.launcher.addEventListener('click', function () { self.toggle(); });
    this.el.closeBtn.addEventListener('click', function () { self.close(); });

    this.el.langBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        self._setLanguage(btn.getAttribute('data-lang'));
      });
    });

    this.el.textarea.addEventListener('input', function () {
      self._autoGrow();
      self.el.sendBtn.disabled = self.isSending || !self.el.textarea.value.trim();
    });

    this.el.textarea.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        self._handleSend();
      }
    });

    this.el.sendBtn.addEventListener('click', function () { self._handleSend(); });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && self.isOpen) self.close();
    });
  };

  ONMAChatWidget.prototype._autoGrow = function () {
    var ta = this.el.textarea;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  };

  ONMAChatWidget.prototype.toggle = function () {
    if (this.isOpen) this.close();
    else this.open();
  };

  ONMAChatWidget.prototype.open = function () {
    this.isOpen = true;
    this.el.panel.classList.add('onma-chat-open');
    this.el.launcher.setAttribute('aria-expanded', 'true');

    if (!this.consentReady) {
      this._showConsentNotice();
      this.pendingFirstOpen = true;
      return;
    }

    this._ensureSession();
    this.el.textarea.focus();
  };

  ONMAChatWidget.prototype.close = function () {
    this.isOpen = false;
    this.el.panel.classList.remove('onma-chat-open');
    this.el.launcher.setAttribute('aria-expanded', 'false');
    this.el.launcher.focus();
  };

  ONMAChatWidget.prototype._showConsentNotice = function () {
    if (this.el.messages.querySelector('.onma-chat-consent')) return;
    var notice = document.createElement('div');
    notice.className = 'onma-chat-consent';
    var strong = document.createElement('strong');
    strong.textContent = this._t('consentTitle');
    notice.appendChild(strong);
    notice.appendChild(document.createTextNode(this._t('consentBody')));
    this.el.messages.appendChild(notice);
  };

  ONMAChatWidget.prototype._hideConsentNotice = function () {
    var notice = this.el.messages.querySelector('.onma-chat-consent');
    if (notice) notice.remove();
  };

  ONMAChatWidget.prototype._ensureSession = function () {
    var self = this;
    if (this.sessionToken) return Promise.resolve(this.sessionToken);

    try {
      var stored = localStorage.getItem(this.config.storageKey);
      if (stored) {
        this.sessionToken = stored;
        this._renderGreetingIfEmpty();
        return Promise.resolve(stored);
      }
    } catch (e) {}

    return fetch(this.config.apiBase + '/api/session/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
      .then(function (res) {
        if (!res.ok) throw new Error('session_failed');
        return res.json();
      })
      .then(function (data) {
        self.sessionToken = data.session_token;
        try { localStorage.setItem(self.config.storageKey, self.sessionToken); } catch (e) {}
        self._renderGreetingIfEmpty();
        return self.sessionToken;
      })
      .catch(function () {
        self._renderGreetingIfEmpty();
        return null;
      });
  };

  ONMAChatWidget.prototype._renderGreetingIfEmpty = function () {
    if (this.history.length === 0) {
      this._renderMessage('assistant', this._t('greeting'));
    }
  };

  ONMAChatWidget.prototype._handleSend = function () {
    var text = this.el.textarea.value.trim();
    if (!text || this.isSending) return;
    this._sendMessage(text);
  };

  ONMAChatWidget.prototype._sendMessage = function (text) {
    var self = this;

    this.el.textarea.value = '';
    this._autoGrow();
    this.el.sendBtn.disabled = true;

    this._renderMessage('user', text);
    this.history.push({ role: 'user', content: text });

    this.isSending = true;
    this.el.textarea.disabled = true;

    var supportsStreaming = !!(window.ReadableStream && window.TextDecoder);

    Promise.all([this._ensureSession(), this._getTurnstileToken()])
      .then(function (results) {
        var token = results[0];
        var turnstileToken = results[1];
        return supportsStreaming
          ? self._streamReply(token, text, turnstileToken)
          : self._fetchReplyClassic(token, text, turnstileToken);
      })
      .catch(function () {
        self._renderError(text);
      })
      .finally(function () {
        self.isSending = false;
        self.el.textarea.disabled = false;
        self.el.sendBtn.disabled = !self.el.textarea.value.trim();
        self.el.textarea.focus();
      });
  };

  // Lazily loads Cloudflare's Turnstile script and renders one invisible
  // widget instance, reused for every message (each _getTurnstileToken()
  // call re-executes it to get a fresh, single-use token). No-op — resolves
  // immediately — when turnstileSiteKey isn't configured.
  ONMAChatWidget.prototype._ensureTurnstile = function () {
    var self = this;
    if (!this.config.turnstileSiteKey) return Promise.resolve();
    if (this._turnstileReady) return this._turnstileReady;

    this._turnstileReady = new Promise(function (resolve) {
      function renderWidget() {
        var container = document.createElement('div');
        container.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;';
        document.body.appendChild(container);

        self._turnstileWidgetId = window.turnstile.render(container, {
          sitekey: self.config.turnstileSiteKey,
          size: 'invisible',
          callback: function (token) {
            if (self._turnstileResolve) {
              self._turnstileResolve(token);
              self._turnstileResolve = null;
            }
          },
          'error-callback': function () {
            if (self._turnstileResolve) {
              self._turnstileResolve('');
              self._turnstileResolve = null;
            }
          }
        });
        resolve();
      }

      if (window.turnstile) {
        renderWidget();
        return;
      }

      var script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
      script.async = true;
      script.onload = renderWidget;
      script.onerror = resolve; // Turnstile unreachable — degrade to no token, let the server decide
      document.head.appendChild(script);
    });

    return this._turnstileReady;
  };

  ONMAChatWidget.prototype._getTurnstileToken = function () {
    var self = this;
    if (!this.config.turnstileSiteKey) return Promise.resolve('');

    return this._ensureTurnstile().then(function () {
      if (!window.turnstile || self._turnstileWidgetId === undefined) return '';
      return new Promise(function (resolve) {
        self._turnstileResolve = resolve;
        window.turnstile.execute(self._turnstileWidgetId);
      });
    });
  };

  // Streams the reply via Server-Sent Events (/api/chat/stream/), appending
  // each delta to a growing bubble as it arrives. Falls back to
  // _fetchReplyClassic (one blocking JSON response) in browsers lacking
  // ReadableStream/TextDecoder — see the supportsStreaming check above.
  ONMAChatWidget.prototype._streamReply = function (token, text, turnstileToken) {
    var self = this;
    var typingEl = this._renderTyping();
    var row = null;
    var bubble = null;
    var fullText = '';
    var buffer = '';

    function handleFrame(rawFrame) {
      var line = rawFrame.trim();
      if (line.indexOf('data:') !== 0) return;

      var data;
      try {
        data = JSON.parse(line.slice(5).trim());
      } catch (e) {
        return;
      }

      if (data.delta) {
        if (!row) {
          typingEl.remove();
          row = self._renderMessage('assistant', '');
          bubble = row.querySelector('.onma-chat-bubble');
        }
        fullText += data.delta;
        bubble.textContent = fullText;
        self._scrollToBottom();
      }

      if (data.done) {
        if (!row) {
          // No delta ever arrived (shouldn't happen — every server path
          // sends at least one) — still show something rather than nothing.
          typingEl.remove();
          fullText = self._t('fallbackReply');
          row = self._renderMessage('assistant', fullText);
        }
        if (data.sources && data.sources.length) {
          self._appendSources(row, data.sources);
        }
        self.history.push({ role: 'assistant', content: fullText });
        if (data.lead_prompt) {
          self._renderLeadForm(data.lead_prompt.service_interest || '', text);
        }
      }
    }

    return fetch(this.config.apiBase + '/api/chat/stream/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: token, message: text, language: self.lang, turnstile_token: turnstileToken || ''
      })
    })
      .then(function (res) {
        if (!res.ok || !res.body) throw new Error('stream_request_failed');
        var reader = res.body.getReader();
        var decoder = new TextDecoder();

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) return;
            buffer += decoder.decode(result.value, { stream: true });

            var frames = buffer.split('\n\n');
            buffer = frames.pop();
            frames.forEach(handleFrame);

            return pump();
          });
        }

        return pump();
      })
      .catch(function (err) {
        typingEl.remove();
        throw err;
      });
  };

  // Non-streaming fallback: one POST to /api/chat/, one JSON response.
  ONMAChatWidget.prototype._fetchReplyClassic = function (token, text, turnstileToken) {
    var self = this;
    var typingEl = this._renderTyping();

    return fetch(this.config.apiBase + '/api/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: token, message: text, language: self.lang, turnstile_token: turnstileToken || ''
      })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('request_failed');
        return res.json();
      })
      .then(function (data) {
        typingEl.remove();
        var reply = data.reply || self._t('fallbackReply');
        self._renderMessage('assistant', reply, data.sources);
        self.history.push({ role: 'assistant', content: reply });
        if (data.lead_prompt) {
          self._renderLeadForm(data.lead_prompt.service_interest || '', text);
        }
      })
      .catch(function (err) {
        typingEl.remove();
        throw err;
      });
  };

  ONMAChatWidget.prototype._botAvatarHtml = function () {
    var iconUrl = this._remoteBotIcon || this.config.logoUrl;
    return '<span class="onma-chat-avatar onma-chat-avatar-bot"><img src="' +
      escapeHtml(iconUrl) + '" alt="" data-onma-bot-avatar /></span>';
  };

  ONMAChatWidget.prototype._renderMessage = function (role, content, sources) {
    var isUser = role === 'user';
    var row = document.createElement('div');
    row.className = 'onma-chat-row ' + (isUser ? 'onma-chat-row-user' : 'onma-chat-row-bot');
    row.innerHTML =
      (isUser
        ? '<span class="onma-chat-avatar">' + escapeHtml(this._t('youLabel')) + '</span>'
        : this._botAvatarHtml()) +
      '<div><div class="onma-chat-bubble"></div></div>';
    row.querySelector('.onma-chat-bubble').textContent = content;

    if (!isUser && sources && sources.length) {
      this._appendSources(row, sources);
    }

    this.el.messages.appendChild(row);
    this._scrollToBottom();
    return row;
  };

  ONMAChatWidget.prototype._appendSources = function (row, sources) {
    var sourcesEl = document.createElement('div');
    sourcesEl.className = 'onma-chat-sources';
    sourcesEl.textContent = (this.lang === 'de' ? 'Quellen: ' : 'Sources: ') +
      sources.map(function (s) { return s.title; }).join(', ');
    row.querySelector('div').appendChild(sourcesEl);
  };

  ONMAChatWidget.prototype._renderTyping = function () {
    var row = document.createElement('div');
    row.className = 'onma-chat-row onma-chat-row-bot';
    row.innerHTML =
      this._botAvatarHtml() +
      '<div class="onma-chat-bubble"><span class="onma-chat-typing"><span></span><span></span><span></span></span></div>';
    this.el.messages.appendChild(row);
    this._scrollToBottom();
    return row;
  };

  ONMAChatWidget.prototype._renderError = function (originalText) {
    var self = this;
    var row = document.createElement('div');
    row.className = 'onma-chat-row onma-chat-row-bot';
    row.innerHTML =
      this._botAvatarHtml() +
      '<div>' +
        '<div class="onma-chat-bubble onma-chat-bubble-error"></div>' +
        '<button type="button" class="onma-chat-retry"></button>' +
      '</div>';
    row.querySelector('.onma-chat-bubble-error').textContent = this._t('errorBubble');
    var retryBtn = row.querySelector('.onma-chat-retry');
    retryBtn.textContent = this._t('retryLabel');
    retryBtn.addEventListener('click', function () {
      row.remove();
      self._sendMessage(originalText);
    });
    this.el.messages.appendChild(row);
    this._scrollToBottom();
  };

  ONMAChatWidget.prototype._renderLeadForm = function (serviceInterest, triggeringMessage) {
    var self = this;
    var t = this._t.bind(this);

    var row = document.createElement('div');
    row.className = 'onma-chat-row onma-chat-row-bot';
    row.innerHTML =
      this._botAvatarHtml() +
      '<div class="onma-chat-lead-card">' +
        '<strong class="onma-chat-lead-title"></strong>' +
        '<p class="onma-chat-lead-body"></p>' +
        '<form class="onma-chat-lead-form">' +
          '<input type="text" class="onma-chat-lead-name" autocomplete="name">' +
          '<input type="email" class="onma-chat-lead-email" autocomplete="email">' +
          '<input type="tel" class="onma-chat-lead-phone" autocomplete="tel">' +
          '<label class="onma-chat-lead-consent-row">' +
            '<input type="checkbox" class="onma-chat-lead-consent">' +
            '<span class="onma-chat-lead-consent-label"></span>' +
          '</label>' +
          '<p class="onma-chat-lead-error" hidden></p>' +
          '<div class="onma-chat-lead-actions">' +
            '<button type="button" class="onma-chat-lead-dismiss"></button>' +
            '<button type="submit" class="onma-chat-lead-submit"></button>' +
          '</div>' +
        '</form>' +
      '</div>';

    row.querySelector('.onma-chat-lead-title').textContent = t('leadTitle');
    row.querySelector('.onma-chat-lead-body').textContent = t('leadBody');
    row.querySelector('.onma-chat-lead-name').setAttribute('placeholder', t('leadNamePlaceholder'));
    row.querySelector('.onma-chat-lead-email').setAttribute('placeholder', t('leadEmailPlaceholder'));
    row.querySelector('.onma-chat-lead-phone').setAttribute('placeholder', t('leadPhonePlaceholder'));
    row.querySelector('.onma-chat-lead-consent-label').textContent = t('leadConsentLabel');
    row.querySelector('.onma-chat-lead-dismiss').textContent = t('leadDismissLabel');
    row.querySelector('.onma-chat-lead-submit').textContent = t('leadSubmitLabel');

    var form = row.querySelector('.onma-chat-lead-form');
    var errorEl = row.querySelector('.onma-chat-lead-error');

    row.querySelector('.onma-chat-lead-dismiss').addEventListener('click', function () {
      row.remove();
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var name = row.querySelector('.onma-chat-lead-name').value.trim();
      var email = row.querySelector('.onma-chat-lead-email').value.trim();
      var phone = row.querySelector('.onma-chat-lead-phone').value.trim();
      var consent = row.querySelector('.onma-chat-lead-consent').checked;

      if (!consent) {
        errorEl.textContent = t('leadConsentRequired');
        errorEl.hidden = false;
        return;
      }
      if (!email && !phone) {
        errorEl.textContent = t('leadContactRequired');
        errorEl.hidden = false;
        return;
      }
      errorEl.hidden = true;

      var submitBtn = row.querySelector('.onma-chat-lead-submit');
      submitBtn.disabled = true;

      fetch(self.config.apiBase + '/api/lead/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: self.sessionToken,
          name: name,
          email: email,
          phone: phone,
          service_interest: serviceInterest,
          message: triggeringMessage,
          consent: true
        })
      })
        .then(function (res) {
          if (!res.ok) throw new Error('lead_request_failed');
          return res.json();
        })
        .then(function () {
          row.querySelector('.onma-chat-lead-card').innerHTML =
            '<p class="onma-chat-lead-thankyou">' + escapeHtml(t('leadThankYou')) + '</p>';
          self._scrollToBottom();
        })
        .catch(function () {
          errorEl.textContent = t('leadError');
          errorEl.hidden = false;
          submitBtn.disabled = false;
        });
    });

    this.el.messages.appendChild(row);
    this._scrollToBottom();
  };

  ONMAChatWidget.prototype._scrollToBottom = function () {
    this.el.messages.scrollTop = this.el.messages.scrollHeight;
  };

  window.ONMAChat = {
    _instance: null,
    init: function (config) {
      if (this._instance) return this._instance;
      this._instance = new ONMAChatWidget(config);
      return this._instance;
    }
  };
})(window, document);
