/* Sign-up form: posts {email, interests, source} to the Dozer Worker and shows the answer in place.
   Everything shown is fixed text set with textContent; the address is never put back into the page. */
(function () {
  'use strict';
  var form = document.getElementById('signup-form');
  if (!form) return;
  var err = document.getElementById('signup-error');
  var result = document.getElementById('signup-result');
  var rTitle = document.getElementById('signup-result-title');
  var rText = document.getElementById('signup-result-text');
  var btn = document.getElementById('signup-submit');
  var ENDPOINT = 'https://telemetry.dozersandbox.com/v1/signup';

  function showError(text) { err.textContent = text; err.hidden = false; }
  function clearError() { err.textContent = ''; err.hidden = true; }
  function done(title, text) {
    rTitle.textContent = title; rText.textContent = text;
    form.hidden = true; result.hidden = false; result.focus();
  }
  function busy(on) { btn.disabled = on; btn.textContent = on ? 'Signing up…' : 'Sign up'; }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    clearError();
    var email = form.elements.email.value.trim();
    var interests = Array.prototype.slice.call(form.querySelectorAll('input[name=interests]:checked')).map(function (c) { return c.value; });
    if (!email || !form.elements.email.checkValidity()) { showError('Please enter a valid email address.'); form.elements.email.focus(); return; }
    if (!interests.length) { showError('Please choose at least one thing you would like to hear about.'); return; }
    busy(true);
    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, interests: interests, source: 'website' })
    }).then(function (res) {
      if (res.status === 429) { busy(false); showError('Too many tries — please try again later.'); return; }
      if (res.status === 400) {
        return res.json().catch(function () { return {}; }).then(function (j) {
          busy(false);
          var m = j && (typeof j.error === 'string' ? j.error : (typeof j.message === 'string' ? j.message : ''));
          showError(m && m.length < 160 ? m : 'That does not look right — please check the email address and try again.');
        });
      }
      if (!res.ok) { busy(false); showError('Something went wrong on our side. Please try again in a little while.'); return; }
      return res.json().then(function (j) {
        busy(false);
        if (j && j.status === 'already-confirmed') done('You’re already signed up', 'Nothing more to do. Every email we send has a one-click unsubscribe link.');
        else done('Check your inbox', 'We’ve sent a link to confirm. Nothing else is sent until you click it.');
      });
    }).catch(function () {
      busy(false);
      showError('We couldn’t reach the server. Check your connection and try again — or run doz signup in Terminal.');
    });
  });
})();
