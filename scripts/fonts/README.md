# Embedded typeface

[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) v2.304, subset to
only the characters each graphic actually draws, and inlined into the SVGs as
base64 @font-face.

| file | weight | covers |
|---|---|---|
| jbmono-ramp.woff2 | 400 | the 13 ramp characters in ascii.svg |
| jbmono-head.woff2 | 600 | the letters used by the section headings |
| jbmono-400.woff2 | 400 | basic latin, for the stat graphics |
| jbmono-600.woff2 | 600 | basic latin, for the stat graphics |

Licensed under the SIL Open Font License 1.1 — see OFL.txt.

## Download Instructions

To download the font files, run:

```bash
cd scripts/fonts
for file in jbmono-400.woff2 jbmono-600.woff2 jbmono-head.woff2 jbmono-ramp.woff2; do
  curl -L -o "$file" "https://raw.githubusercontent.com/andriidrok1/andriidrok1/main/scripts/fonts/$file"
done
curl -L -o OFL.txt "https://raw.githubusercontent.com/andriidrok1/andriidrok1/main/scripts/fonts/OFL.txt"
cd ../..
```

Or download them manually from: https://github.com/andriidrok1/andriidrok1/tree/main/scripts/fonts