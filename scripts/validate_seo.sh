#!/bin/bash
set -e

echo "🔍 SEO Validation Suite"
echo "======================="

# Check if index.html exists
if [ ! -f "../public/index.html" ]; then
    echo "❌ public/index.html not found. Please run the build first."
    exit 1
fi

# 1. Check title tag
echo -e "\n1. Title Tag:"
TITLE=$(grep -o '<title>[^<]*</title>' ../public/index.html | sed 's/<[^>]*>//g')
echo "   $TITLE"
if [[ $TITLE == *"CMMC Watch"* ]]; then
    echo "   ✅ Title is correct"
else
    echo "   ⚠️  Title should contain: CMMC Watch"
fi

# 2. Check meta description
echo -e "\n2. Meta Description:"
DESC=$(grep -o 'name="description" content="[^"]*"' ../public/index.html | sed 's/.*content="//;s/"//')
echo "   ${DESC:0:100}..."
if [[ $DESC == *"Real-time dashboard"* ]]; then
    echo "   ✅ Meta description is optimized"
else
    echo "   ⚠️  Meta description could be improved"
fi

# 3. Check JSON-LD
echo -e "\n3. Structured Data:"
if grep -q "application/ld+json" ../public/index.html; then
    SCHEMA_COUNT=$(grep -c "@type" ../public/index.html || true)
    echo "   ✅ JSON-LD found ($SCHEMA_COUNT @type declarations)"

    # Check for specific schema types
    if grep -q '"@type": "WebSite"' ../public/index.html; then
        echo "   ✅ WebSite schema present"
    fi
    if grep -q '"@type": "CollectionPage"' ../public/index.html; then
        echo "   ✅ CollectionPage schema present"
    fi
    if grep -q '"@type": "FAQPage"' ../public/index.html; then
        echo "   ✅ FAQPage schema present"
    fi
else
    echo "   ❌ JSON-LD missing"
fi

# 4. Check navigation
echo -e "\n4. Navigation:"
if grep -q 'href="/archive/"' ../public/index.html; then
    echo "   ✅ Archive link present in navigation"
else
    echo "   ⚠️  Archive link missing"
fi

if grep -q 'href="/articles/"' ../public/index.html; then
    echo "   ✅ Articles link present in navigation"
else
    echo "   ⚠️  Articles link missing"
fi

# 5. Check OG image
echo -e "\n5. Open Graph:"
OG_IMAGE=$(grep -o 'property="og:image" content="[^"]*"' ../public/index.html | sed 's/.*content="//;s/"//')
echo "   OG Image: $OG_IMAGE"
if [[ $OG_IMAGE == *"og-image.png"* ]]; then
    echo "   ✅ Static OG image configured"
else
    echo "   ⚠️  Using dynamic OG image (${OG_IMAGE:0:50}...)"
fi

# 6. Check canonical
echo -e "\n6. Canonical URL:"
if grep -q 'rel="canonical" href="https://cmmcwatch.com/"' ../public/index.html; then
    echo "   ✅ Canonical URL correct"
else
    echo "   ⚠️  Canonical URL issue"
fi

# 7. Check alt text
echo -e "\n7. Image Alt Text:"
PLACEHOLDER_COUNT=$(grep -c 'alt="Placeholder image"' ../public/index.html || true)
if [ "$PLACEHOLDER_COUNT" -eq 0 ]; then
    echo "   ✅ No generic 'Placeholder image' alt text found"
else
    echo "   ⚠️  Found $PLACEHOLDER_COUNT instances of generic 'Placeholder image' alt text"
fi

# 8. Check sitemap
echo -e "\n8. Sitemap:"
if [ -f "../public/sitemap.xml" ]; then
    URL_COUNT=$(grep -c "<url>" ../public/sitemap.xml || true)
    echo "   ✅ Sitemap exists with $URL_COUNT URLs"

    # Check for archive pages in sitemap
    ARCHIVE_COUNT=$(grep -c "/archive/" ../public/sitemap.xml || true)
    if [ "$ARCHIVE_COUNT" -gt 0 ]; then
        echo "   ✅ Archive pages in sitemap ($ARCHIVE_COUNT entries)"
    fi
else
    echo "   ⚠️  Sitemap not found"
fi

echo -e "\n✅ SEO validation complete!"
echo "==========================="
