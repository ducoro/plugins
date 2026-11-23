# WeChat Official Account Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `image_text` (long-form HTML article) and `newspic` (小绿书 3:4 image swipe carousel) |
| Title Length | Max **64** characters (`image_text`); max **32** characters (`newspic`) |
| Body Length | Max **20000** characters HTML (`image_text`; inline styles only, zero `<style>`/`<div>`/`class`/`id`); max **1000** plain-text characters (`newspic`) |
| Images | `image_text`: recommend `<= 10` inline images (hard ceiling 20, max 10 MB each), primary cover `2.35:1` (`900x383`) + `1:1` share thumb; `newspic`: **1–20** `3:4` vertical images (`1080x1440`) |
| Topics | No native API topic field |
| Options | `author` (`<= 8` chars), `digest` (`<= 120` UTF-8 bytes, ~40 Chinese chars), `need_open_comment` (`0`/`1`), `only_fans_can_comment` (`0`/`1`), `showCoverPic` (`bool`), `sourceUrl` (HTTPS) |
| Publish Strategy | Draft first (`draft/add`) → poll `freepublish/get` after `freepublish/submit` |
