# Hosting the demo

The public demo runs on a free Hugging Face Space (Docker SDK). One container serves everything:
`deploy/serve.py` runs the FastAPI backend and serves the frontend's static export from the same port, so the
browser talks to one origin.

- `deploy/huggingface/Dockerfile` clones this repository (`main`), builds the frontend with
  `TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin`, installs `backend/requirements.txt`, downloads the four
  data parts from the `data-package-v1` branch, checks SHA-256 `3290a66b…a2cfa`, and unzips the product.
- `deploy/huggingface/README.md` is the Space's configuration header (Docker SDK, port 7860).

## Create the Space (owner, about 10 minutes)
1. Sign up or sign in at https://huggingface.co (free).
2. New Space: https://huggingface.co/new-space. Name `tanaw`, licence MIT, SDK **Docker** (Blank template),
   hardware **CPU basic (free)**, visibility **Public**. Create.
3. In the Space, open **Files**, choose **Add file → Upload files**, and upload `deploy/huggingface/Dockerfile` and
   `deploy/huggingface/README.md` (replace the README the Space created). Commit.
4. The **Logs** tab shows the build (about 5–10 minutes: npm install, frontend build, Python packages, 392 MB data).
   When it says Running, open `https://<your-username>-tanaw.hf.space` in a signed-out browser.
5. To pick up later changes on `main`, use **Settings → Factory rebuild**.

Free Spaces sleep after about 48 hours without visitors; the first visit after that takes about a minute.
The demo is the same code and data as the repository; it needs no Earthdata login.
