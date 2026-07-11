import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone
from collections import Counter, defaultdict
import numpy as np

# Load data from the ParentsVaccineGUide directory
with open(r'c:\Users\matth\OneDrive\Documents\OpenSourceMed\ParentsVaccineGUide\imahealth_archive.json', 'r', encoding='utf-8') as f:
    articles = json.load(f)

# Parse dates and sort oldest first
for a in articles:
    a['date'] = datetime.fromisoformat(a['post_date'].replace('Z', '+00:00'))

articles.sort(key=lambda a: a['date'])

# Count by type
type_counts = Counter(a['type'] for a in articles)

print(f"Total articles: {len(articles)}")
print(f"Date range: {articles[0]['date'].strftime('%b %d, %Y')} to {articles[-1]['date'].strftime('%b %d, %Y')}")
print(f"Types: {dict(type_counts)}")

# ============================================================
# FIGURE 1: Full timeline with engagement
# ============================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), gridspec_kw={'height_ratios': [1.6, 1]})
fig.suptitle('IMA Health Substack — Publication Timeline & Engagement\n(June 12 – July 11, 2026)', 
             fontsize=18, fontweight='bold', y=0.98)

# --- TOP PANEL: Scatter timeline by type ---
colors = {'newsletter': '#2196F3', 'podcast': '#FF5722', 'restack': '#9C27B0'}
for a in articles:
    c = colors.get(a['type'], '#607D8B')
    ax1.scatter(a['date'], a['like_count'], 
                c=c, s=max(30, a['comment_count'] * 3 + 20),
                alpha=0.75, edgecolors='black', linewidth=0.5,
                label=a['type'] if a['type'] not in [prev.get('type') for prev in articles[:articles.index(a)]] else "")

# Annotate top 5 by likes
top_by_likes = sorted(articles, key=lambda a: a['like_count'], reverse=True)[:5]
for a in top_by_likes:
    ax1.annotate(a['title'][:60] + '...', 
                 (a['date'], a['like_count']),
                 fontsize=7, alpha=0.85,
                 xytext=(5, 5), textcoords='offset points',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

ax1.set_ylabel('Like Count', fontsize=12, fontweight='bold')
ax1.set_title('Article Engagement (bubble size = comment count)', fontsize=13)
ax1.legend(loc='upper left', fontsize=9)
ax1.grid(True, alpha=0.3)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

# --- BOTTOM PANEL: Weekly posting frequency ---
from collections import defaultdict
weekday_counts = defaultdict(int)
type_by_week = defaultdict(lambda: defaultdict(int))
weekly_counts = defaultdict(int)
for a in articles:
    week = a['date'].strftime('%Y-W%U')
    weekly_counts[week] += 1
    day = a['date'].strftime('%A')
    weekday_counts[day] += 1
    type_by_week[week][a['type']] += 1

# Bar chart of weekly counts
weeks_sorted = sorted(weekly_counts.keys())
week_labels = []
for w in weeks_sorted:
    # Parse to get Monday date
    year, wk = w.split('-W')
    week_labels.append(f"Week {int(wk)}")

x = np.arange(len(weeks_sorted))
newsletter_counts = [type_by_week[w].get('newsletter', 0) for w in weeks_sorted]
podcast_counts = [type_by_week[w].get('podcast', 0) for w in weeks_sorted]
restack_counts = [type_by_week[w].get('restack', 0) for w in weeks_sorted]

bars1 = ax2.bar(x, newsletter_counts, color='#2196F3', label='Newsletter', edgecolor='white')
bars2 = ax2.bar(x, podcast_counts, bottom=newsletter_counts, color='#FF5722', label='Podcast', edgecolor='white')
# bars3 = ax2.bar(x, restack_counts, bottom=[n+p for n,p in zip(newsletter_counts, podcast_counts)], color='#9C27B0', label='Restack', edgecolor='white')

for i, (n, p, r) in enumerate(zip(newsletter_counts, podcast_counts, restack_counts)):
    total = n + p + r
    ax2.text(i, total + 0.15, str(total), ha='center', fontweight='bold', fontsize=10)

ax2.set_xticks(x)
ax2.set_xticklabels(week_labels)
ax2.set_ylabel('Articles per Week', fontsize=12, fontweight='bold')
ax2.set_title('Weekly Publishing Cadence', fontsize=13)
ax2.legend(loc='upper right', fontsize=9)
ax2.set_ylim(0, max([n+p+r for n,p,r in zip(newsletter_counts, podcast_counts, restack_counts)]) + 1.5)
ax2.grid(True, alpha=0.3, axis='y')

plt.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig('imahealth_substack_timeline.png', dpi=150, bbox_inches='tight')
print("Saved: imahealth_substack_timeline.png")

# ============================================================
# FIGURE 2: Cumulative posts over time
# ============================================================
fig2, ax = plt.subplots(figsize=(14, 5))
dates_sorted = [a['date'] for a in articles]
cumulative = list(range(1, len(dates_sorted) + 1))

ax.fill_between(dates_sorted, cumulative, alpha=0.4, color='#4CAF50')
ax.plot(dates_sorted, cumulative, 'o-', color='#2E7D32', markersize=6, linewidth=2)

ax.set_ylabel('Cumulative Articles', fontsize=12, fontweight='bold')
ax.set_title('IMA Health Substack — Cumulative Publication Growth', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
ax.set_ylim(0, max(cumulative) + 2)

fig2.tight_layout()
fig2.savefig('imahealth_cumulative_growth.png', dpi=150, bbox_inches='tight')
print("Saved: imahealth_cumulative_growth.png")

# ============================================================
# FIGURE 3: Day-of-week heatmap
# ============================================================
fig3, ax3 = plt.subplots(figsize=(10, 4))
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
day_counts = [weekday_counts[d] for d in days_order]
bars = ax3.bar(days_order, day_counts, color=['#FF9800' if c == max(day_counts) else '#BDBDBD' for c in day_counts], edgecolor='white')
for bar, count in zip(bars, day_counts):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, str(count), ha='center', fontweight='bold')
ax3.set_title('Articles by Day of Week', fontsize=14, fontweight='bold')
ax3.set_ylabel('Number of Articles', fontsize=12)
ax3.grid(True, alpha=0.3, axis='y')
ax3.set_ylim(0, max(day_counts) + 1)
fig3.tight_layout()
fig3.savefig('imahealth_day_of_week.png', dpi=150, bbox_inches='tight')
print("Saved: imahealth_day_of_week.png")

# ============================================================
# Print summary stats
# ============================================================
print(f"\n--- SUMMARY ---")
print(f"Total articles: {len(articles)}")
print(f"Newsletters: {type_counts.get('newsletter', 0)}")
print(f"Podcasts: {type_counts.get('podcast', 0)}")
print(f"Restacks: {type_counts.get('restack', 0)}")
print(f"Total likes: {sum(a['like_count'] for a in articles)}")
print(f"Total comments: {sum(a['comment_count'] for a in articles)}")
print(f"Avg likes/article: {sum(a['like_count'] for a in articles) / len(articles):.1f}")
avg_per_week = len(articles) / len(weeks_sorted)
print(f"Weeks active: {len(weeks_sorted)}")
print(f"Avg articles/week: {avg_per_week:.1f}")
print(f"\nMost liked: {top_by_likes[0]['title']} ({top_by_likes[0]['like_count']} likes)")
print(f"Most commented: {max(articles, key=lambda a: a['comment_count'])['title']} ({max(articles, key=lambda a: a['comment_count'])['comment_count']} comments)")