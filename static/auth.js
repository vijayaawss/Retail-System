(() => {
  function toastInline(message, inputEl) {
    if (!inputEl) return;
    const err = document.getElementById(inputEl.id + 'Err');
    if (err) {
      err.textContent = message;
      err.classList.add('show');
    }
  }

  function clearInline(inputEl) {
    const err = document.getElementById(inputEl.id + 'Err');
    if (err) {
      err.textContent = '';
      err.classList.remove('show');
    }
  }

  function isValidEmail(email) {
    return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  }

  // Signup
  const signupForm = document.getElementById('signupForm');
  if (signupForm) {
    const name = document.getElementById('name');
    const shop = document.getElementById('shop_name');
    const email = document.getElementById('email');
    const password = document.getElementById('password');

    const onBlur = (el) => {
      if (!el) return;
      clearInline(el);
    };

    [name, shop, email, password].forEach(el => el && el.addEventListener('blur', () => onBlur(el)));

    signupForm.addEventListener('submit', (e) => {
      let ok = true;

      if (!name.value.trim()) {
        ok = false;
        toastInline('Name is required.', name);
      }
      if (!shop.value.trim()) {
        ok = false;
        const err = document.getElementById('shopErr');
        if (err) { err.textContent = 'Shop name is required.'; err.classList.add('show'); }
      }
      if (!email.value.trim()) {
        ok = false;
        toastInline('Email is required.', email);
      } else if (!isValidEmail(email.value.trim())) {
        ok = false;
        toastInline('Enter a valid email address.', email);
      }
      if (!password.value.trim()) {
        ok = false;
        toastInline('Password is required.', password);
      } else if (password.value.trim().length < 4) {
        ok = false;
        toastInline('Password must be at least 4 characters.', password);
      }

      if (!ok) e.preventDefault();
    });
  }

  // Login
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    const email = document.getElementById('email');
    const password = document.getElementById('password');

    [email, password].forEach(el => el && el.addEventListener('blur', () => clearInline(el)));

    loginForm.addEventListener('submit', (e) => {
      let ok = true;

      if (!email.value.trim()) {
        ok = false;
        toastInline('Email is required.', email);
      } else if (!isValidEmail(email.value.trim())) {
        ok = false;
        toastInline('Enter a valid email address.', email);
      }

      if (!password.value.trim()) {
        ok = false;
        toastInline('Password is required.', password);
      }

      if (!ok) e.preventDefault();
    });
  }

  // Server flash messages -> inline toasts (simple)
  const flashes = document.querySelectorAll('.server-flashes [data-flash]');
  if (flashes && flashes.length) {
    // Show first flash as inline near email/password.
    const msg = flashes[0].textContent.trim();
    const type = flashes[0].getAttribute('data-flash') || 'info';
    const email = document.getElementById('email');
    const password = document.getElementById('password');

    const target = email || password;
    if (target) {
      toastInline(type === 'error' ? msg : msg, target);
    }
  }
})();

