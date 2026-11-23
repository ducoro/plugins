# YouTube Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `video` only (long-form `16:9` or Shorts `9:16`) |
| Title Length | Max **100** characters |
| Description Length | Max **5000** characters |
| Tags (`tags`) | Native array; combined length max **500** characters |
| Video | 1 video (`mp4`, `mov`, `avi`, `wmv`, `flv`, `mkv`), max **256 GB**, max **43200s** (12 hours) |
| Custom Thumbnail | `1280x720` (`16:9`), `jpg`/`png`, max **2 MB** |
| Options | `privacyStatus` (`public` \| `unlisted` \| `private`), `categoryId`, `publishAt` (ISO-8601; requires `privacyStatus: "private"`), `license` (`youtube` \| `creativeCommon`), `embeddable`, `notifySubscribers`, `selfDeclaredMadeForKids` |
| Post-Publish Update | Supported (`PUT /youtube/v3/videos`) |
| Live URL Pattern | `https://www.youtube.com/watch?v=<videoId>` |
