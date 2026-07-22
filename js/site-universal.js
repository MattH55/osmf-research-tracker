/* ═══════════════════════════════════════════════════════════════ */
/* Open Source Medicine Foundation — Universal Site JS  v3.0 */
/* Scroll reveals, mobile nav, back-to-top, scroll-aware nav */
/* ═══════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function () {

  /* ── Mobile nav toggle ── */
  var navToggle = document.querySelector('.nav-toggle');
  var navLinks = document.querySelector('.nav-links');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', function () {
      navToggle.classList.toggle('open');
      navLinks.classList.toggle('open');
      document.body.style.overflow = navLinks.classList.contains('open') ? 'hidden' : '';
    });
    // Close on link click (for SPA-style navigation)
    navLinks.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        navToggle.classList.remove('open');
        navLinks.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  /* ── Scroll-aware nav (compact on scroll) ── */
  var nav = document.querySelector('nav');
  var lastScroll = 0;
  window.addEventListener('scroll', function () {
    var scrollY = window.pageYOffset || document.documentElement.scrollTop;
    if (scrollY > 80) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
    lastScroll = scrollY;
  }, { passive: true });

  /* ── Back to top button ── */
  var backBtn = document.querySelector('.back-to-top');
  if (backBtn) {
    window.addEventListener('scroll', function () {
      if (window.pageYOffset > 600) {
        backBtn.classList.add('visible');
      } else {
        backBtn.classList.remove('visible');
      }
    }, { passive: true });
    backBtn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  /* ── Scroll reveal (Intersection Observer) ── */
  if ('IntersectionObserver' in window) {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('revealed');
          if (entry.target.dataset.revealOnce !== 'false') {
            revealObserver.unobserve(entry.target);
          }
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });

    // Stagger card reveals
    document.querySelectorAll('.tracker-hub-card').forEach(function (card, i) {
      card.style.transitionDelay = (i * 0.06) + 's';
      revealObserver.observe(card);
    });

    // Generic reveal-on-scroll elements
    document.querySelectorAll('.reveal-on-scroll').forEach(function (el) {
      revealObserver.observe(el);
    });

    // Study / trial / agent cards
    document.querySelectorAll('.study-card, .trial-card, .agent-card').forEach(function (card, i) {
      card.classList.add('reveal-on-scroll');
      card.style.transitionDelay = (i * 0.04) + 's';
      revealObserver.observe(card);
    });
  } else {
    // Fallback: show everything immediately
    document.querySelectorAll('.tracker-hub-card, .reveal-on-scroll').forEach(function (el) {
      el.classList.add('revealed');
    });
  }

  /* ── Ripple effect on buttons ── */
  document.querySelectorAll('.btn-donate, .btn-ghost').forEach(function (btn) {
    btn.classList.add('ripple');
  });

});