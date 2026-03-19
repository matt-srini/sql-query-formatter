## Plan: SQL Formatter UX, SEO, and Retention Overhaul

This plan targets improvements to look & feel, user-friendliness, SEO, and user retention, aiming to make SQL Formatter the top choice for online SQL formatting.

**Steps**

### Phase 1: Visual & UX Enhancements
1. Add favicon and Open Graph/Twitter meta tags for branding and sharing.
2. Add a prominent tagline above the fold (e.g., “The fastest, cleanest way to format SQL online—free and privacy-friendly.”).
3. Add micro-animations to buttons, output area, and modal dialogs for a modern feel.
4. Improve accessibility: ARIA labels, visible focus states, keyboard navigation (tab order, skip to main).
5. Optimize mobile experience: larger touch targets, test and tweak layout for small screens.
6. Add a dismissible “How to use” tip for first-time visitors.
7. Add a “No data stored” or “Privacy-first” badge if true.

### Phase 2: SEO & Technical Improvements
8. Refactor HTML for semantic structure: use <main>, <nav>, <section>, <aside>, <footer>.
9. Ensure proper heading hierarchy: single <h1>, logical <h2>/<h3>.
10. Add FAQ section with accordion UI and FAQ schema markup.
11. Add JSON-LD structured data for FAQ, product, and website.
12. Inline critical CSS for above-the-fold content; defer non-critical JS.
13. Optimize font and highlight.js loading (defer/lazy load).
14. Link sitemap.xml in <head> and add robots.txt to allow crawling.
15. Add <link rel="canonical"> in <head>.
16. Add descriptive alt attributes to all images/icons.

### Phase 3: Retention & “Come Back” Features
17. Store user preferences (theme, last-used options) in localStorage.
18. Add a “Copy link” button to share formatted SQL (encode SQL in URL or use a shortlink service).
19. Show last 3 formatted queries (local only, privacy-safe).
20. Add a “Star us on GitHub” badge and/or user testimonials for social proof.

### Phase 4: Verification
21. Run Google Lighthouse and address any performance, accessibility, or SEO warnings.
22. Manually test on mobile and desktop for usability, speed, and accessibility.
23. Validate structured data and FAQ schema with Google’s Rich Results Test.

**Relevant files**
- frontend/index.html — meta tags, semantic HTML, FAQ, canonical, onboarding tip, badge, share link, testimonials
- frontend/style.css — animations, focus states, mobile tweaks, FAQ accordion
- frontend/app.js — onboarding tip logic, personalization, share link, history, accessibility
- static/favicon.ico — favicon asset
- frontend/sitemap.xml — sitemap reference
- robots.txt — allow crawling

**Verification**
1. Run Lighthouse and fix all major warnings (performance, accessibility, SEO).
2. Use Google Rich Results Test to verify FAQ and structured data.
3. Test on mobile and desktop for usability and speed.
4. Validate that all new features (FAQ, onboarding, share link, history, badge) work as intended.

**Decisions**
- All changes must keep the site fast and lightweight (no heavy frameworks or large dependencies).
- Privacy is a core value: no user SQL or history is sent to the server.
- Accessibility and SEO are as important as visual polish.

**Further Considerations**
1. If user feedback suggests, consider adding more formatting options or dialects.
2. If traffic grows, consider CDN for static assets and backend scaling.
