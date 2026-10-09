
TV-to-Book Recommendation Machine by Adriana Jun Machado (Enhance Enhance LLC)
---------------------------------
Recommends books published before 2010 based on modern TV shows (any show that has aired from 2016 to the present).

I used Figma Make to create a design prototype and Claude Code to create a recommendation machine prototype. I then used VSCode to customize and edit the prototypes to the final product.

Output format:
    If you like [tv_show], then you'll love [book]. 

Each book links to its Goodreads page. By default the link is a Goodreads search for the title + author.

How it works:
  1. Every show and book is described by weighted theme tags.
  2. Rare tags count more than common ones (TF-IDF style weighting).
  3. Cosine similarity ranks books against the show you picked.
  4. Emotional weights refine the ranking. Every show and book also has an
     emotional fingerprint: eight feelings (joy, sadness, fear, anger, tension, warmth, humor, hope), an overall sentiment (bleak to uplifting) and an intensity (gentle to relentless). 
     Final score = (1 - w) * theme match + w * emotional match, where w is the emotion weight (default 0.35, set with --emotion-weight; 0 = themes only).
  5. A small set of hand-curated "editor's picks" always rank first, so signature pairings (e.g. Real Housewives -> Valley of the Dolls) are guaranteed.

Live site: https://ajmachado42.github.io/Book-Recommender/

Publishing:
  The site is static and hosted on GitHub Pages. The page reads code/recommendations.json instead of calling the Python server.
  After editing the catalog in code/book_recommender.py, regenerate the JSON and push:
      python3 code/build_static.py
      git add -A && git commit -m "Update catalog" && git push
  To run the original Python server locally instead: python3 code/book_recommendations.py
