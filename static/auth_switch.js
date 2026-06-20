(() => {
  const loginPane = document.getElementById('loginPane');
  const signupPane = document.getElementById('signupPane');
  if (!loginPane || !signupPane) return;

  const loginLink = document.getElementById('authGoLogin');
  const signupLink = document.getElementById('authGoSignup');

  function show(el) {
    el.classList.add('auth-pane--active');
    el.style.display = 'block';
  }

  function hide(el) {
    el.classList.remove('auth-pane--active');
    // keep in DOM but hidden via opacity/transform; display:none after transition
    setTimeout(() => {
      el.style.display = 'none';
    }, 190);
  }

  // default view: signup visible, login hidden
  signupPane.style.display = 'block';
  loginPane.style.display = 'none';
  signupPane.classList.add('auth-pane--active');
  loginPane.classList.remove('auth-pane--active');

  // If href points to a real page, allow normal navigation.
  loginLink?.addEventListener('click', (e) => {
    const href = loginLink.getAttribute('href');
    if (href && href !== '#' && !href.startsWith('#')) return; 
    e.preventDefault();
    hide(signupPane);
    show(loginPane);
  });

  signupLink?.addEventListener('click', (e) => {
    const href = signupLink.getAttribute('href');
    if (href && href !== '#' && !href.startsWith('#')) return;
    e.preventDefault();
    hide(loginPane);
    show(signupPane);
  });

})();

