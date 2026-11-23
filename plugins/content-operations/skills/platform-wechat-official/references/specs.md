# WeChat Official Account Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `image_text` (HTML article) |
| Title Length | Max **64** characters |
| Body Length | Max **20000** characters (HTML markup; inline images must be uploaded to WeChat CDN first) |
| Images | Up to **20** images (`jpg`, `jpeg`, `png`, `gif`, `bmp`), max **10 MB** each; cover `2.35:1` (`900x383`) |
| Topics | No native API topic field |
| Options | `author` (`<= 8` chars), `digest` (`<= 120` chars), `need_open_comment` (`0`/`1`), `only_fans_can_comment` (`0`/`1`), `showCoverPic` (`bool`), `sourceUrl` (HTTPS) |
| Publish Strategy | Draft first (`draft/add`) → poll `freepublish/get` after `freepublish/submit` |
