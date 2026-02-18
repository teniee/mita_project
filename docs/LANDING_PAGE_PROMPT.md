# PROMPT FOR AI WEBSITE BUILDER

Copy everything below this line and paste into v0 / Lovable / Bolt / Cursor / etc.

---

Build a stunning, premium-quality landing page for **MITA** — an AI-powered personal finance app. The site should feel like a $50M startup's marketing page — polished, modern, emotionally resonant, with smooth animations and world-class design. Think Linear.app meets Stripe meets Headspace in visual quality.

## BRAND & PRODUCT

**Product Name:** MITA — Money Intelligence Task Assistant
**Tagline:** "A Budget That Adapts to Real Life"
**One-liner:** AI-powered daily budgeting app that automatically redistributes your budget when life happens — so one bad day never ruins your month.

**The Problem We Solve:**
Traditional budgeting apps (Mint, YNAB, Monarch) treat users like failures. You set a monthly budget, overspend in one category, and feel guilty. 78% of people abandon their budget within 2 weeks. MITA fixes this with intelligent daily budgets that auto-adjust.

**How It Works (Core Algorithm):**
1. User enters monthly income
2. Income is distributed across spending categories (Food, Transport, Entertainment, etc.)
3. Each category's monthly budget is divided into DAILY allowances
4. User sees exactly how much they can spend TODAY in each category
5. When they overspend in one category → AI automatically redistributes the remaining budget across remaining days
6. No guilt. No failure. Budget adapts to reality.

**Example:** You have $600/month for groceries = $20/day. Monday you spend $35. Instead of showing "OVER BUDGET" in red, MITA recalculates: your remaining 29 days now get $19.48/day. You're still on track. No guilt.

## DESIGN SYSTEM

**Color Palette:**
- Primary: Deep Navy Blue `#193C57` — trust, intelligence, stability
- Accent: Warm Gold `#FFD25F` — optimism, success, growth
- Background: Warm Cream `#FFF9F0` — welcoming, calm, approachable
- Surface: Pure White `#FFFFFF` — clean cards and containers
- Success: `#4CAF50` (green — under budget)
- Warning: `#FF9800` (orange — approaching limit)
- Danger: `#F44336` (red — overspent)

**Typography:**
- Headlines: "Sora" font, bold (700), confident and modern
- Body text: "Manrope" font, regular (400), readable and balanced
- If Sora/Manrope unavailable, use Inter for both

**Visual Style:**
- Warm, human, approachable — NOT cold corporate fintech
- Generous whitespace, large typography, smooth micro-animations
- Rounded corners everywhere (buttons: 24px radius, cards: 16px radius)
- Subtle shadows on cards (rgba(0,0,0,0.08) 0 4px 24px)
- Glassmorphism effects on hero section elements
- Gradient accents: Navy → slightly lighter blue for depth
- Floating elements with subtle parallax on scroll

**Animations:**
- Hero: Smooth fade-in + scale from 0.95 to 1.0 on load (600ms ease-out)
- Sections: Reveal on scroll with staggered fade-up animations (200ms delay between elements)
- Numbers/stats: Count-up animation when scrolling into view
- Budget redistribution: Animated visualization showing money flowing between categories (key selling point — make this beautiful)
- Buttons: Subtle lift + shadow increase on hover (150ms)
- Mobile mockup: Gentle floating animation (up/down 10px, 3s loop)

## PAGE STRUCTURE

### Section 1: HERO (Full viewport height)

**Layout:** Split — left side text, right side phone mockup

**Left side:**
- Small badge/pill above headline: "AI-Powered Finance" with sparkle icon
- Main headline (48-64px): "Money That Finally Makes Sense"
- Subheadline (18-20px, muted color): "The first budget that adapts to how you actually spend. AI-powered daily budgeting that turns financial anxiety into financial confidence."
- Two CTA buttons side by side:
  - Primary: "Start Free" (navy background, white text, large, with right arrow →)
  - Secondary: "Watch Demo" (outline/ghost button with play icon ▶)
- Trust line below buttons: "No credit card required · Free forever · 2 min setup"
- Small row of 5-star rating: "★★★★★ Loved by 10,000+ users"

**Right side:**
- Beautiful 3D-perspective phone mockup showing the app's calendar screen
- Calendar shows days colored green/yellow/red
- Floating UI cards around the phone showing:
  - "Today's Budget: $47.50" (green card)
  - "AI Insight: You save 23% more on weekdays" (gold card)
  - "Goal: iPhone 16 — 67% complete" (progress bar card)
- Subtle glow/gradient behind the phone

**Background:** Warm cream `#FFF9F0` with subtle gradient mesh pattern (very light navy + gold blobs)

---

### Section 2: PROBLEM STATEMENT

**Headline:** "Why Your Budget Keeps Failing"
**Subheadline:** "It's not you. It's your app."

**Three problem cards in a row:**

Card 1: 🔒 "Rigid Monthly Limits"
"Set $500 for food. Spend $520. App screams 'OVER BUDGET!' in angry red. Thanks for the guilt trip."

Card 2: 😰 "The Shame Spiral"
"One overspend → feel guilty → stop tracking → blow entire budget → start over January 1st. Sound familiar?"

Card 3: ⏰ "Manual Data Entry Hell"
"Spending 30 minutes entering receipts defeats the purpose of saving time. Life's too short for spreadsheets."

**Bottom stat:** "78% of people abandon their budget within 14 days" — with source attribution

**Visual:** Dark navy background section for contrast. White text. Cards have slight transparency/glassmorphism.

---

### Section 3: THE SOLUTION — HOW MITA WORKS

**Headline:** "Meet the Budget That Actually Works"
**Subheadline:** "Three steps. Zero guilt. Real results."

**Interactive/animated 3-step process:**

**Step 1:** "Set It Once"
- Icon: Wallet with sparkles
- "Enter your income and choose your categories. MITA creates your daily budget automatically. Takes 2 minutes."
- Visual: Simple form UI mockup

**Step 2:** "Live Your Life"
- Icon: Coffee cup / shopping bag
- "Spend normally. Log expenses with one tap or snap a receipt photo. MITA categorizes everything automatically."
- Visual: Receipt scanning animation

**Step 3:** "MITA Adapts"
- Icon: Brain with refresh arrows
- "Overspent on Tuesday? MITA intelligently redistributes your remaining budget. You stay on track without trying."
- Visual: **THIS IS THE KEY ANIMATION** — Show a budget bar chart where one category goes over, and the remaining days' bars smoothly shrink/adjust. Money particles flow from the overspent category back into remaining days. Make this beautiful and mesmerizing.

**Background:** White/cream. Each step appears as you scroll.

---

### Section 4: FEATURE SHOWCASE

**Headline:** "Everything You Need. Nothing You Don't."

**Bento grid layout (like Apple's feature pages):**

**Large card (spans 2 columns):** "AI Daily Budgeting"
- "See exactly what you can spend today. For each category. Updated in real-time."
- Visual: Calendar UI with daily amounts per category

**Medium card:** "Receipt Scanning"
- "Point. Shoot. Done. 99.8% accuracy."
- Icon: Camera with receipt
- "Powered by Google Vision AI"

**Medium card:** "AI Financial Advisor"
- "Chat with your personal AI about money. Get insights, not lectures."
- Icon: Chat bubble with brain
- "Powered by GPT-4"

**Small card:** "Savings Goals"
- "Set goals. Track progress. Celebrate wins."
- Visual: Progress ring at 67%

**Small card:** "Spending Calendar"
- "See your month at a glance. Green days, gold days, red days."
- Visual: Mini calendar with colored dots

**Small card:** "Smart Alerts"
- "Get warned BEFORE you overspend. Not after."
- Icon: Bell with shield

**Medium card:** "Offline-First"
- "Full functionality without internet. Syncs when you're back online."
- Icon: Phone with checkmark + cloud

**Small card:** "Bank-Level Security"
- "AES-256 encryption. Biometric auth. GDPR compliant."
- Icon: Lock/shield

---

### Section 5: SOCIAL PROOF & RESULTS

**Headline:** "Real Results. Real People."

**Stats bar (horizontal, with count-up animation):**
- "23%" — Average spending reduction
- "5 hrs/mo" — Time saved on tracking
- "15%" — Increase in savings rate
- "2 min" — Average setup time

**Three testimonial cards with photos:**

Testimonial 1:
"I finally stopped feeling guilty about buying coffee. MITA adjusts my budget automatically — one splurge doesn't ruin my month anymore."
— Sarah K., 32, Marketing Manager
★★★★★

Testimonial 2:
"The receipt scanning alone saves me 30 minutes every week. And the AI insights showed me I was spending $400/month on subscriptions I forgot about."
— Marcus T., 28, Software Engineer
★★★★★

Testimonial 3:
"For the first time in my life, budgeting doesn't feel like punishment. MITA treats me like a human, not a spreadsheet."
— Jessica L., 41, Small Business Owner
★★★★★

**Trust badges row:**
- "99.95% Uptime"
- "Bank-Level Encryption"
- "GDPR Compliant"
- "SOC 2 Ready"

---

### Section 6: PRICING

**Headline:** "Simple Pricing. No Surprises."
**Subheadline:** "Start free. Upgrade when you're ready. Cancel anytime."

**Two pricing cards side by side (centered):**

**FREE card:**
- Price: "$0" with "Forever free" subtitle
- Features list with checkmarks:
  ✓ Daily category budgeting
  ✓ Manual expense tracking
  ✓ 1 savings goal
  ✓ Monthly reports
  ✓ Calendar view
  ✓ Basic categorization
- CTA button: "Get Started Free" (outline style)

**PREMIUM card (highlighted, with "Most Popular" badge):**
- Price: "$9.99" with "/month" subtitle and "or $99/year (save 17%)" below
- Features list with checkmarks:
  ✓ Everything in Free
  ✓ Unlimited OCR receipt scanning
  ✓ AI financial insights (GPT-4)
  ✓ Advanced spending analytics
  ✓ Unlimited savings goals
  ✓ Behavioral pattern analysis
  ✓ Predictive budgeting
  ✓ Priority support
- CTA button: "Start 14-Day Free Trial" (solid navy, prominent)
- Small text: "No credit card required"

**Background:** Light gradient or subtle pattern to distinguish section

---

### Section 7: COMPARISON TABLE

**Headline:** "Why MITA Wins"

**Comparison table: MITA vs YNAB vs Monarch vs Banking Apps**

| Feature | MITA | YNAB | Monarch | Bank App |
|---------|------|------|---------|----------|
| Daily Budgeting | ✅ | ❌ | ❌ | ❌ |
| AI Redistribution | ✅ | ❌ | ❌ | ❌ |
| Receipt OCR | ✅ | Limited | ✅ | ❌ |
| AI Insights | ✅ GPT-4 | ❌ | Basic | ❌ |
| Offline Mode | ✅ Full | ❌ | ❌ | ❌ |
| Free Tier | ✅ | ❌ ($14.99) | ❌ ($9.99) | ✅ |
| Behavioral AI | ✅ | ❌ | ❌ | ❌ |

Use green checkmarks and red X marks. Highlight MITA's column.

---

### Section 8: FAQ

**Headline:** "Questions? We've Got Answers."

**Accordion-style FAQ (6 items):**

Q: "Is MITA really free?"
A: "Yes! Our free tier includes daily budgeting, expense tracking, and calendar view. Premium adds AI insights, OCR scanning, and advanced analytics for $9.99/month."

Q: "How is MITA different from YNAB or Monarch?"
A: "MITA is the only app with daily category-based budgeting and AI-powered budget redistribution. When you overspend, your budget adapts automatically — no manual adjustments needed."

Q: "Is my financial data safe?"
A: "Absolutely. We use bank-level AES-256 encryption, biometric authentication, and are GDPR compliant. We never sell your data. Period."

Q: "Does it work offline?"
A: "Yes! MITA is built offline-first. Track expenses anywhere, anytime. Everything syncs automatically when you're back online."

Q: "How does the receipt scanning work?"
A: "Simply photograph your receipt. Our AI (Google Vision) extracts the amount, date, and items with 99.8% accuracy, then auto-categorizes the expense."

Q: "Can I cancel anytime?"
A: "Yes, cancel with one tap. No contracts, no hidden fees, no questions asked. Your data stays accessible on the free tier."

---

### Section 9: FINAL CTA (Full-width)

**Background:** Deep navy gradient with subtle animated particles/dots

**Headline (white, large):** "Your Financial Peace of Mind Starts Now"
**Subheadline (white/muted):** "Join 10,000+ people who stopped dreading their bank balance."

**CTA buttons (centered):**
- Primary: "Start Free Today" (gold background `#FFD25F`, navy text, large, with sparkle animation on hover)
- Secondary: "Schedule a Demo" (white outline)

**Below buttons:** App Store + Google Play download badges (side by side)

**Very bottom:** Small text: "Available on iOS, Android & Web"

---

### FOOTER

**Dark navy background**

**4 columns:**
Column 1: MITA logo + short tagline + social media icons (Twitter/X, LinkedIn, Instagram, TikTok)
Column 2: Product — Features, Pricing, Security, Roadmap, API Docs
Column 3: Company — About, Blog, Careers, Press, Contact
Column 4: Legal — Privacy Policy, Terms of Service, Cookie Policy, GDPR

**Bottom bar:** "© 2026 MITA. All rights reserved." + "Made with ❤️ for your financial wellbeing"

---

## TECHNICAL REQUIREMENTS

- **Fully responsive**: Desktop, tablet, mobile — looks perfect on all
- **Performance**: Lighthouse score 95+ (lazy load images, optimize fonts)
- **SEO**: Proper meta tags, Open Graph, structured data
- **Accessibility**: WCAG 2.1 AA compliant, keyboard navigable, screen reader friendly
- **Dark mode**: Support system dark mode preference with appropriate color adjustments
- **Smooth scrolling**: CSS scroll-behavior: smooth
- **Loading**: Skeleton screens or shimmer effects while loading
- **Favicon**: Use a simple "M" letter in navy on gold circle

## ANIMATION LIBRARY
Use Framer Motion (React) or GSAP for scroll-triggered animations. Each section should reveal with a smooth fade-up + slight scale effect as it enters the viewport.

## OVERALL VIBE
The page should feel like opening a beautifully designed book about your financial future. Warm, inviting, trustworthy — but undeniably modern and tech-forward. The user should think: "This feels premium. This feels different. This feels like it was made for ME."

Every pixel should communicate: "We take your money seriously, but we don't take ourselves too seriously."
