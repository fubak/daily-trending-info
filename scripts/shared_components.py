"""
Shared HTML components for consistent header/footer across all pages.
"""
from datetime import datetime


def get_nav_links(active_page: str = '') -> str:
    """
    Generate navigation links HTML.

    Args:
        active_page: One of 'home', 'tech', 'world', 'science', 'politics',
                     'finance', 'media', 'articles' to mark as active
    """
    links = [
        ('/', 'Home', 'home'),
        ('/tech/', 'Tech', 'tech'),
        ('/world/', 'World', 'world'),
        ('/science/', 'Science', 'science'),
        ('/politics/', 'Politics', 'politics'),
        ('/finance/', 'Finance', 'finance'),
        ('/media/', 'Media', 'media'),
        ('/articles/', 'Articles', 'articles'),
        ('/archive/', 'Archive', 'archive'),
    ]

    items = []
    for href, label, page_id in links:
        active_class = ' class="active"' if page_id == active_page else ''
        items.append(f'<li><a href="{href}"{active_class}>{label}</a></li>')

    return '\n            '.join(items)


def build_header(active_page: str = '', date_str: str = None) -> str:
    """
    Build consistent header/navigation HTML.

    Args:
        active_page: Which page to mark as active in navigation
        date_str: Date string to display (defaults to today)
    """
    if date_str is None:
        date_str = datetime.now().strftime('%B %d, %Y')

    nav_links = get_nav_links(active_page)

    return f'''
    <nav class="nav" id="nav" role="navigation" aria-label="Main navigation">
        <a href="/" class="nav-logo" aria-label="DailyTrending.info Home">
            <span>DailyTrending.info</span>
        </a>
        <button class="mobile-menu-toggle" id="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false">
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
        </button>
        <ul class="nav-links" id="nav-links">
            {nav_links}
        </ul>
        <div class="nav-actions">
            <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark/light mode" title="Toggle dark/light mode">
                <svg class="sun-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                </svg>
                <svg class="moon-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
            </button>
            <a href="https://github.com/fubak/daily-trending-info" class="nav-github" target="_blank" rel="noopener noreferrer" aria-label="View source on GitHub" title="View source on GitHub">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
            </a>
        </div>
    </nav>'''


def build_footer(date_str: str = None, style_info: str = '') -> str:
    """
    Build consistent footer HTML.

    Args:
        date_str: Date string to display (defaults to today)
        style_info: Optional style/theme info line
    """
    if date_str is None:
        date_str = datetime.now().strftime('%B %d, %Y')

    style_line = f'<p class="footer-description">{style_info}</p>' if style_info else ''

    return f'''
    <footer class="footer" role="contentinfo">
        <div class="footer-content">
            <div class="footer-main">
                <div class="footer-brand">DailyTrending.info</div>
                <p class="footer-description">
                    An autonomous trend aggregation website that regenerates daily
                    with fresh content from multiple sources worldwide.
                </p>
                {style_line}
                <a href="https://github.com/fubak/daily-trending-info" class="footer-github" target="_blank" rel="noopener noreferrer">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                    View Source on GitHub
                </a>
            </div>
            <div class="footer-links-section">
                <h4 class="footer-section-title">Explore</h4>
                <ul class="footer-links">
                    <li><a href="/">Home</a></li>
                    <li><a href="/tech/">Tech</a></li>
                    <li><a href="/world/">World</a></li>
                    <li><a href="/articles/">Articles</a></li>
                    <li><a href="/archive/">Archive</a></li>
                    <li><a href="/media/">Media</a></li>
                </ul>
            </div>
        </div>
        <div class="footer-bottom">
            <span>Generated on {date_str}</span>
            <div class="footer-actions">
                <a href="/archive/" class="archive-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 3h18v18H3z"></path>
                        <path d="M21 9H3"></path>
                        <path d="M9 21V9"></path>
                    </svg>
                    View Archive
                </a>
                <a href="https://github.com/fubak/daily-trending-info" class="github-btn" target="_blank" rel="noopener noreferrer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                    GitHub
                </a>
            </div>
        </div>
    </footer>'''


def get_header_styles() -> str:
    """Get CSS styles for the header/navigation."""
    return '''
        /* Navigation */
        .nav {
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 2rem;
            background: var(--color-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--color-border);
        }

        .nav-logo {
            font-family: var(--font-primary);
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--color-text);
            text-decoration: none;
            display: flex;
            align-items: center;
        }

        .nav-links {
            display: flex;
            gap: 0.25rem;
            list-style: none;
            margin: 0;
            padding: 0;
        }

        .nav-links a {
            padding: 0.5rem 1rem;
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 500;
            border-radius: 0.5rem;
            transition: color 0.2s ease, background 0.2s ease;
        }

        .nav-links a:hover {
            color: var(--color-text);
            background: rgba(255, 255, 255, 0.05);
        }

        .nav-links a.active {
            color: var(--color-accent);
            background: rgba(255, 255, 255, 0.08);
        }

        .nav-actions {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .nav-date {
            font-size: 0.85rem;
            color: var(--color-muted);
            display: none;
        }

        @media (min-width: 768px) {
            .nav-date {
                display: block;
            }
        }

        .theme-toggle, .nav-github {
            background: none;
            border: none;
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 0.5rem;
            color: var(--color-muted);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s ease, background 0.2s ease;
        }

        .theme-toggle:hover, .nav-github:hover {
            color: var(--color-text);
            background: rgba(255, 255, 255, 0.05);
        }

        .theme-toggle .sun-icon { display: none; }
        .theme-toggle .moon-icon { display: block; }
        body.light-mode .theme-toggle .sun-icon { display: block; }
        body.light-mode .theme-toggle .moon-icon { display: none; }

        /* Mobile menu */
        .mobile-menu-toggle {
            display: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 0.5rem;
            z-index: 101;
        }

        .hamburger-line {
            display: block;
            width: 24px;
            height: 2px;
            background: var(--color-text);
            margin: 5px 0;
            transition: transform 0.3s ease;
        }

        @media (max-width: 900px) {
            .mobile-menu-toggle {
                display: block;
            }

            .nav-links {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                flex-direction: column;
                background: var(--color-bg);
                border-bottom: 1px solid var(--color-border);
                padding: 1rem;
            }

            .nav-links.active {
                display: flex;
            }

            .nav-links li {
                opacity: 0;
                transform: translateY(-10px);
                transition: opacity 0.3s ease, transform 0.3s ease;
            }

            .nav-links.active li {
                opacity: 1;
                transform: translateY(0);
            }

            .nav-links.active li:nth-child(1) { transition-delay: 0.1s; }
            .nav-links.active li:nth-child(2) { transition-delay: 0.15s; }
            .nav-links.active li:nth-child(3) { transition-delay: 0.2s; }
            .nav-links.active li:nth-child(4) { transition-delay: 0.25s; }
            .nav-links.active li:nth-child(5) { transition-delay: 0.3s; }
            .nav-links.active li:nth-child(6) { transition-delay: 0.35s; }
            .nav-links.active li:nth-child(7) { transition-delay: 0.4s; }
            .nav-links.active li:nth-child(8) { transition-delay: 0.45s; }
            .nav-links.active li:nth-child(9) { transition-delay: 0.5s; }

            .nav-links a {
                display: block;
                padding: 0.75rem 1rem;
            }
        }
    '''


def get_footer_styles() -> str:
    """Get CSS styles for the footer."""
    return '''
        /* Footer */
        .footer {
            margin-top: 4rem;
            padding: 3rem 2rem;
            background: var(--color-card-bg);
            border-top: 1px solid var(--color-border);
        }

        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 3rem;
        }

        @media (max-width: 768px) {
            .footer-content {
                grid-template-columns: 1fr;
                gap: 2rem;
            }
        }

        .footer-brand {
            font-family: var(--font-primary);
            font-weight: 700;
            font-size: 1.5rem;
            color: var(--color-text);
            margin-bottom: 1rem;
        }

        .footer-description {
            color: var(--color-muted);
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }

        .footer-github {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color 0.2s ease;
        }

        .footer-github:hover {
            color: var(--color-accent);
        }

        .footer-section-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--color-text);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .footer-links {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .footer-links li {
            margin-bottom: 0.5rem;
        }

        .footer-links a {
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color 0.2s ease;
        }

        .footer-links a:hover {
            color: var(--color-accent);
        }

        .footer-bottom {
            max-width: 1200px;
            margin: 2rem auto 0;
            padding-top: 2rem;
            border-top: 1px solid var(--color-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            font-size: 0.85rem;
            color: var(--color-muted);
        }

        .footer-actions {
            display: flex;
            gap: 1rem;
        }

        .footer-actions a {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--color-muted);
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            background: rgba(255, 255, 255, 0.05);
            transition: color 0.2s ease, background 0.2s ease;
        }

        .footer-actions a:hover {
            color: var(--color-text);
            background: rgba(255, 255, 255, 0.1);
        }
    '''


def get_theme_script() -> str:
    """Get JavaScript for theme toggle and mobile menu."""
    return '''
    <script>
        // Theme toggle functionality
        (function() {
            const themeToggle = document.getElementById('theme-toggle');
            const body = document.body;

            // Check for saved theme preference
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {
                body.classList.remove('dark-mode');
                body.classList.add('light-mode');
            } else {
                body.classList.remove('light-mode');
                body.classList.add('dark-mode');
            }

            if (themeToggle) {
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
            }
        })();

        // Mobile menu toggle
        (function() {
            const menuToggle = document.getElementById('mobile-menu-toggle');
            const navLinks = document.getElementById('nav-links');

            if (menuToggle && navLinks) {
                menuToggle.addEventListener('click', function() {
                    navLinks.classList.toggle('active');
                    const isExpanded = navLinks.classList.contains('active');
                    menuToggle.setAttribute('aria-expanded', isExpanded);
                });
            }
        })();
    </script>'''
