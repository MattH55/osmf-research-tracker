<?xml version="1.0" encoding="UTF-8"?>
<!--
  Renders the tracker's RSS feeds (feeds/*.xml, digest/feed.xml) as a readable
  page when someone opens the feed URL in a browser instead of a feed reader.
  Referenced by the xml-stylesheet instruction that build_condition_feeds.py and
  build_digest.py write at the top of each feed. Readers ignore it.
-->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" encoding="UTF-8" indent="yes"/>

  <xsl:template match="/">
    <html lang="en">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title><xsl:value-of select="/rss/channel/title"/></title>
        <meta name="robots" content="noindex"/>
        <style>
          :root { --ink: #0e1444; --ink-2: #2b3050; --muted: #6b7290; --accent: #ff9800; --accent-2: #e64a19; --surface: #f6f7fb; --border: rgba(14,20,68,0.09); }
          * { box-sizing: border-box; }
          body { margin: 0; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: #fff; line-height: 1.6; }
          header { background: linear-gradient(135deg, #0e1444 0%, #1a2266 100%); color: #fff; padding: 3rem 1.25rem 2.5rem; }
          .wrap { max-width: 860px; margin: 0 auto; }
          .eyebrow { display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #ffb74d; background: rgba(255,152,0,0.14); border: 1px solid rgba(255,152,0,0.35); border-radius: 999px; padding: 0.35rem 0.9rem; margin-bottom: 1rem; }
          h1 { font-size: clamp(1.6rem, 4vw, 2.3rem); line-height: 1.15; letter-spacing: -0.02em; margin: 0 0 0.8rem; }
          header p { color: rgba(255,255,255,0.75); margin: 0 0 1.2rem; max-width: 60ch; }
          .actions a { display: inline-block; margin: 0 0.6rem 0.5rem 0; padding: 0.55rem 1rem; border-radius: 10px; font-weight: 700; font-size: 0.9rem; text-decoration: none; }
          .btn { background: linear-gradient(135deg, #ff9800, #e64a19); color: #fff; }
          .ghost { border: 1px solid rgba(255,255,255,0.35); color: #fff; }
          .note { font-size: 0.82rem; color: rgba(255,255,255,0.6); margin: 0; }
          .note code { background: rgba(255,255,255,0.12); padding: 0.1rem 0.4rem; border-radius: 5px; font-size: 0.8rem; word-break: break-all; }
          main { padding: 2rem 1.25rem 4rem; }
          .meta { font-size: 0.82rem; color: var(--muted); margin: 0 0 1.5rem; }
          article { border: 1px solid var(--border); border-radius: 16px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; background: #fff; box-shadow: 0 1px 2px rgba(14,20,68,0.04); }
          article h2 { font-size: 1.08rem; line-height: 1.35; margin: 0 0 0.4rem; }
          article h2 a { color: var(--ink); text-decoration: none; }
          article h2 a:hover { color: var(--accent-2); }
          .tags { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0 0 0.6rem; }
          .tag { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; background: var(--surface); color: var(--ink-2); border-radius: 999px; padding: 0.18rem 0.55rem; }
          .date { font-size: 0.78rem; color: var(--muted); }
          .body { font-size: 0.92rem; color: var(--ink-2); }
          .body p { margin: 0.4rem 0; }
          .body a { color: var(--accent-2); }
          footer { border-top: 1px solid var(--border); padding: 1.5rem 1.25rem; font-size: 0.82rem; color: var(--muted); text-align: center; }
        </style>
      </head>
      <body>
        <header>
          <div class="wrap">
            <span class="eyebrow">RSS feed · Open Source Medicine Foundation</span>
            <h1><xsl:value-of select="/rss/channel/title"/></h1>
            <p><xsl:value-of select="/rss/channel/description"/></p>
            <p class="actions">
              <a class="btn" href="{/rss/channel/link}">Open the web page</a>
              <a class="ghost" href="https://research.opensourcemed.info/feeds/index.html">All feeds</a>
            </p>
            <p class="note">This is a feed. To follow it, copy this address into a feed reader or an email-by-RSS service: <code><xsl:value-of select="/rss/channel/atom:link[@rel='self']/@href"/></code></p>
          </div>
        </header>
        <main>
          <div class="wrap">
            <p class="meta">
              <xsl:value-of select="count(/rss/channel/item)"/> entries · last built <xsl:value-of select="/rss/channel/lastBuildDate"/> · newest first
            </p>
            <xsl:for-each select="/rss/channel/item">
              <article>
                <h2><a href="{link}"><xsl:value-of select="title"/></a></h2>
                <xsl:if test="category">
                  <p class="tags">
                    <xsl:for-each select="category"><span class="tag"><xsl:value-of select="."/></span></xsl:for-each>
                  </p>
                </xsl:if>
                <xsl:if test="pubDate"><p class="date"><xsl:value-of select="pubDate"/></p></xsl:if>
                <div class="body"><xsl:value-of select="description" disable-output-escaping="yes"/></div>
              </article>
            </xsl:for-each>
          </div>
        </main>
        <footer>Research information, not medical advice. · <a href="https://opensourcemed.info/">opensourcemed.info</a></footer>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
