# LinkedIn Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `text`, `image_text`, `video`, `document` (1 PDF carousel `<= 100 MB`; no mixed image+video) |
| Title (for media/article) | Max **200** characters |
| Body (`commentary`) | Max **3000** characters |
| Options | `firstReply` (validated first comment for outbound links/CTAs, `<= 3000` chars) |
| Images | 1–**9** images (`jpg`, `jpeg`, `png`, `gif`), max **10 MB** each |
| Video | 1 video (`mp4`), max **200 MB**, max **600s** |
| Topics | No native API topic field (inline hashtags optional, 0–3) |
| Required Headers | `Authorization: Bearer <token>`, `LinkedIn-Version: YYYYMM`, `X-Restli-Protocol-Version: 2.0.0` |
| Live URL Pattern | `https://www.linkedin.com/feed/update/<postUrn>` |
