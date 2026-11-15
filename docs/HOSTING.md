# Hosting (optional)

**Status (15 Nov 2026): no public live demo.** The submission is the repository plus the video; anyone can run the app locally with the data package (see the README). Hosting was prepared and tested but not published: Hugging Face now requires a PRO subscription for Docker Spaces on the free CPU, the free Docker hosts we checked (Render, Koyeb) cap memory at 512 MB while the app peaks at about 571 MB, and Vercel's serverless Python functions cannot hold the geospatial libraries or the 376 MB product. The files below run unchanged on any Docker host with about 1 GB of memory.

The Docker image targets a Hugging Face Space (Docker SDK). One container serves everything:
`deploy/serve.py` runs the FastAPI backend and serves the frontend's static export from the same port, so the
browser talks to one origin.

- `deploy/huggingface/Dockerfile` clones this repository (`main`), builds the frontend with
  `TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin`, installs `backend/requirements.txt`, then `deploy/fetch_data.py` downloads the four
  data parts from the `data-package-v1` branch, checks SHA-256 `3290a66b…a2cfa`, and unzips the product.
- `deploy/huggingface/README.md` is the Space's configuration header (Docker SDK, port 7860).

## Create the Space (if a PRO or paid plan is available; about 10 minutes)
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

## Tested
The Space image was built from GitHub with Docker on 15 Nov 2026 and run as user 1000 on port 7860: every page and
API route (including validation, cross-track, timelapse, downloads and spot check) returned 200, and all five
modes rendered in English and Filipino with no page errors. The image is about 4.6 GB, within the free tier.
