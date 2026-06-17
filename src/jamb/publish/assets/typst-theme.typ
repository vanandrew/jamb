// Formal-specification styling for jamb PDF output, included in the Typst
// preamble. Serif body with sans-serif headings, a conservative blue accent,
// and a page footer with "Page X of Y". Fonts fall back gracefully.

#set text(
  font: ("Charter", "Georgia", "Times New Roman", "DejaVu Serif"),
  fill: rgb("#1d1d1f"),
)

#show heading: set text(
  font: ("Helvetica Neue", "Arial", "DejaVu Sans"),
  fill: rgb("#1d1d1f"),
)

#show link: set text(fill: rgb("#0a52a3"))

#set page(
  numbering: "1",
  footer: context {
    set text(size: 9pt, fill: rgb("#6e6e73"))
    line(length: 100%, stroke: 0.5pt + rgb("#d2d2d7"))
    v(2pt)
    align(center)[Page #counter(page).display() of #counter(page).final().first()]
  },
)
