#!/usr/bin/env python3
"""
JavaScript Generator Module - Handles all JS generation for the website builder.

This module extracts JavaScript generation logic from build_website.py for better maintainability.
Includes:
- Theme toggle with localStorage persistence
- Scroll-triggered animations with IntersectionObserver
- Lazy loading for story cards
- Navbar scroll effects
- Reduced motion preference detection
- Web Vitals tracking
"""

import json
from typing import List, Dict


def minify_js(js: str) -> str:
    """
    Basic JS minification - removes comments and extra whitespace.
    For production, consider using a proper minifier like terser.

    Args:
        js: Raw JavaScript string

    Returns:
        Minified JavaScript string
    """
    import re

    # Remove single-line comments (but not URLs)
    js = re.sub(r'(?<!:)//.*$', '', js, flags=re.MULTILINE)

    # Remove multi-line comments
    js = re.sub(r'/\*[\s\S]*?\*/', '', js)

    # Collapse multiple whitespace/newlines
    js = re.sub(r'\s+', ' ', js)

    # Remove whitespace around operators (careful with regex)
    js = re.sub(r'\s*([{};,=()[\]:])\s*', r'\1', js)

    return js.strip()


def get_theme_toggle_js() -> str:
    """Generate theme toggle functionality with localStorage persistence."""
    return """
(function() {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;
    const savedTheme = localStorage.getItem('theme');

    if (savedTheme === 'light') {
        body.classList.remove('dark-mode');
        body.classList.add('light-mode');
    } else {
        body.classList.remove('light-mode');
        body.classList.add('dark-mode');
    }

    themeToggle.addEventListener('click', function() {
        if (body.classList.contains('light-mode')) {
            body.classList.remove('light-mode');
            body.classList.add('dark-mode');
            localStorage.setItem('theme', 'dark');
        } else {
            body.classList.remove('dark-mode');
            body.classList.add('light-mode');
            localStorage.setItem('theme', 'light');
        }
    });
})();
"""


def get_navbar_scroll_js() -> str:
    """Generate navbar scroll effect."""
    return """
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
    if (window.scrollY > 100) {
        nav.classList.add('scrolled');
    } else {
        nav.classList.remove('scrolled');
    }
});
"""


def get_scroll_animations_js() -> str:
    """Generate scroll-triggered animations with IntersectionObserver."""
    return """
const animationTypes = ['animate-fade-up', 'animate-fade-left', 'animate-fade-right', 'animate-scale-in', 'animate-slide-up'];
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
        if (entry.isIntersecting) {
            const el = entry.target;

            if (prefersReducedMotion) {
                el.style.opacity = '1';
            } else {
                const parent = el.parentElement;
                const siblings = parent ? Array.from(parent.children) : [];
                const index = siblings.indexOf(el);

                const staggerClass = `stagger-${Math.min(index + 1, 8)}`;
                el.classList.add(staggerClass);

                let animationType = 'animate-fade-up';
                if (el.classList.contains('story-card')) {
                    if (index === 0) {
                        animationType = 'animate-scale-in';
                    } else if (index % 3 === 1) {
                        animationType = 'animate-fade-left';
                    } else if (index % 3 === 2) {
                        animationType = 'animate-fade-right';
                    } else {
                        animationType = 'animate-slide-up';
                    }
                } else if (el.classList.contains('compact-card')) {
                    animationType = index % 2 === 0 ? 'animate-fade-left' : 'animate-fade-right';
                } else if (el.classList.contains('stat')) {
                    animationType = 'animate-scale-in';
                } else if (el.classList.contains('section')) {
                    animationType = 'animate-slide-up';
                }

                el.classList.add(animationType);
            }

            observer.unobserve(el);
        }
    });
}, {
    threshold: 0.1,
    rootMargin: '50px'
});

document.querySelectorAll('.story-card, .compact-card, .stat, .section, .enriched-card, .word-cloud').forEach(el => {
    if (!prefersReducedMotion) {
        el.style.opacity = '0';
        // Fallback: ensure elements become visible after 1 second if animation doesn't trigger
        setTimeout(() => {
            if (el.style.opacity === '0') {
                el.style.opacity = '1';
                el.style.transition = 'opacity 0.3s ease-out';
            }
        }, 1000);
    }
    observer.observe(el);
});
"""


def get_lazy_loading_js() -> str:
    """Generate lazy loading for story cards using IntersectionObserver."""
    return """
// Lazy loading for story cards
const lazyObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
        if (entry.isIntersecting) {
            const card = entry.target;

            // Load image if present
            const img = card.querySelector('img[data-src]');
            if (img) {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                img.addEventListener('load', () => {
                    img.classList.add('lazy-loaded');
                });
            }

            // Mark card as loaded
            card.classList.remove('lazy-placeholder');
            card.classList.add('lazy-loaded');

            lazyObserver.unobserve(card);
        }
    });
}, {
    threshold: 0,
    rootMargin: '200px'  // Start loading 200px before entering viewport
});

// Observe all lazy-loadable cards
document.querySelectorAll('.story-card[data-lazy], .compact-card[data-lazy]').forEach(card => {
    lazyObserver.observe(card);
});
"""


def get_ticker_js() -> str:
    """Generate ticker pause on hover functionality."""
    return """
const ticker = document.querySelector('.ticker');
if (ticker) {
    ticker.addEventListener('mouseenter', () => {
        ticker.style.animationPlayState = 'paused';
    });
    ticker.addEventListener('mouseleave', () => {
        ticker.style.animationPlayState = 'running';
    });
}
"""


def get_web_vitals_js() -> str:
    """Generate Web Vitals tracking for Core Web Vitals monitoring."""
    return """
// Web Vitals tracking
if ('PerformanceObserver' in window) {
    // Largest Contentful Paint (LCP)
    try {
        const lcpObserver = new PerformanceObserver((entryList) => {
            const entries = entryList.getEntries();
            const lastEntry = entries[entries.length - 1];
            console.log('[Web Vitals] LCP:', Math.round(lastEntry.startTime), 'ms');
            if (window.gtag) {
                gtag('event', 'web_vitals', {
                    event_category: 'Web Vitals',
                    event_label: 'LCP',
                    value: Math.round(lastEntry.startTime),
                    non_interaction: true
                });
            }
        });
        lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {}

    // First Input Delay (FID)
    try {
        const fidObserver = new PerformanceObserver((entryList) => {
            const entries = entryList.getEntries();
            entries.forEach(entry => {
                console.log('[Web Vitals] FID:', Math.round(entry.processingStart - entry.startTime), 'ms');
                if (window.gtag) {
                    gtag('event', 'web_vitals', {
                        event_category: 'Web Vitals',
                        event_label: 'FID',
                        value: Math.round(entry.processingStart - entry.startTime),
                        non_interaction: true
                    });
                }
            });
        });
        fidObserver.observe({ type: 'first-input', buffered: true });
    } catch (e) {}

    // Cumulative Layout Shift (CLS)
    try {
        let clsValue = 0;
        const clsObserver = new PerformanceObserver((entryList) => {
            const entries = entryList.getEntries();
            entries.forEach(entry => {
                if (!entry.hadRecentInput) {
                    clsValue += entry.value;
                }
            });
        });
        clsObserver.observe({ type: 'layout-shift', buffered: true });

        // Report CLS on page hide
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                console.log('[Web Vitals] CLS:', clsValue.toFixed(3));
                if (window.gtag) {
                    gtag('event', 'web_vitals', {
                        event_category: 'Web Vitals',
                        event_label: 'CLS',
                        value: Math.round(clsValue * 1000),
                        non_interaction: true
                    });
                }
            }
        });
    } catch (e) {}
}
"""


def get_service_worker_registration_js() -> str:
    """Generate service worker registration for PWA support."""
    return """
// Register service worker for PWA support
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('[PWA] Service Worker registered:', registration.scope);
            })
            .catch(error => {
                console.log('[PWA] Service Worker registration failed:', error);
            });
    });
}
"""


def generate_complete_js(enable_lazy_loading: bool = True,
                         enable_web_vitals: bool = True,
                         enable_pwa: bool = True,
                         minify: bool = False) -> str:
    """
    Generate the complete JavaScript for the website.

    Args:
        enable_lazy_loading: Include lazy loading code
        enable_web_vitals: Include Web Vitals tracking
        enable_pwa: Include PWA service worker registration
        minify: Whether to minify the output

    Returns:
        Complete JavaScript string wrapped in script tag
    """
    js_parts = [
        get_theme_toggle_js(),
        get_navbar_scroll_js(),
        get_scroll_animations_js(),
    ]

    if enable_lazy_loading:
        js_parts.append(get_lazy_loading_js())

    js_parts.append(get_ticker_js())

    if enable_web_vitals:
        js_parts.append(get_web_vitals_js())

    if enable_pwa:
        js_parts.append(get_service_worker_registration_js())

    complete_js = '\n'.join(js_parts)

    if minify:
        complete_js = minify_js(complete_js)

    return f"<script>\n{complete_js}\n</script>"
