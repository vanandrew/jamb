// Apple-inspired styling for jamb PDF output, included in the Typst preamble.
// Near-black text in a clean sans-serif with a single blue accent for links.
// Fonts fall back gracefully when "Helvetica Neue" is unavailable.

#set text(
  font: ("Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans", "Liberation Sans"),
  fill: rgb("#1d1d1f"),
)

#show link: set text(fill: rgb("#0071e3"))
#show heading: set text(fill: rgb("#1d1d1f"))
