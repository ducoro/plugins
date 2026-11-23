# Kuaishou (Kwai) Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `video` only |
| Title Length | Max **30** characters |
| Body / Total Text | Max **1000** characters combined |
| Topics / Tags | Supported; recommended max **4** tags |
| Video | 1 video (`mp4`, `avi`, `mkv`, `mov`, `webm`), max **100 MB** (OpenAPI baseline), max **1800s** |
| Cover Image | `jpg`, `jpeg`, `png`, `bmp`, `webp`, max **20 MB** |
| Options | `cover` (cover image file/bytes uploaded in multipart `POST /openapi/photo/publish`), `stereo_type`, `merchant_product_id` |
| Live URL Pattern | `https://www.kuaishou.com/short-video/<photoId>` |
