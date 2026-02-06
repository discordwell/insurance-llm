OCR_PROMPT = """Extract ALL text from this document image. This is likely an insurance document, certificate of insurance (COI), policy, lease, or contract.

Return the text exactly as it appears, preserving:
- Line breaks and formatting
- Checkbox status (show as [X] for checked, [ ] for unchecked)
- Tables and columns (use spacing to preserve alignment)
- Headers and section titles
- All numbers, dates, and dollar amounts exactly as written

Do not summarize or interpret - just extract the raw text content."""
